# Spec: price-zone — SMC 結構視角下的價格區間模組

> 版本:**v0.2**(草稿,尚未實作)
> 前版:v0.1(chat 靈感稿,見對話紀錄)
> 隸屬:`deep-research-stock` skill 的擴充(新增報告 §8)
> 目標讀者:Claude Code(實作者)

---

## 0. v0.2 相對 v0.1 的變更摘要(讀者先看這段)

| # | 變更 | 為什麼 |
|---|---|---|
| A | **§8 標題**:「技術結構與價格區間」→「**SMC 結構視角下的價格區間**」 | BOS/CHoCH/FVG/eq H/L 是 Smart Money Concepts / ICT 學派方言,不是「客觀技術結構」。命名誠實化,日後加 EMA/MACD 等其他學派不會 schema 衝突。 |
| B | **區間寬度公式改用「ATR 為主,價格 % 為地板/天花板」** | `0.5×ATR` 對 $985+β 2.14 的 MU 會產生 ~10% 寬的區間,失去「參考位」意義。加入 0.75%–2.5% 價格帶邊界,讓區間永遠在螢幕上大致 1.5–5%。 |
| C | **逆勢(countertrend)時 `buy_zone = null`,改輸出 `buy_zone_pending`** | 原本「畫區間 + 貼警語」讀者一眼看到區間、警語當耳邊風。改為明確不輸出,並提供「要看到什麼價位才會產生買區」的 trigger price。 |
| D | **Fractal look-ahead 明確處理**:最新 3 根 K 標 `pending`,不得當 zone basis | v0.1 未定義。無此規則會出現「昨天 K 被判定為 swing、今天 K 打破 → basis 消失」的 UX 惡夢。 |
| E | **JSON 加 `schema_version: "v0.2"`** | 為「欄位可增不可減」政策提供版本座標。 |
| F | **驗收 §6 加 golden-file 回歸測試** | 三次跑 byte-identical 只能防「同 run 內」漂移,防不了演算法自身悄悄改。 |
| G | **v0.1 的 `volume_nodes` 移出 v0.1 範圍** | 24 bins × 12mo 的 1D volume-at-price 訊號密度不高、又混合近遠期。v0.2 若加,直接時間加權。 |
| H | **§5 新增兩條硬規則**:`buy_zone.high < price` 必須標「等待回檔」(`needs_pullback=true`);`sell_zone.high < price` 直接 null | 防止「已破結構」被當成有效區間輸出。**修訂**:v0.2 首稿誤寫為 `buy_zone.low > price`,語意錯誤(zone 在現價之上 = 需上漲進場,非回檔),已於實作時更正。 |

---

## 1. 目標與非目標

### 目標

為 `deep-research-stock` 報告的每個 ticker 產出:

1. 日線級別的**結構判定**(趨勢方向、最近 BOS/CHoCH、premium/discount 位置)
2. **買入參考區間**與**賣出/減碼參考區間**(帶邏輯依據,非單一價位)
3. **失效條件**(跌破/突破哪個價位代表區間作廢)
4. 流動性池標註(equal lows/highs 掃損風險)

### 非目標(明確排除)

- ❌ 不做 1H 以下級別的進場點(僅日線波段參考)
- ❌ 不做自動下單、不接交易所 API
- ❌ 不輸出「建議買入/賣出」等指令性措辭
- ❌ LLM 不得目測 K 線自行發明價位(見 §5)
- ❌ v0.1 不做 volume profile(見變更 G)

---

## 2. 架構總覽

```
ticker
  │
  ▼
[compute_zones.py]  ← 純 Python,確定性計算,不經 LLM
  │  輸入:yfinance 日線 OHLCV(12mo)
  │  輸出:結構 JSON(swing points、趨勢、FVG、區間、失效價...)
  ▼
[LLM(skill 內)]
  │  只讀 JSON,負責文字詮釋與 narrative
  ▼
報告 §8「SMC 結構視角下的價格區間」
```

**核心分工:可規則化的全部交給 Python;LLM 只做解讀,不做計算。**
同一份數據跑 N 次,區間數字必須完全一致。

---

## 3. 計算腳本 `compute_zones.py`

### 3.1 位置與呼叫方式

- 路徑:`finance-workflows/scripts/compute_zones.py`
- 環境:沿用 `finance-workflows/mcp/.venv`(需補裝 `yfinance`)
- CLI:
  ```bash
  .venv/bin/python compute_zones.py TICKER [--period 12mo] [--out zones/TICKER.json]
  ```
- 在 skill 流程中由 Bash tool 呼叫;預設寫入 `finance-workflows/reports/deep-stock-research/_zones/<DATE>/<TICKER>.json`

### 3.2 數據來源

- `yfinance.Ticker(ticker).history(period="12mo", interval="1d", auto_adjust=True)`
- 最少需要 60 根日 K;不足時進入**降級模式**(見 §3.6)
- **穩定性**:index 只保留到日期,不帶時區,避免因 yfinance 分秒級微幅修訂造成 golden-file 誤 diff

### 3.3 計算項目(全部為確定性規則)

