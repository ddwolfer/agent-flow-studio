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
  "stablecoins":     {"stablecoins": [...], "usdt_usdc_combined_delta_24h": ...}
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

### 4. 抓 TWSE 三大法人 + 融資

**日期參數計算**:報告在 07:00 TPE 跑,呼叫時要取「**上一交易日**」的資料,不是
「昨日 (`today - 1`)」。規則:
- 週一/國定假日隔天:回推到上週五(或最近一個非週末非假日)
- 一般工作日(週二~週五):取 `today - 1`
- 台股國定假日表沒維護時,若第一次呼叫回空,自動 fallback 再往前推 1 天(最多 3 天)

實作:先呼叫 `mcp__twse__get_daily_market_trading_info(date=<today - 1>)`,
若回空或錯,依序試 `today - 2` / `today - 3`;第一個非空的日期記為 `<TWSE_DATE>`,
以下所有 TWSE 呼叫都用同一個 `<TWSE_DATE>`。

呼叫:
- `mcp__twse__get_foreign_investment_by_industry(date=<TWSE_DATE>)` — 注意:此
  endpoint 給的是「產業別外資持股 %」(MI_QFIIS_cat),**不是**每日三大法人買賣超
  金額。TWSE Open API 沒有公開的「三大法人日買賣超」endpoint。若本欄需求為
  「三大法人淨買超」而此 endpoint 不足以呈現,直接標「TWSE Open API 未提供
  此資料」,不要硬用產業持股 % 代替。
- `mcp__twse__get_margin_trading_info(date=<TWSE_DATE>)` — 取融資餘額 + DoD Δ

若某 endpoint 回空,**標「TWSE 該源今日不可用」**,繼續寫其他段。

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
