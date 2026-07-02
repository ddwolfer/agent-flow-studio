# Spec: carry-guardian — Bitget 抵押借幣 carry 倉位風控（arb-sentinel 擴充）
 
> 建議存放路徑：`docs/superpowers/specs/2026-07-02-carry-guardian.md`
> 實作位置：`arb-sentinel/`（擴充，非新專案）
> Phase 1 = 純監控告警（read-only）。Phase 2 = 自動動作（預設關閉，見 §9）。
 
---
 
## 1. 背景與倉位事實
 
使用者在 Bitget 有一組進行中的 carry trade：
 
| 項目 | 數值（2026-07-02 快照） |
|---|---|
| 借款 | 21,580.39 USDC（活期，時利率 0.000342%，年化約 3.0%，浮動） |
| 抵押 | 0.56571125 BTC |
| 質押率（LTV） | 63.45%（補保線 85%，強平線 91%） |
| 資產 | 24,604.61 USDGO 放在簡單賺幣活期 |
| 收益 | 階梯 4%~10%，目前部位全落在第一階梯 10%（<100k） |
| 預期日派息 | 持倉 × 10% / 365 ≈ 6.74 USDGO/天 |
| 借款訂單 ID | 1454384882276573190 |
 
風險排序（高→低）：① 質押率逼近強平而人不在場；② USDGO 流動性/脫鉤；③ 補貼利率退坡未察覺；④ 借款利率飆升。本模組把 ①③④ 自動化，② 已由現有 `depeg` task 部分覆蓋（本 spec 補上深度檢查）。
 
## 2. 設計原則（沿用 arb-sentinel 既有哲學）
 
1. **Deterministic Python，排程絕不跑 `claude -p`**，零 LLM。
2. **Collector never raises**：所有網路呼叫回 `(data, err)`，任何失敗降級為告警而不是 crash。
3. **Phase 1 只用 read-only API key**（沿用現有 `BITGET_API_KEY/SECRET/PASSPHRASE`）。專案 CLAUDE.md 的「never enable trade/withdraw/transfer」規則在 Phase 1 完全不動。
4. 告警走既有 `notify.send_message`，路由到**新的 forum topic**（倉位風控），不混入 arb topic。
5. Git 依專案規則小步提交（見 root `CLAUDE.md`），secrets 一律 `.env`。
## 3. 整合方式
 
- 新模組：`arb_sentinel/carry.py`（規則引擎，pure functions，模式仿 `exits.py`）
- 擴充：`arb_sentinel/collectors/bitget.py` 加 4 個函式（見 §4），複用既有 `_signed_get`
- 新 task：`--task carry`（快循環）與 `--task carry-digest`（每日摘要），註冊進 `run.py`
- 新 launchd plist：`launchd/com.arbsentinel.carry.plist`、`com.arbsentinel.carrydigest.plist`
- 狀態：沿用 state.json 機制，新增 namespace `carry:*`（見 §6 去重規則）
## 4. 資料來源（新增 collector 函式）
 
| 函式 | 端點 | 認證 | 用途 |
|---|---|---|---|
| `loan_ongoing_orders()` | `GET /api/v2/earn/loan/ongoing-orders` | 簽名 | pledgeRate、負債、未還利息 |
| `loan_hour_interest(coin="USDC")` | `GET /api/v2/earn/loan/public/hour-interest` | 公開 | 借款時利率 |
| `savings_assets()` / `savings_records(type=...)` | `GET /api/v2/earn/savings/assets`、`/api/v2/earn/savings/records` | 簽名 | USDGO 活期餘額與每日派息 |
| `spot_orderbook(symbol="USDGOUSDC", limit=15)` | `GET /api/v2/spot/market/orderbook` | 公開 | 買一價、買方深度 |
 
**實作第一步（必做）**：先寫一支 `scripts/carry-smoke.py`，用現有 read-only key 依序打上面四個端點並 print 原始 JSON。目的：
1. 驗證帳戶走 v2 classic（`/api/v2/earn/loan/*`）還是 v3 UTA（`/api/v3/loan/*`）——以能查到訂單 `1454384882276573190` 為準；若是 v3，端點路徑整組替換，欄位名以實際回傳為準。
2. 確認實際欄位名（`pledgeRate` 的單位是 `0.6345` 還是 `63.45`——**不要猜，跑了才知道**，閾值比較要正規化成小數）。
3. 確認派息在 `records` 的哪個 type 下（可能是 `interest` / `profit`）。
smoke 結果貼進 spec 同目錄的 `carry-smoke-notes.md` 再開始寫正式 collector。
## 5. 監控規則（carry.py，全部 pure function + 單元測試）
 
