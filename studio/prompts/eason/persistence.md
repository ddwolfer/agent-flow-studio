# SQLite 持久化指令

完成分析後，**必須依序執行以下兩筆 SQLite 寫入**（缺一不可）。

---

## Phase 1 寫入：eason_training（影片訓練樣本）

在取得並分析 Eason 最新影片後，立即用 `mcp__sqlite__create_record` 寫入 `eason_training` 表：

```
table: eason_training
fields:
  video_id          ← ytdlp 回傳的影片 ID（如已存在則跳過）
  video_date        ← 影片發布日期 YYYY-MM-DD
  video_title       ← 影片標題
  video_url         ← 影片完整 URL
  month_batch       ← 發布月份 YYYY-MM（例：2026-05）
  stance            ← 看多 / 看空 / 中性 / 謹慎看多
  stance_score      ← 整數 -5 ~ +5
  indicators_mentioned ← JSON array，例：["季線","外資淨空單"]
  sectors_mentioned    ← JSON array，例：["散熱","CPO"]
  stocks_mentioned     ← JSON array，例：["2330","MU"]
  logic_chain          ← 結構化 JSON 或文字，5 層推理摘要
  predictions          ← JSON array，Eason 的預測
  action_advice        ← 操作建議（文字）
  risk_warnings        ← 風險警示（文字）
  tone_intensity       ← 語氣強度 1~10
  transcript_summary   ← 逐字稿摘要（文字）
```

**去重規則**：先用 `mcp__sqlite__query` 執行
`SELECT id FROM eason_training WHERE video_id = ?`
若已有紀錄則跳過，不重複寫入。

---

## Phase 6 寫入：eason_daily（每日觀點存檔）

報告所有段落完成後，用 `mcp__sqlite__create_record` 寫入 `eason_daily` 表：

```
table: eason_daily
fields:
  date              ← 報告日期 YYYY-MM-DD（即 ${DATE}）
  pillar_seasonal   ← 四大支柱：季節性觀點（文字）
  pillar_chip       ← 四大支柱：籌碼面觀點（文字）
  pillar_micron     ← 四大支柱：個股微觀觀點（文字）
  pillar_otc        ← 四大支柱：OTC/中小型觀點（文字）
  overall_signal    ← BULLISH / NEUTRAL / BEARISH
  confidence        ← 信心評分 0.0~10.0
  bias_flags        ← JSON array，偵測到的偏誤，例：["home_bias","confirmation_bias"]
  key_levels        ← JSON，關鍵價位，例：{"季線":19800,"MU月線":95}
  eason_latest_view ← Eason 今日觀點完整段落（引用逐字稿，非腦補）
  report            ← 完整 HTML 報告內容（optional，可省略以節省空間）
```

---

## 重要規則

1. **兩筆都要寫**：`eason_training`（影片樣本）+ `eason_daily`（今日觀點）是不同表，互不取代。
2. **使用 MCP 工具**：`mcp__sqlite__create_record` 寫入，`mcp__sqlite__query` 查詢去重。
3. **失敗不中斷報告**：若 SQLite 寫入失敗，記錄錯誤訊息並繼續，不要中斷整個分析流程。
4. **逐字稿不可用時**：`transcript_summary` 填 "逐字稿不可用"，其餘欄位填根據數據推估的值。
