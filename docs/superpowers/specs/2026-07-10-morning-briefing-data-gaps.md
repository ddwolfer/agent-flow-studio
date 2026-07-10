# Morning Briefing — 剩餘資料缺口分析(WTI 原因 + ETF flow)

> 版本:分析稿(尚未實作)
> 日期:2026-07-10
> 隸屬:`finance-workflows/morning-briefing` workflow
> 前置:本次已修完的三個「資料不可用」缺口(commit `94fc363` Fed RSS + TWSE date probe;`3ca975f` 三大法人 via pre-script)
> 狀態:兩個議題延後,先分析可行方案供明日決策

---

## 背景

2026-07-09 morning-briefing 報告修完三個「資料不可用」後,仍有兩個軟缺口:

1. **WTI「原因不明」** — Five things #5 寫「WTI 反彈 +1.46% 至 $74.59。原因不明,持續觀察。」
2. **ETF flow gap** — 報告缺 IBIT/FBTC 加密 ETF 淨創/贖 flow;股票 ETF(SPY/QQQ)也僅有 volume proxy

本文件分析兩者的可行方案 + 優先度建議,**不含實作**。

---

## 議題 1:WTI「原因不明」— 本質是 news 源沒接

### 根因

Workflow 只有 tape 資料(價格 + FRED 利率 + VIX + 加密),**完全沒有 news source**。
LLM 看到 WTI +1.46% 想寫 catalyst 但沒東西可引,只好寫「原因不明」。同樣的問題也
會出現在:Gold 大幅波動、BTC 突然抽動、SPX 期指異常。

這不是 WTI 特有問題,而是「tape-only briefing 缺 narrative 源」的通用症狀。

### 方案比較

| 方案 | 來源 | 成本 | 效益 | 風險 |
|---|---|---|---|---|
| **A ⭐** EIA + CNBC commodity RSS | `eia.gov/pressroom/rss.xml` + `cnbc.com/id/23103218/device/rss/rss.html` | 低(RSS,30-45 min) | 高 — EIA 是 oil 原始 catalyst 源頭 | CNBC RSS 需 title 過濾「WTI/oil/OPEC」 |
| B Google News RSS 查詢 | `news.google.com/rss/search?q=WTI+crude+oil` | 超低(零程式碼) | 中 — 覆蓋廣但訊噪比差 | LLM 可能拿內容農場 headline 硬套 |
| C 刪掉「原因分析」子句 | — | 0(改 prompt) | 低但正 — 不再出現空洞句 | 失去部分讀者期待的 catalyst 說明 |
| D 每 asset 配 news lookup | 8 asset × 5 headlines pre-fetch | 高 | 中(brief 篇幅有限用不到) | over-engineering |

### 推薦:A + 少量 B 補充

- **EIA RSS** 是能源市場 authoritative catalyst source。每週三 EIA petroleum status
  report 是 oil 最重要的每週事件,不接就浪費。
- **CNBC commodities RSS** 補市場 color(OPEC 動態、地緣、供需 headline)。
- **Google News RSS(B)** 只在 EIA/CNBC 24h 內都無 hit 時作為次補,避免低品質 headline
  污染。
- 實作:`fetch_extras.py::fetch_commodity_news()`,prompt Five things 段加「若 commodity_news
  有 WTI/oil 相關 item,引用作 catalyst;否則不寫『原因不明』,只陳述漲跌幅」。
- **可延伸性**:同 fetcher 可加 metals RSS(gold)、crypto news RSS(CoinDesk),一次寫多用。

---

## 議題 2:ETF flow gap — 細分兩類,價值不同

### 2a. 加密 ETF flow(IBIT / FBTC / BITB / ...)

**用途:** 追蹤 BTC/ETH 現貨 ETF 每日淨創/贖(institutional flow proxy)。crypto brief
最有價值指標之一。

