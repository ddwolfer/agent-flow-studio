# Morning Briefing — orchestration

你的任務:為 ${WORKFLOW_NAME}(${DATE},Asia/Taipei)產出今日 cross-asset
**盤前簡報**,寫到 `${OUTPUT_PATH}`。

## 輸出路徑(絕對)

- HTML 報告:`${OUTPUT_PATH}`
- Telegram brief:同目錄,檔名 `_brief.md`(用 Write 工具寫,raw Markdown
  就是 Telegram 訊息內容,**上限 3900 chars**)
- (history.jsonl 由 runner 自動產出,你不需要寫)

目錄你可以心算:`${OUTPUT_PATH}` 拿掉 `<date>.html` 尾巴就是。

## 預載資料(已由 fetch_extras.py 跑完)

`reports/morning-briefing/_extras/${DATE}.json` 已經有以下資料,**用 Read 工具讀進來**:

```
{
  "binance_funding": {"BTC": {...}, "ETH": {...}},
  "binance_oi":      {"BTC": {...}, "ETH": {...}},
  "cboe_vix":        {"VIX": {...}, "VIX9D": {...}, "VIX3M": {...}},
  "treasury_auctions": {"auctions": [...]},
  "stablecoins":     {"stablecoins": [...], "usdt_usdc_combined_delta_24h": ...},
  "twse_three_investors": {"as_of_date": "YYYYMMDD", "unit": "TWD 億",
                           "foreign_net_billion_twd": ..., "invtrust_...": ...,
                           "prop_dealer_...": ..., "total_net_billion_twd": ...}
}
```

每個區塊內若有 `"error"` 欄位,代表該源今天不可用,**該區塊改寫「資料不可用」
不要硬填**。

## 來源宣告(JSON)

```
${SOURCES_JSON}
```

## 步驟

### 1. 讀 extras JSON

用 `Read` 工具讀 `reports/morning-briefing/_extras/${DATE}.json`,記下:
- BTC + ETH funding 年化、24h avg、z-score(用 4 個 sample 算 std 是不夠的,
  改用 `latest_annualised - avg_annualised` 除以一個保守常數 0.05 當粗略 z 即可,
  或直接 surface annualised 數字本身,讓讀者看數字大小判斷)
- VIX、VIX9D、VIX3M 收盤;算 **VIX9D / VIX** 比值(< 1.00 = backwardation 🚨)
- Treasury auctions 篩出 7 天內的,排前 5 條
- Stablecoin USDT+USDC 24h Δ(正值 = 鑄發/印新錢進場,負值 = 贖回/退場)

### 2. 抓 cross-asset 即時資訊

對下列每個 ticker 呼叫 `mcp__yahoo-finance__get_stock_info(symbol=<ticker>)`,
取最新 regularMarketPrice / regularMarketChangePercent / fiftyTwoWeekHigh /
fiftyTwoWeekLow 等。歷史 5d / 60d 算 1W Δ 與 1y percentile,呼叫
`mcp__yahoo-finance__get_historical_stock_prices(symbol=<ticker>, start_date=<60d 前>, end_date=${DATE})`。

| 類別 | Ticker |
|---|---|
| US 期指夜盤 | `ES=F`, `NQ=F` |
| US 公債(yfin 版) | `^TNX`(10y), `^FVX`(5y), `^IRX`(13w) |
| 匯率 | `DX-Y.NYB`(DXY), `TWD=X`(USDTWD) |
| 商品 | `CL=F`(WTI), `GC=F`(Gold) |
| 波動度(yfin 版作交叉驗證) | `^VIX` |
| 加密 | `BTC-USD`, `ETH-USD` |
| 台股代理 | `TSM`(ADR), `2330.TW`(本土) |
| ETF flow proxy | `IBIT`, `FBTC` — 取昨日 close + volume(僅作 reference,不算 flow $) |

### 3. 抓 FRED 利率序列

呼叫 `mcp__fred__fred_get_series(series_id=<id>, observation_start=<約 60d 前>, observation_end=${DATE})`:
- `DGS2`(2y)、`DGS10`(10y)、`T10Y2Y`(2s10s 利差)
- `DFF`(有效聯邦資金利率,當作 Fed funds rate)
- 若 yfin 的 `^TNX` 跟 FRED 的 `DGS10` 不一致,**列出兩個值並標「FRED / Yahoo 版本」**。

