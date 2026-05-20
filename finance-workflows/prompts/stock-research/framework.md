# 個股深度研究框架(adapted from Anthropic market-researcher,for free MCP)

對每一檔個股,**逐層完成**以下分析。**寧可漏掉某層也不要亂填** —— faithfulness.md 是上位規則。

## 1. 公司概覽
- 主業務、營收結構(若 IR 頁可抓到)、規模、上市地點。
- 來源:`web_extract_article(url=<source.url>)`(該股 IR 頁)+ `get_stock_info(ticker)` 的 longBusinessSummary 欄位。
- 不亂編公司歷史 / 故事性敘事。

## 2. 產品 / 業務分析
- 主要產品線、近期推出的新產品、用戶 / 客戶結構(若有提及)。
- 來源:IR 頁 + 近期新聞(可用 `web_fetch` 抓公司新聞稿或新聞網站搜尋結果)。
- 嚴禁猜「市場份額多少」這類沒被引用的數字。

## 3. 行業地位 + 競爭格局
- 所屬產業 / sector / industry(`get_stock_info` 有這兩個欄位)。
- 主要競爭對手(從 IR 提及或公開知識):用「業界常被並列比較的對手」描述,不要編造份額排名。
- 客觀比較:**只列觀察事實**(eg. NVDA 在 AI 訓練 GPU 是事實上的領先;不要寫「NVDA 一定贏」這種斷言)。

## 4. 財務快照(Yahoo `get_stock_info`)
逐項列出(只列實際抓到的數字,缺漏標 N/A):
- 市值(marketCap)、目前股價(currentPrice)、52 週區間(fiftyTwoWeekHigh/Low)
- 估值:PE(trailingPE / forwardPE)、PB(priceToBook)、PEG(pegRatio)
- 獲利能力:profitMargins、operatingMargins、ROE(returnOnEquity)、ROA(returnOnAssets)
- 成長:revenueGrowth、earningsGrowth、earningsQuarterlyGrowth
- 資本結構:debtToEquity、totalCash、totalDebt、freeCashflow
- 股利:dividendYield、payoutRatio(若有)

## 5. 估值簡評(誠實邊界)
- **不做 DCF**(沒有 FactSet 級資料,DCF 假設輸入就會在「胡編」邊緣)。
- 改做 **相對估值**:把這檔的 PE / PEG / PB 跟它的 **sector 平均 / 主要競爭對手** 比對,標「相對偏貴 / 中性 / 相對便宜」+ 一句話理由。
- 標明「以上比較僅基於 Yahoo 抓到的點數據,未做正規化或歷史百分位分析」這種誠實邊界。

## 6. 風險
- **業務風險**(產業循環、單一客戶集中、技術替代…只列該股 IR / 新聞實際提及或近期市場討論的)。
- **法規 / 地緣風險**(若該股有明確暴露,例如中國市場依賴、美國出口管制)。
- **總經連動**(對利率敏感度、對 USD 強弱敏感度、對景氣循環敏感度);這層接 `fred_get_series` 抓 DGS10 / T10Y2Y 當下水位,做「目前總經環境對這檔的方向性」一句話判斷。

## 7. 投資邏輯 + 觀察重點
- **多 / 空 / 中性**三選一(中性也是答案,不要為了給結論硬偏)。
- 信心 0-10(對個股,不是對市場)。
- 3-5 條接下來要 watch 的具體事件 / 數字(eg. 「下次財報是 X 月 X 日」、「若 PE 上 35 視為過熱」、「若主要客戶有大型轉單新聞」)。
- 隔週 / 隔月觀察重點(不是 day-trade 訊號)。

---

**整體層**(所有個股研究完後,寫在報告最後):
- **整體市場 view**(偏多 / 中性 / 偏空 + 信心):橫看 watchlist 大家共同的 sector exposure、目前的總經 / rates 環境、整體估值水位。
- **本次最該注意的 1-2 件事**(跨個股的 common thread)。