| 方案 | 來源 | 成本 | 效益 | 風險 |
|---|---|---|---|---|
| **A ⭐** SoSoValue 公開 API | `api.sosovalue.xyz/openapi/v2/etf/currentEtfDataMetrics?type=us-btc-spot` | 低(JSON,30-45 min) | 高 — 涵蓋 IBIT/FBTC/GBTC/BITB/EZBC 全部 US spot BTC ETF daily flow + AUM + premium | 須 curl 驗是否真 keyless;CORS 對 server-fetch 不影響 |
| B CoinGlass API | `open-api.coinglass.com/public/v2/us_bitcoin_etf_flow` | 中(可能需免費 key) | 中 — 覆蓋類似但有限流 | SoSoValue 不通再考慮 |
| C iShares 官方 CSV | BlackRock daily flow CSV | 低 | 低 — 只有 iShares 系列,覆蓋不足 | 非首選,可作 A 的 backup |

**推薦:A(SoSoValue)。** 一個 endpoint 覆蓋整條 spot BTC ETF 生態。實作:加
`fetch_extras.py::fetch_crypto_etf_flow()`,~30-45 min。**第一步必須先 curl 驗 keyless。**

### 2b. 股票 ETF flow(SPY / QQQ / VOO / IVV)

**用途:** 大盤 ETF 資金淨流入/流出 — sentiment(risk-on/off)proxy。

| 方案 | 來源 | 成本 | 效益 | 建議 |
|---|---|---|---|---|
| A State Street SPDR 官方 | SSGA 頁面需 JS render + session | 高(scrape) | 中 | ❌ 不做 |
| B Yahoo `totalAssets` DoD Δ | 已在用 | 0 | 低 — 混合 NAV 變動 + flow,無法純化 | 現況即此,精度就這樣 |
| C ETF.com daily flows | HTML scraping,格式常變 | 高 | 中 | ❌ 不做 |
| **D ⭐** 接受缺口 | — | 0(prompt 注釋) | — | ✅ 承認 daily flow 對 pre-market brief 訊號量低 |

**推薦:D(接受限制)。** 股票 ETF 的 daily flow 對 morning brief 邊際效用低(週報級別
才有意義),加抓成本 vs 訊號 ROI 不划算。prompt 明講「IBIT/FBTC 已提供實際 flow $;
SPY/QQQ 僅提供 volume 作為 proxy」即可。

---

## 綜合優先度建議

| 項目 | 成本 | 效益 | 建議 |
|---|---|---|---|
| **1A** WTI 用 EIA + CNBC RSS | 30-45 min | 高(修根本原因,可延伸多資產) | ✅ 優先 |
| **2a-A** 加密 ETF flow via SoSoValue | 30-45 min | 高(crypto brief 核心指標) | ✅ 優先 |
| 2b 股票 ETF flow | 高 | 低 | ❌ 不做(接受 gap) |
| 1B Google News RSS 補位 | 15 min | 低-中 | 🟡 可選,先 1A 之後看 |
| 1D 每 asset 配 news | 高 | 中 | ❌ over-engineering |

### 打包建議

**1A + 2a-A 一起做**(合起來 ~1 hr):都是 `fetch_extras.py` 加新 fetcher + prompt 加
新段位,pattern 完全一致(與已完成的 Binance/CBOE/Treasury/DefiLlama/TWSE 三大法人
相同)。同一個 slice、同一個 commit,cost 只多一點但收益疊加(WTI 原因 + crypto ETF
flow 兩個空白都補)。

### 實作前置檢查(共同)

1. **先 curl 驗 endpoint**:SoSoValue 是否真 keyless、EIA/CNBC RSS 是否可 `rss_fetch` —
   不驗就寫代碼是白費(參照本次 TWSE 修法的經驗:先 curl 拿到 2026-07-09 資料才動手)。
2. **遵守既有 pattern**:新 fetcher 的 signature 與 error 處理跟 `fetch_binance_funding` /
   `fetch_twse_three_investors` 一致,`{"error": "..."}` 隔離失敗。
3. **加 test**:monkeypatch httpx + 對真實 response body 做 happy-path assert +
   never-raises assert(參照 `test_fetch_extras.py`)。
4. **不動 runner、不動 MCP**:純 pre-script + prompt。

---

## 相關 KG 節點

- `web_extract_article fails on listing pages — use RSS or raw fetch instead`(本次 Fed RSS 修法)
- `TWSE public JSON endpoints — keyless, structured, ready for pre-script`(本次三大法人修法,可作新 fetcher 模板)
- `morning-briefing extras: 5 keyless data sources + ETF-flow gap`(原始 gap 紀錄)