### 4. TWSE 三大法人(由 extras JSON 讀)+ 融資(TWSE MCP)

**4a. 三大法人**:由 `fetch_extras.py` 已預先抓好,直接從 step 1 讀入的
`twse_three_investors` 讀數字,**不要**呼叫 twse MCP。欄位:

```
twse_three_investors = {
  "as_of_date": "YYYYMMDD",
  "unit": "TWD 億",
  "foreign_net_billion_twd":            <外資及陸資淨買超,億元>,
  "invtrust_net_billion_twd":           <投信淨買超>,
  "prop_dealer_self_net_billion_twd":   <自營商自行買賣>,
  "prop_dealer_hedge_net_billion_twd":  <自營商避險>,
  "prop_dealer_combined_net_billion_twd": <自營商合計 = self + hedge>,
  "total_net_billion_twd":              <三大法人合計>
}
```

正值 = 淨買超,負值 = 淨賣超。TW open 段位一律用 `外資 X 億 / 投信 Y 億 /
自營 Z 億(合計 T 億)` 的格式,一位小數。若該區塊有 `"error"` 欄位,標
「三大法人:資料不可用」不要編。

**4b. 融資餘額**:改用 TWSE MCP,需計算「**上一交易日**」的資料。規則:
- 週一/國定假日隔天:回推到上週五(或最近非週末非假日)
- 一般工作日:取 `today - 1`

實作:先呼叫 `mcp__twse__get_daily_market_trading_info(date=<today - 1>)`,
若回空或錯,依序試 `today - 2` / `today - 3`;第一個非空的日期記為
`<TWSE_DATE>`,融資餘額呼叫也用同一個。

呼叫 `mcp__twse__get_margin_trading_info(date=<TWSE_DATE>)` — 取融資餘額
+ DoD Δ。若回空,標「融資餘額:資料不可用」,繼續寫其他段。

**注意**:`mcp__twse__get_foreign_investment_by_industry` 給的是「產業別外資
持股 %」,**不是**每日三大法人買賣超金額 — 別呼叫它。三大法人已由 extras
JSON 提供,見 4a。

### 4c. 讀昨日新聞聚合(news digest)

用 `Read` 讀 `reports/morning-briefing/_news/${DATE}.json`(由 `fetch_news_digest.py`
在 shell driver 預先產出)。結構:

```
{
  "window_start": iso,           # 上一次 morning-briefing 執行時點(≈昨日 08:00 TPE)
  "window_end":   iso,           # 本次執行時點(≈今日 07:00 TPE)
  "counts":       { feed: n, ... },
  "items": [
    { "ts": iso, "feed": name, "title": str, "url": str, "summary": str },
    ...  # 已由腳本按 URL/標題兩層去重,新→舊排序
  ]
}
```

**這個檔案是 §Five things 的主要素材來源**。腳本已做確定性去重,你的任務是
在其上做:

1. **分群**(不要按 feed,按主題):美股/總經 · 亞洲/台股 · 加密/商品 · 政治/監理
2. **重要性排序** — 影響大盤 > 影響單一大型股 > 個股利好利空。同一事件多源覆蓋
   時代表市場關注度高,優先入選。
3. **選 5 條**填 §Five things。每條寫 2-3 句:先事實,再「為什麼今天對台股/夜盤重要」。
4. **來源標註** — 每條末尾加 `(feed_name)`,例:`(bloomberg)`、`(cnbc)`。若跨兩家以上,寫 `(bloomberg + cnbc)`。
5. **與 tape 訊號共振** — 若某條新聞正好解釋一個 tape 異常(例:BTC funding
   衝高有一條 ETF 通過新聞、VIX backwardation 對應地緣事件),主動連起來,
   放在 §Editor's take 或 §Five things 的第 1 條位置。

**不要做的**:
- 不要把腳本挑出的 headline 逐字抄成 5 條(那沒有增值)。你的價值在「為什麼重要」。
- 一則消息若只有 investing.com 單源、且明顯是轉述,可以忽略(投機新聞優先度低)。
- 標題若含「rumour / sources say / could / may」而未有第二方證實,措辭必用「傳」「據報」「未證實」。
- 若 `_news/${DATE}.json` 不存在或 items 為空,§Five things 改標「昨日新聞:
  聚合來源全部不可用」並用你能從 tape 訊號推得的 5 條要點填補,不要中止報告。

