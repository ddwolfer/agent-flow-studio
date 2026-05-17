#!/bin/bash
# Daily Macro x Tactical Briefing - weekdays 9:30am
# Combines: 游庭皓 + Eason + real-time data
# Output: HTML → PDF → Discord(text+PDF) + LINE(text+images)

DATE=$(date +%Y-%m-%d)
REPORT_DIR="/mnt/c/FINANCIAL/reports"
LOG_FILE="${REPORT_DIR}/briefing-${DATE}.log"
HTML_FILE="${REPORT_DIR}/${DATE}_daily-macro-tactical-briefing.html"
PDF_FILE="${REPORT_DIR}/${DATE}_daily-macro-tactical-briefing.pdf"

source /mnt/c/FINANCIAL/scripts/notify.sh
mkdir -p "$REPORT_DIR"

echo "[$(date)] Starting daily macro x tactical briefing..." > "$LOG_FILE"

cd /mnt/c/FINANCIAL
claude -p "請產出今日的「每日總經 × 台股戰情室」綜合報告。步驟如下：

1. 用 yt-dlp MCP 搜尋游庭皓今天早上的最新影片（搜尋 '游庭皓 早晨財經速解讀'，uploadDateFilter='today'，fallback 'week'），下載逐字稿（language zh-TW），萃取他的總經觀點
2. 查詢 SQLite eason_training 表最新一筆資料，取得 Eason 前一天的觀點（不需要重新抓影片）
3. 平行收集即時數據：
   - TWSE：加權指數、主要指數、融資融券
   - Yahoo Finance：MU, ^SOX, ^IXIC, BZ=F, GC=F, 2330.TW, ^TWII 歷史（算20MA/60MA）
   - FRED：T10Y2Y
4. 用 /mnt/c/FINANCIAL/reports/2026-03-25_daily-macro-tactical-briefing.html 作為模板格式，產出完整 HTML 報告，包含：
   - 市場快照表
   - 游庭皓觀點（從今日逐字稿萃取）
   - Eason 觀點（從 SQLite 取前一天的）
   - 共識與分歧矩陣
   - 綜合信號評估（含信心分數）
   - 操作啟示
   - 關鍵價位追蹤
   - 今日觀察重點
5. 儲存報告到 ${HTML_FILE}

注意：
- 游庭皓的風格是宏觀結構分析、中性偏謹慎、關注總經風險
- Eason 的風格是台股實戰派、偏多、選股至上
- 報告要中立呈現兩人觀點差異，用數據交叉驗證
- HTML 格式要跟模板一致（含 CSS 樣式）

寫作原則（嚴格遵守）：
- **禁止編造因果解讀**：不可寫「因為X所以Y」「主戰場」「代表真粉絲」「演算法開始推」等未經證實的因果
- **只寫觀察事實**：例如「T10Y2Y 從 +0.15 升至 +0.22」「2330 突破 20MA」
- 若原因不明，明確寫「**原因不明，持續觀察**」，不要為了看起來有洞見就胡扯因果
- 共識/分歧一律基於兩人**實際說過的話**，不要替他們腦補立場" \
  --allowedTools '*' \
  --model claude-sonnet-4-6 \
  --max-turns 50 \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] Report generation completed." >> "$LOG_FILE"

# Convert HTML to PDF
if [ -f "$HTML_FILE" ]; then
  google-chrome --headless --disable-gpu --no-sandbox \
    --print-to-pdf="$PDF_FILE" --print-to-pdf-no-header \
    "$HTML_FILE" 2>/dev/null
fi

# Generate summary
SUMMARY=$(claude -p "讀取 ${LOG_FILE}，用繁體中文產出一份訊息摘要（限1800字元內），格式：
- 第一行：📊 每日總經 × 台股戰情室 ${DATE}
- 游庭皓核心觀點（2-3行）
- Eason 核心觀點（2-3行）
- 關鍵分歧（1-2行）
- 市場信號（用 emoji：🟢🟡🔴）
- 綜合信心評分
- 今日觀察重點（2-3點）
不要用 markdown 表格，用簡潔列表。只輸出摘要文字，不要多餘說明。" \
  --allowedTools 'Read' \
  --model claude-haiku-4-5 \
  --max-turns 5 \
  2>/dev/null)

[ -z "$SUMMARY" ] && SUMMARY="📊 每日總經 × 台股戰情室 ${DATE} — 報告已產出"

# Send to Discord (summary + PDF)
send_discord "$SUMMARY" "$PDF_FILE" >> "$LOG_FILE" 2>&1

# Send to LINE (summary + 2 report images)
send_line "$SUMMARY" "$HTML_FILE" >> "$LOG_FILE" 2>&1

echo "[$(date)] Discord + LINE notifications sent." >> "$LOG_FILE"
