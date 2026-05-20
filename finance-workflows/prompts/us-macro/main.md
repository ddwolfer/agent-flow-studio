# 美國總經每日簡報任務

你的任務：為 ${WORKFLOW_NAME}（${DATE}）產出一份**美國總經每日簡報** HTML，寫到 `${OUTPUT_PATH}`。

來源宣告（JSON）：
```
${SOURCES_JSON}
```

## 步驟

1. **抓 FRED 總經序列**：對下列每一條序列呼叫 `mcp__fred__fred_get_series(series_id=<id>, observation_start=<約 ${DATE} 往前 24 個月>, observation_end=${DATE})`，取最新 1-3 個觀測值，並計算與前期、與一年前的變化。**最少要拉這些**：
   - 政策利率：`DFF`（有效聯邦資金利率）
   - 殖利率：`DGS2`（2 年期）、`DGS10`（10 年期）、`T10Y2Y`（10y-2y 利差）
   - 通膨：`CPIAUCSL`（CPI 全部項目）、`PCEPI`（PCE 物價指數）
   - 勞動：`UNRATE`（失業率）、`PAYEMS`（非農就業）

   若某序列回傳空 / 失敗，在報告中標註「該序列今日不可用」，繼續其他序列。

2. **抓 Yahoo 指數／匯率／VIX**：對下列每一個 ticker，先呼叫 `mcp__yahoo-finance__get_stock_info(symbol=<ticker>)` 取即時／近期資訊，必要時用 `mcp__yahoo-finance__get_historical_stock_prices(symbol=<ticker>, start_date=<約 ${DATE} 往前 60 天>, end_date=${DATE})` 取歷史以計算短中期均線與位階：
   - 美股大盤：`^GSPC`、`^DJI`、`^IXIC`
   - 波動度：`^VIX`
   - 美元指數：`DX-Y.NYB`
   - 10 年期殖利率（市場版本，與 FRED 互為交叉驗證）：`^TNX`

3. **抓 Fed 新聞稿 / FOMC 聲明**（best-effort）：呼叫 `mcp__web-fetch__web_extract_article(url="https://www.federalreserve.gov/newsevents/pressreleases.htm")` 抓 Federal Reserve 最近的新聞稿列表頁；從回傳內容找最近 7 天的 FOMC statement / monetary policy 相關連結，再對該連結呼叫 `mcp__web-fetch__web_extract_article(url=<連結>)` 取全文。若列表頁無相關項目，於報告中標註「本週無新聲明」，繼續往下。

4. **綜合分析**：依參考的 framework + voice，做 top-down 整合。**禁止**對任何單一資料來源做流水帳；要交叉比對 FRED 序列、Yahoo 收盤、Fed 聲明措辭三方是否一致。一致就強化訊號，分歧就明確列出背離。

5. **產出 HTML**：用 `Write` 工具把完整 HTML 寫到 `${OUTPUT_PATH}`。包含**所有以下段落，順序固定**：

   - **市場快照** —— 表格形式列出當日（或最近交易日）：`^GSPC`／`^DJI`／`^IXIC` 收盤與日變化%、`^VIX` 收盤、`DX-Y.NYB` 收盤、`DGS2`／`DGS10` 殖利率、`T10Y2Y` 利差。**只列觀察事實，不下因果**。
   - **政策動向** —— Fed funds rate（`DFF`）現值；最近一次 FOMC 聲明的關鍵措辭（逐字引號）；下一次會議市場隱含路徑（若可從 Fed 文件取得，否則標註「本報告未取得即時 fed funds futures 隱含機率」）；Fed 官員近期談話基調。
   - **數據面** —— CPI／PCE 最新月與年增、核心 vs headline；非農（PAYEMS）月變動；失業率（UNRATE）；觀察 trend break。
   - **利率與曲線** —— 2Y／10Y 殖利率水位、T10Y2Y 倒掛狀態（多久了、深度）、實質殖利率（若取得 TIPS）；殖利率曲線當下訊號的市場一般解讀。
   - **風險與資產配置** —— 整體 risk-on／中性／risk-off 判斷；資產類別層級的傾向（股／債／美元／避險）。**絕對禁止個股或個別代號買賣建議**；只能寫類別層級。
   - **報告總結** —— 整體風險基調 + 信心 0-10 + Fed 路徑解讀（再升／按兵不動／轉鴿降息）+ 3-5 條今日關鍵訊號 + 隔日／本週觀察重點。**必須實際 Write 進 HTML，不可只放在你的回覆訊息**。

## 嚴格規則

- 寫作鐵則（faithfulness.md）優先，違反即任務失敗：不編造因果、只引用資料實際出現的數字、不確定就省略。
- Fed 聲明、官員談話的引用必須**逐字加引號**，不可改寫翻譯（可在括號內補中譯）。
- 區分三層：**觀察到的資料**（FRED／Yahoo 數字、Fed 逐字）／**市場一般解讀**／**本報告推論**。
- 若任一資料源完全失敗（FRED 全空、Yahoo 全部 timeout、Fed 站 503），明確在 HTML 中標註該源不可用，**用剩下的源繼續產出**，不要因此放棄。
- 個股／個別代號（含個別 ETF）的買賣建議一律禁止；ETF 作為資產類別代理（如「美元指數 ETF」做為 DXY 觀察工具）可提，但不可下「買 / 賣」建議。
- 不對未來價格做斷言；用機率、條件式語言（「若 X 跌破 Y 則 …」）。
- HTML 要乾淨可讀（基本 CSS、表格清楚、可用顏色／emoji 標示 risk regime 但勿過度）；不要寫 broken markup。
- 完成 Write 後即結束，不要做額外步驟。