### 5. (best-effort)Fed 新聞稿

呼叫 `mcp__rss__rss_fetch(url="https://www.federalreserve.gov/feeds/press_all.xml", max_items=10)`,
看最近 24-48 小時內有沒有 FOMC statement / Fed speaker 預告 / interest rate 相關
release。RSS 每一 item 有 `{title, link, published, summary}`;`published` 是
`YYYY-MM-DD` 形式。挑 published 在 `${DATE} - 2 天`到 `${DATE}`之間的 items,
每條寫一行 `<title>(published)`。

若回 `[]` 或最近 48h 內無相關項目,標「Fed 新聞稿 24-48h 內無新項目」,不要
瞎編。**禁止**再多抓 article 內文細節(深度分析交給 us-macro 那支)。

### 6. 計算 emoji flag 三條件

明確檢查並標記:
- 🚨 `cboe_vix.VIX9D.latest_close / cboe_vix.VIX.latest_close < 1.00`
- ⚡ `BTC funding annualised` 顯著偏離(粗估 > 30% 年化偏多,或 < -10% 偏空)
- 🎯 TSM ADR premium = `TSM_close × USDTWD ÷ 2330.TW_close - 1`,
  與過去 1y 百分位比較,**> 0.95 percentile or < 0.05 percentile** 才標

其他段落保持中性,不加 emoji。

### 7. 寫 HTML 到 `${OUTPUT_PATH}`

用 `Write` 工具。HTML 包含 7 個固定 section(順序、標題照 framework.md):

1. Mood line(一句話)
2. Tape snapshot(表格)
3. Five things(numbered list,每條 2-3 句)
4. Today's calendar(表格)
5. TW open hint(bullet)
6. Editor's take(1-2 句)
7. 附註(資料源 + 編譯時間)

**HTML 設計鐵則**:
- 單檔內嵌 CSS,**max-width 720px**,A4 一頁印得完
- 字體用 system fonts(`-apple-system, "PingFang TC", "Noto Sans TC"`)
- 表格邊框輕巧,行距 1.5,標題粗體但不誇張
- emoji flag 用 inline 不要做成獨立色塊
- **不要**寫圖表(沒有 chart library 可用)
- print CSS(`@media print`)隱藏不必要的 padding

### 8. 寫 `_brief.md`(Telegram body)

用 `Write` 工具,**Markdown 語法(注意是 Telegram Markdown, 不是 MarkdownV2)**:

```
📰 *Morning Briefing* — `${DATE}`

> <mood line>

*Tape snapshot*
• ES <last> <1d>
• UST 2y/10y/2s10s <levels> <bp Δ>
• DXY/USDTWD <levels>
• VIX/VIX9D/VIX9D:VIX <vals> <🚨 if backwardation>
• BTC/ETH <prices> <1d>
• BTC funding 年化 <X>% <⚡ if extreme>
• TSM ADR premium <X>% <pct rank> <🎯 if extreme>

*Five things*
1. <事件 + 時間>
   <why it matters 1 句>
2. ...
...
5. ...

*TPE 行事曆*
• <time> <event> (cons <c> / prior <p>)
...

*TW open*
• 三大法人 <net buy>
• 融資 <DoD>
• TSM ADR premium <X>% → 2330 開盤理論價 <Y>
• TWD <Δ>

*Editor's take*
<1-2 句>
```

**上限 3900 chars**(Telegram sendMessage 4096 - 一點 buffer)。
如果你寫超過,壓掉表格細節,保留標題 + flag,把長文搬到 HTML。

### 9. 寫完即結束

不要多做任何步驟。runner 會自動跑 history extract + Telegram 推送 + PDF 生成。

## 嚴格規則

- 寫作鐵則(faithfulness.md)優先,違反即任務失敗。
- 個股買賣建議**禁止**(TSMC 也一樣,只能寫「開盤偏多 / 偏空」hint)。
- 不對未來價格做斷言;條件式語言。
- emoji flag 只有那 3 條,**不可亂用**。
- 任何來源失敗,該欄位標「資料不可用」,**不要中止整份報告**。
- 報告完成 Write 後即結束。