| 項目 | 定義 | 參數 |
|---|---|---|
| Swing High/Low | fractal:左右各 N 根皆更低(高) | `N = 3` |
| **最新 3 根 K** | 標記 `pending`,不得成為 zone basis(**v0.2 新增**) | — |
| 趨勢判定 | 最近 4 個 **已確認** swing 的 HH/HL vs LH/LL 序列 | — |
| BOS | 收盤價突破最近同向 swing 極值 | 以收盤價認定 |
| CHoCH | 收盤價突破最近**反向** swing 極值 | 以收盤價認定 |
| Equal Lows/Highs | ≥2 個 swing 極值落在 tolerance 內 | `tolerance = 0.3 × ATR(14)` |
| Daily FVG | 三根 K:K1 高點 < K3 低點(bullish)或反之 | 只保留**未回補**的 |
| ATR | Wilder ATR | `period = 14` |
| Range 與均衡 | 近 `120` 根內最高/最低,50% 為 equilibrium | premium = 上半,discount = 下半 |

### 3.4 區間寬度公式(**v0.2 修訂**)

```python
half_width = min(
    max(0.5 * atr14, 0.0075 * price),   # 地板:price 的 0.75%
    0.025 * price                         # 天花板:price 的 2.5%
)
# 白話:0.5 ATR 為主;低價低波動時 0.75% 保底,高價高波動時 2.5% 封頂
# 結果:區間總寬度永遠落在 price 的 1.5–5%
```

### 3.5 區間推導規則

**買入參考區(buy_zone)** — 需同時符合三條件才輸出:
1. 當前趨勢為 `up` 或 `range`(**逆勢不輸出,改走 `buy_zone_pending`**)
2. 存在有效 basis:未回補 bullish FVG 或**已確認**的 HL swing low(最新 3 根 pending 不算)
3. basis 位於 discount zone(equilibrium 以下)

```
# v0.2.1 修訂:zone.low 錨定在失效價,往上延伸
# 保證 zone.low == invalidation_price(不再出現「失效價在區間內部」的語意矛盾)

if basis == FVG:
    buy_zone.low  = FVG.bottom
    buy_zone.high = max(FVG.top, buy_zone.low + 2 * half_width)
elif basis == swing_low:
    buy_zone.low  = swing_low_price
    buy_zone.high = swing_low_price + 2 * half_width

invalidation_price = buy_zone.low
```

- 若 `buy_zone.high < current_price`(zone 位於現價之下):標註 `"needs_pullback": true`,§8 敘述必須用「等待回檔到 xx–xx」而非「當前買入區」
- 若 `buy_zone.low > current_price`(zone 位於現價之上,異常):`warnings` 加 `"buy_zone_above_price_anomaly"`,§8 應標「基準異常,請人工檢視」
- 若區間下方 `1.5×ATR` 內存在 equal lows → JSON 標 `"liquidity_below"`,§8 必寫「下方 X 元有流動性池,存在被掃風險」

**逆勢時的 `buy_zone_pending`(**v0.2 新增**)**

```json
"buy_zone": null,
"buy_zone_pending": {
  "reason": "downtrend — 目前無有效買區,需先 CHoCH 反轉",
  "watch_price_for_choch": 0.0,
  "watch_rule": "daily close above 0.0"
}
```

**賣出/減碼參考區(sell_zone)** — 需同時符合:
1. 存在有效 basis:equal highs 或**已確認**的 swing high
2. basis 位於 premium zone

```
# v0.2.1 修訂:sell_zone 為 buy_zone 的鏡像
sell_zone.high = invalidation_price  # equal_highs 或 swing_high
sell_zone.low  = sell_zone.high − 2 * half_width
```

- 若 `sell_zone.high < current_price`:**直接 null** 且 `warnings` 加 `"structure_already_broken_above"`(結構已被突破,原 zone 失效)

**失效條件(invalidation)**:

- 買區失效價 = 買區依據的 swing low 收盤跌破
- 賣區失效價 = 賣區依據的 swing high 收盤突破
- JSON 必須包含 `invalidation_price` 與 `invalidation_rule`(機器可讀)

### 3.6 降級模式(新股/數據不足)

觸發:日 K < 60 根。輸出改為:

- `"mode": "degraded"`
- 只提供:IPO 價(首日開盤)、歷史最高/最低、當前價在歷史區間的百分位、ATR
- **不輸出** buy_zone / sell_zone
- 報告 §8 寫明:「上市未滿 60 個交易日,結構樣本不足,僅提供位置參考,不產出買賣區間。」

### 3.7 輸出 JSON Schema

