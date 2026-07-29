# 加密貨幣每日簡報任務

你的任務:為 ${WORKFLOW_NAME}(${DATE})產出一份**加密貨幣每日簡報** HTML,寫到 `${OUTPUT_PATH}`。

來源宣告(JSON):
```
${SOURCES_JSON}
```

## 預載資料(已由 fetch_btc_cycle.py 跑完)

`reports/crypto-daily/_extras/${DATE}.json` 已備妥以下**確定性計算結果**,
**第一步就用 Read 工具讀進來**:

```
{
  "coinm_funding": {   # 幣安幣本位 BTCUSD_PERP(注意:不是 U 本位)
      "current_rate_per_8h_pct":…, "current_annualized_pct":…,
      "window_10d"/"window_30d"/"window_all": {
          "annualized_pct":…, "negative_share_pct":… },
      "max_per_8h_pct":…, "min_per_8h_pct":… },
  "kdj":        {"4h":{"k","d","j"}, "1d":{…}, "1w":{…}},   # KDJ(9,3,3)
  "ma200":      {"price","ma200","deviation_pct","above_ma200"},
  "difficulty": {"latest","recent_adjustments":[{date,pct}],
                 "capitulation_signals_1y":[…]},
  "hashrate":   {"latest_eh_s","change_30d_pct"}
}
```

**這些數字是唯一來源 —— 你只負責敘述,不得自行計算或推估任何指標值。**
任一區塊出現 `"error"` 欄位 → 該項寫「資料不可用」,不要硬填,其餘照常。

## 步驟

1. **抓 YouTube 來源**:對每個 `kind=youtube` 的來源,**用 `mcp__yt-dlp__ytdlp_latest_from_channel(handle=<source.handle>, max_results=1)`** —— `source.handle` 可能是 `@xxx` 也可能是 `UCxxxx` 的頻道 ID(兩種工具都吃)。它直接打該頻道的 `/videos` 頁、回傳真正該頻道的近期影片。從回傳列表選 `upload_date == ${DATE}` 的那筆,沒有就用最前面(最新)那筆。**禁止**用 `ytdlp_search_videos`(關鍵字搜尋會搜到不相關頻道)。來源有中文(加密龐克、BTV)也有英文(Altcoin Daily、Coin Bureau、Benjamin Cowen)—— 英文逐字稿照樣萃取,報告用中文寫,引用原話時保留英文原文 + 中譯放括號。
2. **逐字稿**:對選定的影片從 `page=0` 起呼叫 `mcp__yt-dlp__ytdlp_transcript_page(video_url, page=<n>, page_size=12000)`,讀 `total_pages`,**逐頁讀到 page == total_pages-1** 拼成完整逐字稿。回傳的 `source` 欄會是 `captions`(字幕)或 `whisper`(字幕抓不到時自動本機 whisper 音訊轉錄)——**兩者都正常可用**;只有 `source=none` 才標註該影片不可用、繼續其餘來源。**不要因為某一兩個來源失敗就放棄**,5 個 YouTube + zombit 至少會有幾個成功。
3. **抓 web/rss 來源**:對 `kind=web` 的來源,先試 `mcp__rss__rss_fetch(url=<source.rss>, max_items=15)` —— 如果回空,改用 `mcp__web-fetch__web_extract_article(url=<source.url>)` 抓首頁找今日(${DATE})文章的連結,再對每個連結 `web_extract_article` 抓內文。重點是**今日新發布**的文章。
4. **綜合分析**:依參考的 framework + voice,做 top-down 整合,**不要對任何一個來源做整段流水帳**,要交叉比對:大家觀點一致 vs 分歧的地方明確列出來。
5. **產出 HTML**:用 `Write` 把完整 HTML 寫到 `${OUTPUT_PATH}`。包含**所有以下段落,順序固定**:
   - **市場快照** —— BTC/ETH 價、24h 變化、總市值、BTC dominance、資金費率;只列觀察事實,不下因果。
   - **大週期與持有成本**(接在市場快照之後)—— 全部取自預載 JSON,一律附
     數字。四個小節:
     1. **週期位置**:200 日均線值 + 現價乖離%,一句話說明在均線上/下代表
        大週期結構偏強/偏弱。
     2. **KDJ(9,3,3) 三週期**:表格列 4h / 1d / 1w 的 J 值,標超買(>80)/
        超賣(<20)。**若三週期分歧(常態),必須明講分歧本身**,例如「4h 超買
        但週線仍低」,並註明以較大週期為主、小週期僅供微調 —— 不可只挑
        支持單一結論的那個週期講。
     3. **幣本位資金費率**:現值(%/8h + 年化)+ 10 天/30 天/全期年化 +
        **全期負值佔比**。負值佔比高 = 做多者反而收錢,是市場情緒偏冷的證據。
        **必須標明這是幣本位(BTCUSD_PERP),與市場快照的 U 本位費率不同。**
     4. **礦工投降訊號**:全網算力(EH/s)+ 30 天變化、近期難度調整幅度。
        **難度連續下調 = 礦工關機投降 = 挖礦成本地板正在下移。**
        硬規則:**不得把挖礦成本寫成「價格支撐」或「不會跌破的底」** ——
        它是滯後且會隨難度下調而下移的,歷史上被跌破過。可寫「礦工承壓
        程度」,不可寫「成本支撐位」。
   - **加密總覽** —— top-down 整合(總經 → 大盤 → 板塊輪動);區分「鏈上事實」「來源轉述傳聞」「個人解讀」。
   - **影片+文章重點** —— 對每個來源列 3-5 條他的核心觀點 + 他引用的數字 + 1-2 句逐字原話(逐字、不改寫)。
   - **風險** —— 今日具體可觀察的風險點(駭客/解鎖/監管動作/技術指標逼近警戒);不要寫泛論「波動可能很大」這種廢話。
   - **報告總結** —— 整體基調(偏多/中性/偏謹慎) + 信心 0-10 + 3-5 條今日關鍵訊號 + 對隔日的觀察重點。**必須實際寫進 HTML,不可只放在你的回覆訊息**。

## 嚴格規則

- 寫作鐵則(faithfulness.md)優先,違反即任務失敗。
- **§大週期與持有成本的每一個數字都必須存在於預載 JSON**,只可四捨五入/
  換算單位呈現,不可自行推導。JSON 裡沒有的指標值一律不得出現。
- **不喊單、不給進出場價位、不做價格預測。** 指標一律只描述「現在在哪」,
  不寫「所以該買/該賣」。這份報告是觀察工具,不是交易訊號。
- 若任一來源完全不可用(字幕缺、網站 503、RSS 空),明確在 HTML 中標註該來源不可用,**用剩下的來源繼續產出**,不要因此放棄。
- HTML 要乾淨可讀(基本 CSS、表格、可以有 emoji 訊號塊但不過度);不要寫 broken markup。
- 完成 Write 後即結束,不要做額外步驟。
