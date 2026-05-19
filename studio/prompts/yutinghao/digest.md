# 逐字稿濃縮任務（前置步驟，務必完成並寫檔）

唯一任務：把游庭皓今日影片的完整逐字稿，濃縮成忠實、結構化的摘要，用 `Write` 寫入：
```
${TRANSCRIPT_DIGEST}
```

## 步驟
1. `mcp__yt-dlp__ytdlp_search_videos(query="{{channel.search_query}}", maxResults=2, uploadDateFilter="today")` 找今日影片；無新片用最近一支。
2. 每支影片從 `page=0` 起呼叫 `mcp__yt-dlp__ytdlp_transcript_page(video_url="<url>", page=<n>, page_size=12000)`，讀 `total_pages`，**逐頁讀到 `page==total_pages-1`**，心中串接完整逐字稿。
3. 依下方 schema 寫入 ${TRANSCRIPT_DIGEST}。

## 摘要 schema（嚴格照寫）
```
# 逐字稿摘要（{{calendar}}）

## 影片清單
- 標題 ｜ video_id ｜ url ｜ 逐字稿來源(captions/gemma4:e4b/none) ｜ 完整字元數

## 游庭皓總體立場
（偏多／中性／偏謹慎 + 1–2 句理由，僅依逐字稿）

## 關鍵總經數據與解讀
- <數據名>：<他引用的數字/變化> → <他的解讀>（逐條，只列他實際講的）

## 風險點
- （他實際提到的總經/市場風險，逐條）

## 資產配置與操作傾向
- （他對資產類別/大盤/類股的傾向；不是個股選股）

## 關鍵原話逐字引用
> 「（從逐字稿原文逐字複製，不可改寫、不可翻譯、不可潤飾）」
（5–10 句）
```

## 忠實度鐵則（違反即失敗）
- 只能萃取逐字稿真實出現的內容；嚴禁臆測、補充、合理推論他沒講的數字或結論。
- 不確定 → 省略。原話必須逐字。
- 即使逐字稿 source=none 或抓不到，**仍要 Write 出檔案**：影片清單標「逐字稿不可用」，其餘節寫「（逐字稿不可用）」。

## 限制
- 本輪只允許 `mcp__yt-dlp__*` 與 `Write`、`Read`。禁止其他工具、禁止產生報告/HTML。完成 Write 即結束。
