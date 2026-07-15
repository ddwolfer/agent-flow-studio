# Spec: binance-square-daily — 幣安廣場日更草稿 pipeline

> 版本:v1(設計稿,待 user 過目後實作)
> 日期:2026-07-15
> 定位:**6 週實驗**,唯一 KPI = 追蹤數斜率;收益期望值 ≈ 0(見 §8)
> 前置研究:`finance-workflows/reports/binance-square-poc/`(drafts v1–v4 + square-style-study)
> KG 錨:`90d771bd`(可行性評估)、`7628581b`(貼文格式規則)

---

## 1. 目標與非目標

### 目標
每日 18:30 TPE 自動產出 **3 篇幣安廣場貼文候選**(不同 persona × 側重),推到
Telegram topic `TELEGRAM_TOPIC_BINANCE_SQUARE`(=1715),user 看心情挑一篇
(或都不發)手動貼上廣場。單日人工投入 ≤5 分鐘。

### 非目標
- ❌ 不自動發文(幣安無發文 API;人工 gate 也是反降權保險)
- ❌ 不做盤中(1H↓)分析 — 沿用 price-zone spec 的日線限定
- ❌ 不帶單:不給雙向進出場價、不曬單、不寫「建議買入」
- ❌ 不以收益為目標(冷啟動返佣 ≈ $0,見研究)

---

## 2. 內容規則(全部已實證定案)

### 2.1 長度與結構(KG `7628581b`)
- **220–350 字**(不含空白)。下限 = 挖礦資格 200 字 + buffer;上限 = user 親手濃縮示範的長度
- **結構公式:hook(1-2 句)→ 📌 條件式劇本/數據條列 → 開放式問句結尾**
- 砍掉中間說理鋪陳(滑動讀者不讀論證)
- 濃縮後通讀:引導句後必須有被引導的內容(懸空句檢查)

### 2.2 固定元素(每篇)
- `$幣種` 標籤 ×3 用滿(優先:當篇主角 > BTC > ETH/BNB)
- `#話題` ×5(至少 1 個蹭當日熱門話題,若有相關)
- ⚠️ 免責 footer:「非投資建議」+ 失效位 = 紀律線措辭
- 建議方向 chip(看漲/看跌)標注在草稿標頭,發文時選

### 2.3 零術語規則(v3 定案)
發文禁用:CHoCH、BOS、FVG、equal lows/highs、liquidity、premium/discount、
invalidation、SMC、order block。每個結構概念用「行為描述」:

| SMC 術語 | 人話 |
|---|---|
| CHoCH / BOS | 「下跌的節奏第一次被打斷」「收盤站上前高」 |
| FVG | 「衝太快沒人成交的真空區」 |
| equal lows + 流動性池 | 「三次跌到同一位置都彈 → 大家停損掛同一處 → 大戶的提款機」 |
| liquidity sweep | 「往下捅一根把停損掃掉再漲」 |
| invalidation | 「跌破就代表我看錯」「紀律線」 |
| HH/HL | 「低點一個比一個高」 |
| range/equilibrium | 「箱內遊戲」「區間中軸」 |

### 2.4 Faithfulness 紅線
- 條件式立場 OK(「守住 X 看多,破了我錯」= 有 accountability 的劇本)
- 禁止:「必漲」「建議買入」「立刻上車」等誘導即時下單措辭
- 所有價位必須來自 zone JSON / 行情數據,LLM 不得發明價位

## 3. 三 persona × 三側重(二維)

**Persona(風格):**
- **A 有立場老手**:第一人稱擔責(「我看多,但有條件」),轉化最高
- **B 數據偵探**:懸念 hook(「昨晚有一批空單被迫認賠 — 你發現了嗎?」),說故事
- **C 日更陪伴**:晨間儀式感(「行情作業照常交,直接抄」+ 大餅/乙太土話),養追蹤

**側重(方向感,由當日 zone JSON 決定,不互相矛盾):**
- 主劇本(結構偏多/偏空的正面敘述)
- 風險面(同一數據,鏡頭對準流動性池/套牢區)
- 觀望(多空分界未決,等收盤表態)