### 5.1 質押率哨兵（每次 `carry` task 執行）
 
正規化後的 `ltv`（0~1）分級：
 
| 等級 | 條件 | 行為 |
|---|---|---|
| ⚫ OK | ltv < 0.72 | 不通知（寫 state 供 digest 用） |
| 🟡 WATCH | 0.72 ≤ ltv < 0.78 | 通知一次，之後每 +0.02 或跨級才再通知 |
| 🟠 ALERT | 0.78 ≤ ltv < 0.82 | 通知，冷卻 30 分鐘 |
| 🔴 CRITICAL | ltv ≥ 0.82 | **每次執行都通知**（不去重），訊息附操作指引 |
 
🔴 訊息必附：目前 ltv、距補保(0.85)/強平(0.91)還差幾 %、換算 BTC 價格還能跌幾 %、兩條逃生指令提示（「賣 USDGO 還款」優先於「補 BTC」）。BTC 價換算公式：`price = debt / (ltv_target × collateral_btc)`。
 
**API 失敗也是事件**：`ongoing-orders` 連續 3 次失敗 → 🟠 告警「風控失明」。查無進行中訂單 → 通知「借款已結清或被平」，並停用後續檢查直到 state 重置。
 
### 5.2 派息稽核（每日一次，併入 carry-digest）
 
- `expected = usdgo_balance × 0.10 / 365`
- 昨日實際派息 < `0.9 × expected` → 🟠「補貼疑似退坡」；完全沒有派息紀錄 → 🔴
- 動態階梯：若餘額 >100k，expected 改用階梯加權（100k 內 10%、超出部分 6.5%），階梯常數進 config
### 5.3 借款利率監控（每次 `carry` task 執行，公開端點）
 
- 時利率 > `0.00057%`（年化 ≈ 5%）→ 🟡；> `0.00080%`（≈ 7%）→ 🟠
- 同時計算**淨利差**：`savings_apr − borrow_apr`，< 2% → 🟠「利差瀕死，依既定計畫平倉」
### 5.4 USDGO 深度/錨定（每次 `carry` task 執行，公開端點）
 
- 買一價 < 0.9990 → 🟠；< 0.9970 → 🔴
- 買方前 15 檔累計量 < 2 × USDGO 持倉 → 🟡「深度不足以無滑點出場」
- 與既有 `depeg` task 的關係：`depeg` 管的是通用穩定幣追蹤（30 分鐘級），本檢查是針對本倉位的高頻版；共用 `depeg_bps` config 但獨立閾值 `carry.bid_floor`
### 5.5 每日摘要（carry-digest，每天 08:00 TPE 一則）
 
單一訊息，格式仿 `_brief.md` 風格：LTV、負債、USDGO 餘額、昨日派息（實際 vs 預期）、借款年化、淨利差、估計日淨收益（USD）、四項檢查的綠燈/黃燈狀態。**摘要同時是 heartbeat**——沒收到摘要 = 系統掛了，這點寫進訊息 footer 提醒使用者。
 
## 6. 通知與去重
 
- 新 env：`TELEGRAM_TOPIC_CARRY`（forum topic id），沿用 notify.py 的 fail-closed 行為（topic 空值拒發並 stderr）
- state key：`carry:ltv_tier`、`carry:ltv_last_notified`、`carry:rate_alert`、`carry:depth_alert`、`carry:payout_date`
- 去重原則：**升級必通知、降級通知一次「解除」、同級靠 cooldown**。🔴 級不去重。
## 7. 排程與 MacBook 睡眠限制（重要）
 
- `com.arbsentinel.carry.plist`：`StartInterval` 300 秒（5 分鐘），24/7
- `com.arbsentinel.carrydigest.plist`：`StartCalendarInterval` 08:00
**已知限制：MacBook 闔蓋/睡眠時 launchd 不執行，凌晨暴跌存在監控空窗。** 緩解措施（依序）：
1. README 註明建議 `sudo pmset repeat wakeorpoweron MTWRFSU 03:00:00` 之類的定時喚醒，或插電時 `caffeinate` 常駐（由使用者決定，spec 不強制）
2. 訊息與 README 提醒使用者**同時開啟 Bitget App 原生的補保/強平推播**作為獨立備援
3. 每日 digest 兼 heartbeat（§5.5），空窗至少隔天早上會被發現
4. 長期解：此 task 移到常駐 VPS 只需要搬 plist → cron，程式碼不動——collector 保持零 macOS 依賴
## 8. config.yaml / .env 增項
 