```json
{
  "schema_version": "v0.2",
  "ticker": "NVDA",
  "as_of": "2026-07-08",
  "as_of_confirmed_swing": "2026-07-03",
  "mode": "full",
  "price": 0.0,
  "atr14": 0.0,
  "trend": {"direction": "up|down|range", "basis": "HH/HL x2 since 2026-05-14"},
  "last_bos": {"price": 0.0, "date": "", "direction": "up|down"},
  "last_choch": {"price": 0.0, "date": "", "direction": "up|down"},
  "range": {"high": 0.0, "low": 0.0, "equilibrium": 0.0, "position": "premium|discount"},
  "equal_lows": [{"price": 0.0, "touches": 2}],
  "equal_highs": [],
  "unfilled_fvg": [{"type": "bullish", "top": 0.0, "bottom": 0.0, "date": ""}],
  "buy_zone": {
    "low": 0.0, "high": 0.0,
    "basis": "unfilled bullish FVG 2026-06-20",
    "needs_pullback": false,
    "liquidity_below": {"exists": true, "price": 0.0},
    "invalidation_price": 0.0,
    "invalidation_rule": "daily close below 0.0"
  },
  "buy_zone_pending": null,
  "sell_zone": null,
  "warnings": ["structure_already_broken_above"]
}
```

規則:
- **schema_version 必填**;版本升級時舊消費者仍能讀
- 欄位可增不可減;算不出來填 `null` 並在 `warnings` 註明
- `buy_zone` 與 `buy_zone_pending` **互斥**(其一必為 null)

---

## 4. SKILL.md 修改點

### 4.1 Stage 2 每個 ticker 新增步驟

- **Tier A / Tier B / ETF** 一律執行 `compute_zones.py <ticker>` 並讀 JSON
- 腳本便宜(< 3 秒),ETF 純 price action 反而更適合此模組

### 4.2 報告新增 §8「SMC 結構視角下的價格區間」

**Tier A 完整版**(150–250 字 + 表格):
- 結構敘述:趨勢方向、最近 BOS/CHoCH、目前在 premium 還是 discount
- 買入參考區 + basis + 流動性風險(或 `buy_zone_pending` 的 trigger)
- 賣出/減碼參考區 + basis
- **失效條件**(獨立一行,加粗)

**Tier B 精簡版**(三行):
```
趨勢:下跌(LH/LL)｜位置:discount
買區:暫無(需 daily close > xx 觸發 CHoCH)
減碼:xx–xx｜失效:收盤 > xx
```

**降級模式**:一行說明 + 位置百分位,不給區間。

### 4.3 §7 vs §8 銜接

§7 的「方向 + 信心」若與 §8 的趨勢判定矛盾,**不得隱藏**,必須明寫:
「基本面與 SMC 結構目前分歧,傾向等待 §8 失效條件解除。」

---

## 5. 硬規則(faithfulness 延伸)

1. **報告中出現的所有價位數字,必須存在於 JSON 中。** LLM 不得四捨五入以外地修改。
2. 每個區間必須附 `basis` 與 `invalidation`,缺一不給區間。
3. 所有區間文字一律標註「SMC 技術參考區間,非投資建議」(HTML footer 統一標一次)。
4. 措辭禁令:禁止「建議買入」「必漲」「強力支撐」;equal lows 一律稱「流動性池」並附掃損風險說明。
5. 腳本失敗 → §8 標「技術數據不可用,本次跳過」,不影響其餘章節。
6. **v0.2 新增**:`buy_zone.high < price` 時(zone 位於現價之下),措辭必為「等待回檔到 xx–xx」;若寫成「當前買區」為 spec 違規。`buy_zone.low > price` 為異常,標 warning。
7. **v0.2 新增**:`sell_zone.high < price` 時,直接 null 不寫;不得以「近期壓力位」等模糊措辭包裝已破結構。
8. 沿用主 skill 規則:不 spawn `claude -p`、不新增 `.mcp.json` 以外的 MCP。yfinance 是 Python 套件,允許直接在腳本內使用。

---

## 6. 驗收標準

- [ ] `compute_zones.py NVDA` 連跑 3 次,JSON 逐 byte 一致(除 `as_of`)
- [ ] **v0.2 新增**:golden-file 回歸測試 — 固定 ticker + 固定歷史 as_of 日期(用快照 CSV 而非 live yfinance),期望 JSON 存為 fixture,任何演算法改動須解釋 diff
- [ ] 日 K < 60 根的 ticker 正確進入降級模式
- [ ] ETF(如 IVV)可正常產出區間
- [ ] 趨勢下跌的票,`buy_zone = null` 且 `buy_zone_pending` 提供 CHoCH trigger price
- [ ] equal lows 存在時,`liquidity_below` 正確標註且報告有掃損說明
- [ ] `buy_zone.low > price` 時,報告措辭出現「等待回檔」
- [ ] `sell_zone` 若因結構已破而 null,`warnings` 明確標 `structure_already_broken_above`
- [ ] 報告中每個價位都能在 JSON 中找到(寫個 grep 驗證腳本)
- [ ] 單一 ticker 全流程 < 15 秒、新增 LLM token < 1.5k

---

## 7. 未來版本(不在 v0.2 範圍)

- 1H 級別數據 + 多時間框架共振
- Volume Profile(時間加權,非 v0.1 的 24-bin 平均)
- 區間回測:歷史區間 vs 後續走勢命中率(接 knowledge-graph)
- Telegram 推播附區間摘要
- SMC 以外的技術學派(EMA/MACD/RSI)並列 lens
