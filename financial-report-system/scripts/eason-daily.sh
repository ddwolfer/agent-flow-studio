#!/bin/bash
# Eason Daily Analysis - runs via cron weekdays 8pm Taiwan time
# Generates report → HTML → PDF → Discord(text+PDF) + LINE(text+images)

DATE=$(date +%Y-%m-%d)
REPORT_DIR="/mnt/c/FINANCIAL/reports"
LOG_FILE="${REPORT_DIR}/eason-${DATE}.log"
HTML_FILE="${REPORT_DIR}/eason-${DATE}.html"
PDF_FILE="${REPORT_DIR}/eason-${DATE}.pdf"

source /mnt/c/FINANCIAL/scripts/notify.sh
mkdir -p "$REPORT_DIR"

echo "[$(date)] Starting Eason daily analysis..." > "$LOG_FILE"

cd /mnt/c/FINANCIAL
claude -p "/eason-analysis

完成分析後，請額外產出一份完整的 HTML 報告，使用 /mnt/c/FINANCIAL/reports/2026-03-25_daily-macro-tactical-briefing.html 的 CSS 樣式作為參考（深藍主色、紅色強調、信號用 emoji 色塊、卡片式排版），儲存到 ${HTML_FILE}。報告標題為「Eason 視角：台股 AI 戰情室 ${DATE}」。

寫作原則（嚴格遵守）：
- **禁止編造因果解讀**：不要寫「推薦池鎖定」「主戰場」「代表真粉絲」「演算法開始推」這類未經證實的因果論述
- **只引用 Eason 實際說過的話**：立場分數、目標價、產業觀點都必須從影片逐字稿萃取，不要替他腦補
- **指標儀表板用觀察事實**：例如「費半季線 +2.3%」「MU 站上 60MA」，不要加「顯示資金回流AI」這種因果話
- 若原因不明或資料不足，明確寫「**原因不明，持續觀察**」
- 偏誤檢查段落保留原本功能（錄影時間 vs 市場開盤的時間差）" \
  --allowedTools '*' \
  --model claude-sonnet-4-6 \
  --max-turns 50 \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] Eason daily analysis completed." >> "$LOG_FILE"

# Convert HTML to PDF
if [ -f "$HTML_FILE" ]; then
  google-chrome --headless --disable-gpu --no-sandbox \
    --print-to-pdf="$PDF_FILE" --print-to-pdf-no-header \
    "$HTML_FILE" 2>/dev/null
fi

# Generate summary
SUMMARY=$(claude -p "讀取 ${LOG_FILE}，用繁體中文產出一份訊息摘要（限1800字元內），格式：
- 第一行：📊 Eason 視角：台股 AI 戰情室 ${DATE}
- 影片標題 + 立場分數 + 語氣強度
- 指標儀表板（用 emoji 信號：🟢🟡🔴）
- AI族群快掃（1-2行）
- 偏誤檢查結論（1行）
- 關鍵價位（季線、MU季線）
- 信心評分
不要用 markdown 表格，用簡潔列表。只輸出摘要文字，不要多餘說明。" \
  --allowedTools 'Read' \
  --model claude-haiku-4-5 \
  --max-turns 5 \
  2>/dev/null)

[ -z "$SUMMARY" ] && SUMMARY="📊 Eason 視角：台股 AI 戰情室 ${DATE} — 報告已產出"

# Send to Discord (summary + PDF)
send_discord "$SUMMARY" "$PDF_FILE" >> "$LOG_FILE" 2>&1

# Send to LINE (summary + 2 report images)
send_line "$SUMMARY" "$HTML_FILE" >> "$LOG_FILE" 2>&1

echo "[$(date)] Discord + LINE notifications sent." >> "$LOG_FILE"

# ===== 萃取 Eason 推薦個股 → 寫入 eason_picks 資料表 =====
echo "[$(date)] Extracting Eason stock picks..." >> "$LOG_FILE"

claude -p "讀取今天的 Eason 報告 ${HTML_FILE} 和 log ${LOG_FILE}，萃取 Eason 今天**明確帶方向提及**的個股，寫入 SQLite 資料庫 eason_picks 表。

嚴格規則（寧可漏也不要亂寫）：
1. **只萃取以下三類**：
   - 新推薦（今天首次明確建議進場）→ signal_type='新推', status='active'
   - 抗跌觀察 / 候選名單（可買訊號、觀察）→ signal_type='抗跌觀察', status='active'
   - 明確喊出場或停損 → UPDATE 該 ticker 最近一筆 status='active' 紀錄 → status='closed', close_reason='Eason 出場' 或 '停損'
2. **不要寫入**：
   - 只是泛論產業沒點名個股
   - 順帶提到但沒帶方向
   - 維持持倉沒新動作（重複紀錄沒意義）
   - 列名稱但沒任何評論傾向
3. **去重**：先用 mcp__sqlite__query 查 SELECT id FROM eason_picks WHERE ticker=? AND pick_date=?，已有就跳過
4. **欄位對應**：
   - pick_date = ${DATE}
   - ticker, name = 從報告中取
   - entry_price = 當日收盤（若報告有寫）
   - category = 散熱/CPO/記憶體/ASIC/被動元件/設備/AI伺服器/金融/其他
   - confidence = 強（重押/主戰場語氣）/ 中（推薦但不強調）/ 弱（順帶提一下）
   - reason_industry / reason_technical / reason_chips = 分別填（沒有就 NULL）
   - reason_summary = 一句話總結（≤50字）
   - source = 'Eason daily ${DATE}'
5. 完成後輸出單行：『[picks] 新增 N 筆 / 更新 M 筆出場 / 跳過 K 筆重複』

若判斷不出來或資料不足，寧可不寫入，不要腦補。" \
  --allowedTools 'Read,mcp__sqlite__query,mcp__sqlite__create_record,mcp__sqlite__update_records' \
  --model claude-haiku-4-5 \
  --max-turns 30 \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] Eason picks extraction completed." >> "$LOG_FILE"
