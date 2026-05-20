# 加密貨幣每日簡報任務

你的任務:為 ${WORKFLOW_NAME}(${DATE})產出一份**加密貨幣每日簡報** HTML,寫到 `${OUTPUT_PATH}`。

來源宣告(JSON):
```
${SOURCES_JSON}
```

## 步驟

1. **抓 YouTube 來源**:對每個 `kind=youtube` 的來源,用 `mcp__yt-dlp__ytdlp_search_videos(query=<source.search_query>, maxResults=2)` 找今日(或最近一支)影片;選 `upload_date == ${DATE}` 的那筆,沒有就用日期最新那筆。
2. **逐字稿**:對選定的影片從 `page=0` 起呼叫 `mcp__yt-dlp__ytdlp_transcript_page(video_url, page=<n>, page_size=12000)`,讀 `total_pages`,**逐頁讀到 page == total_pages-1** 拼成完整逐字稿。若 source 是 `none`(無字幕)就在報告中標註該影片不可用、繼續其餘來源。
3. **抓 web/rss 來源**:對 `kind=web` 的來源,先試 `mcp__rss__rss_fetch(url=<source.rss>, max_items=15)` —— 如果回空,改用 `mcp__web-fetch__web_extract_article(url=<source.url>)` 抓首頁找今日(${DATE})文章的連結,再對每個連結 `web_extract_article` 抓內文。重點是**今日新發布**的文章。
4. **綜合分析**:依參考的 framework + voice,做 top-down 整合,**不要對任何一個來源做整段流水帳**,要交叉比對:大家觀點一致 vs 分歧的地方明確列出來。
5. **產出 HTML**:用 `Write` 把完整 HTML 寫到 `${OUTPUT_PATH}`。包含**所有以下段落,順序固定**:
   - **市場快照** —— BTC/ETH 價、24h 變化、總市值、BTC dominance、資金費率;只列觀察事實,不下因果。
   - **加密總覽** —— top-down 整合(總經 → 大盤 → 板塊輪動);區分「鏈上事實」「來源轉述傳聞」「個人解讀」。
   - **影片+文章重點** —— 對每個來源列 3-5 條他的核心觀點 + 他引用的數字 + 1-2 句逐字原話(逐字、不改寫)。
   - **風險** —— 今日具體可觀察的風險點(駭客/解鎖/監管動作/技術指標逼近警戒);不要寫泛論「波動可能很大」這種廢話。
   - **報告總結** —— 整體基調(偏多/中性/偏謹慎) + 信心 0-10 + 3-5 條今日關鍵訊號 + 對隔日的觀察重點。**必須實際寫進 HTML,不可只放在你的回覆訊息**。

## 嚴格規則

- 寫作鐵則(faithfulness.md)優先,違反即任務失敗。
- 若任一來源完全不可用(字幕缺、網站 503、RSS 空),明確在 HTML 中標註該來源不可用,**用剩下的來源繼續產出**,不要因此放棄。
- HTML 要乾淨可讀(基本 CSS、表格、可以有 emoji 訊號塊但不過度);不要寫 broken markup。
- 完成 Write 後即結束,不要做額外步驟。