```yaml
carry:
  enabled: true
  loan_order_id: "1454384882276573190"   # 空字串 = 自動取第一筆進行中訂單
  loan_coin: USDC
  pledge_coin: BTC
  earn_asset: USDGO
  pair: USDGOUSDC
  savings_apr_tiers: [[100000, 0.10], [1000000, 0.065], [null, 0.04]]
  ltv_watch: 0.72
  ltv_alert: 0.78
  ltv_critical: 0.82
  margin_call_ltv: 0.85
  liquidation_ltv: 0.91
  borrow_hour_rate_warn: 0.0000057   # 小數，非百分比
  borrow_hour_rate_alert: 0.0000080
  net_spread_floor: 0.02
  bid_floor_warn: 0.9990
  bid_floor_critical: 0.9970
  depth_multiple: 2.0
  payout_ratio_floor: 0.9
  alert_cooldown_min: 30
```
 
`.env` 新增：`TELEGRAM_TOPIC_CARRY=<topic_id>`（其餘沿用既有 Bitget read-only 三件組）。
 
## 9. Phase 2 — 自動動作（本次不實作，僅預留介面）
 
- 觸發：ltv ≥ `auto_action_ltv`（建議 0.83）時自動執行二選一：(a) 市價區間限價賣出 USDGO + `POST /api/v2/earn/loan/repay` 部分還款（預設，撤退優於加碼）；(b) `POST /api/v2/earn/loan/revise-pledge` 追加 BTC
- **前置條件（缺一不可）**：① 使用者本人修改專案 CLAUDE.md 的 read-only 規則並在 commit message 說明；② 新開一組獨立 API key，僅開「交易+理財」權限、**永不開提幣**、綁 IP 白名單，存於 `BITGET_TRADE_KEY/SECRET/PASSPHRASE`；③ config `carry.auto_actions: false` 預設關閉；④ 先以 `dry_run: true` 跑滿一週，所有 would-have-executed 動作只發通知
- 賣出 USDGO 一律用帶保護價的限價 IOC（如買一 − 5bps），禁止裸市價單
- Claude Code 注意：**在使用者完成前置條件 ① 之前，不得實作任何簽名 POST**。本 spec 的 Phase 1 驗收不含此節。
## 10. 測試與驗收
 
單元測試（仿 `tests/test_collectors_base.py` 風格，pure function 直測）：
- LTV 分級：0.70/0.73/0.79/0.83 各落正確等級；0.72→0.74 不重複通知、0.74→0.79 通知、0.83 連續兩次都通知
- pledgeRate 單位正規化：輸入 `"63.45"` 與 `"0.6345"` 都得到 0.6345
- 派息稽核：6.7→綠、5.9→🟠、無紀錄→🔴；階梯加權在 150k 餘額下正確
- 深度檢查：構造 orderbook fixture 驗證買一與累計深度兩條規則
- collector 失敗路徑：連續失敗計數與「風控失明」告警
端到端驗收（手動）：
1. `--task carry` 跑通，Telegram carry topic 收到訊息或安靜通過（LTV 63% 應為 ⚫ 無聲）
2. 暫時把 `ltv_watch` 調到 0.60 觸發 🟡，確認訊息格式含 BTC 價換算，改回後收到「解除」
3. `--task carry-digest` 產出完整摘要且數字與 Bitget 網頁一致（±捨入）
4. 拔網路跑一次，確認不 crash、stderr 有紀錄
5. launchd 載入後觀察 24h，digest 準時到達
## 11. 交付物清單
 
- `arb_sentinel/carry.py` + `arb_sentinel/collectors/bitget.py` 擴充
- `run.py` 註冊 `carry`、`carry-digest`
- `scripts/carry-smoke.py` + `docs/superpowers/specs/carry-smoke-notes.md`
- `launchd/com.arbsentinel.carry.plist`、`com.arbsentinel.carrydigest.plist`
- `config.yaml` 增區塊、`.env.example` 增 `TELEGRAM_TOPIC_CARRY`
- `tests/test_carry.py`
- `arb-sentinel/README.md` 增章節（含睡眠限制與 Bitget 原生推播備援的說明）