每日產 3 篇 = 3 persona 各配一個「當日盤面最誠實的側重」。方向是數據的函數,
只有風格和鏡頭是選擇 — 禁止對同一數據產出互相矛盾的結論讓 user 挑。

## 4. 選題邏輯(跨資產差異化 — 實地研究核心發現)

優先序:
1. **當日熱門話題有我們覆蓋的資產** → 蹭話題(例:#美光股价跌14% ↔ MU zone JSON)。
   話題頁自帶瀏覽量,是冷啟動唯一分發外掛
2. **官方活動話題進行中** → 額外產 1 篇活動文(故事體,不佔 3 篇分析文名額)
3. **加密大事件日**(CPI、FOMC、爆倉潮)→ BTC/ETH 事件驅動
4. **平淡日** → C 版日更 BTC/ETH + 一篇美股跨資產(用當日 deep-stock zone 資料)

跨資產是差異化主軸:我們有 FRED + 美股 zone + 加密 zone 三線,純幣圈作者沒有。

## 5. Pipeline 架構

```
launchd 每日 18:30 TPE(com.financeworkflows.binance-square.plist)
  → scripts/compute_zones.py BTC-USD ETH-USD(+ 依當日熱題可加個股,重用當日 _zones/ 已有 JSON)
  → run-workflow.py binance-square(claude -p,吃 credit pool — user 已確認選項 A)
      prompt 讀:zone JSONs + 本 spec 的內容規則 + 熱門話題(fetch 廣場熱題,best-effort)
      產出:3 篇草稿(persona × 側重)寫入 reports/binance-square/{date}.md
  → notify:推 TELEGRAM_TOPIC_BINANCE_SQUARE(1715),每篇一則訊息(方便長按複製)
  → user 挑一篇貼廣場(附 K 線、選 chip、20:00–23:00 發或預約)
```

- 新 workflow json:`workflows/binance-square.json`(model 沿用 claude-sonnet 級,max_turns 小)
- 熱門話題抓取:v1 先用 web-fetch best-effort 抓廣場熱題頁;抓不到就跳過蹭話題步驟,
  不擋主流程(never-raise 慣例)
- 幣安九周年類活動偵測:v1 不自動,user 在 Telegram 看到活動自己說一聲即可

## 6. 檔案清單(實作時)

| 檔案 | 動作 |
|---|---|
| `workflows/binance-square.json` | 新增 |
| `prompts/binance-square/{framework,voice,main}.md` | 新增(內容規則 §2-§4 固化於此) |
| `launchd/com.financeworkflows.binance-square.plist` | 新增(18:30 TPE) |
| `.env` | `TELEGRAM_TOPIC_BINANCE_SQUARE=1715` ✅ 已填 |
| `reports/binance-square/` | 產出目錄(gitignored) |

Runner 不改(≤200 LoC 鐵律);新能力 = workflow json + prompts,符合 CLAUDE.md 慣例。

## 7. 驗收標準

- ☐ 手動跑一次 workflow,3 篇草稿字數全部落在 220–350(不含空白)
- ☐ 全部零 SMC 術語(grep 禁用詞清單 = 0 hit)
- ☐ 每篇有:hook、📌 條列、問句結尾、⚠️ footer、$×3、#×5、方向 chip 建議
- ☐ 3 篇方向側重不互相矛盾(同一 zone JSON 的不同鏡頭)
- ☐ Telegram 1715 收到 3+1 則(header + 3 篇),可長按複製
- ☐ zone JSON 價位 spot-check:草稿中每個價位都在 JSON 裡
- ☐ launchd 掛上後隔日 18:30 自動觸發成功

## 8. 實驗設計與停損

- **期間:6 週**(至 ~2026-08-26)
- **唯一 KPI:廣場追蹤數斜率**(週記一次即可);views 為輔助觀察
- **明確不看:** 返佣收益(冷啟動 ≈ $0,已實證:14K 粉大號單篇也只 600–4k views)
- **停損條件:** 6 週後追蹤數無明顯斜率(如 <50)→ 停 launchd,pipeline 留檔不刪
- **人工投入上限:** 每天 ≤5 分鐘(挑文 + 貼上);超過即檢討流程
