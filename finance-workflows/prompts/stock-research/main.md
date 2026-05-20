# 個股深度研究任務

你的任務:為 ${WORKFLOW_NAME}(${DATE})對 watchlist 中的每一檔個股產出一份**深度研究** HTML,寫到 `${OUTPUT_PATH}`。

watchlist(從 `${SOURCES_JSON}` 解析,取所有 `kind="stock"` 的 source,使用 `name` 欄當 ticker、`url` 欄當該股的 IR 頁):
```
${SOURCES_JSON}
```

## 步驟

### 第一階段:總經背景(只做一次)
抓 FRED 當下水位當所有個股研究的總經背景:
- `mcp__fred__fred_get_series(series_id="DGS10")` — 10Y 美債殖利率
- `mcp__fred__fred_get_series(series_id="T10Y2Y")` — 10Y-2Y 利差(衰退預兆)
- `mcp__fred__fred_get_series(series_id="DFF")` — Fed funds rate
- `mcp__fred__fred_get_series(series_id="CPIAUCSL")` — CPI 最新
- 留住這 4 個數據,後面每一檔股票分析「總經連動」那層會用到。

### 第二階段:逐檔深入(每檔依以下流程)
對 watchlist 中**每一檔 ticker**做以下:

A. **Yahoo 抓快照**:`mcp__yahoo-finance__get_stock_info(ticker=<TICKER>)` — 拿到 longBusinessSummary、sector、industry、marketCap、currentPrice、trailingPE / forwardPE / pegRatio / priceToBook、profitMargins / operatingMargins / returnOnEquity、revenueGrowth / earningsGrowth、debtToEquity / freeCashflow、dividendYield、52 週區間。**不要呼叫 `get_historical_stock_prices` 拿全歷史**(資料量大、用不上)—— 只在你需要近期趨勢且 `get_stock_info` 沒給時才用。

B. **公司 IR 頁**:`mcp__web-fetch__web_extract_article(url=<source.url>)` — 抓公司投資人關係頁的近期內容(可能是最新財報摘要、IR presentation 連結、近期事件)。若該頁回不到內容(403 / 403 / 內容空),就標註 IR 頁不可用,繼續。

C. **近期新聞**(可選):若你判斷該股近期(過去 7 天)有具體事件(財報、產品發表、地緣風險),可用 `mcp__web-fetch__web_fetch` 或 `web_extract_article` 抓 Yahoo Finance 該 ticker 的 news 頁面(`https://finance.yahoo.com/quote/<TICKER>/news`)。不確定就跳過,不要編造新聞。

D. **依 framework.md 的 7 層**寫出該股的研究段落:
   1. 公司概覽
   2. 產品 / 業務分析
   3. 行業地位 + 競爭格局
   4. 財務快照(逐項列 Yahoo 數據)
   5. 估值簡評(**相對估值,不做 DCF**;誠實邊界)
   6. 風險(業務 / 法規 / 總經連動 — 總經那層接第一階段抓的 4 個 FRED 數值)
   7. 投資邏輯 + 觀察重點(多 / 中性 / 空 + 信心 0-10 + 3-5 條 watch points)

### 第三階段:整體市場層(所有個股做完後,寫在報告最後)
- 整體市場 view(偏多 / 中性 / 偏空 + 信心),用 framework.md 最後那段的方法。
- 本次最該注意的 1-2 件事(跨個股的 common thread)。

## 產出 HTML 規範

用 `Write` 把完整 HTML 寫到 `${OUTPUT_PATH}`。結構:

```
<h1>個股深度研究 — ${DATE}</h1>
<p class="disclaimer">本報告基於公開免費資料(Yahoo Finance + FRED + 公司 IR),非機構級 due diligence。投資決策請自負風險。</p>

<section id="macro-context">
  <h2>總經背景</h2>
  -- 第一階段的 4 個 FRED 數據,當下水位 + 一句話總結
</section>

<!-- 對 watchlist 每一檔重複以下 section,順序依 watchlist 順序 -->
<section id="ticker-NVDA">
  <h2>NVDA — NVIDIA Corporation</h2>
  <h3>1. 公司概覽</h3>
  ...
  <h3>2. 產品 / 業務分析</h3>
  ...
  <h3>3. 行業地位 + 競爭格局</h3>
  ...
  <h3>4. 財務快照</h3>
  <table>
    <tr><th>指標</th><th>數值</th></tr>
    <tr><td>市值</td><td>...</td></tr>
    ... 全部 framework.md §4 列的指標 ...
  </table>
  <h3>5. 估值簡評</h3>
  ...
  <h3>6. 風險</h3>
  <ul>...</ul>
  <h3>7. 投資邏輯 + 觀察重點</h3>
  <ul>
    <li><strong>方向</strong>:多 / 中性 / 空</li>
    <li><strong>信心</strong>:N/10</li>
    <li><strong>觀察重點</strong>:
      <ul>...</ul>
    </li>
  </ul>
</section>

<section id="overall">
  <h2>整體市場 view</h2>
  ...
</section>
```

## 嚴格規則
- faithfulness.md 鐵則優先,違反即任務失敗。
- 對任一檔股票,若 Yahoo `get_stock_info` 都連不到,在該股的 section 標註「資料不可用,本次跳過」**並繼續其餘股票**,不要因此放棄整份報告。
- HTML 用乾淨的 inline CSS(可以參考表格樣式、深色背景或淺色背景隨你)。不要寫 broken markup。
- 完成 `Write` 後即結束。
