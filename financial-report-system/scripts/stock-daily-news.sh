#!/bin/bash
# Stock Daily News - Personal watchlist news + risk analysis
# Runs via cron weekdays - NO notifications (personal use only)
# Reports saved to /mnt/c/FINANCIAL/reports/stocks/

DATE=$(date +%Y-%m-%d)
REPORT_DIR="/mnt/c/FINANCIAL/reports/stocks"
LOG_FILE="${REPORT_DIR}/news-${DATE}.log"
HTML_FILE="${REPORT_DIR}/news-${DATE}.html"

mkdir -p "$REPORT_DIR"

echo "[$(date)] Starting stock daily news scan..." > "$LOG_FILE"

cd /mnt/c/FINANCIAL
claude -p "你是個股研究助理。今天是 ${DATE}。請執行以下任務：

1. 從 SQLite stock_watchlist 表讀取所有 active=1 的股票
2. 對每支股票：
   - 用 Yahoo Finance 取得最新新聞 (get_yahoo_finance_news)
   - 用 TWSE 取得公司重大訊息 (get_company_major_news)
   - 用 Yahoo Finance 取得今日股價資訊 (get_stock_info)
   - 如需 WebSearch 補充，搜尋關鍵字必須包含近期日期（如 ${DATE}），只採用 48 小時內的新聞
3. ⚠️ 嚴格時間過濾：
   - 只收錄過去 48 小時內發布的新聞（以新聞發布日期為準）
   - 超過 48 小時的舊聞一律丟棄，不納入報告
   - 如果無法確認新聞日期，標註為「日期不明」並降低權重
   - 如果所有股票加總後有效新聞為 0 則，不產出 HTML 報告，只在 log 寫一行「無新聞，跳過」即可結束
4. 對每則新聞做風險評估：
   - risk_level: LOW / MEDIUM / HIGH / CRITICAL
   - sentiment: POSITIVE / NEUTRAL / NEGATIVE
   - 一句話風險摘要
5. 將新聞寫入 SQLite stock_daily_news 表（date=${DATE}），不要重複寫入已存在的新聞
6. 產出 HTML 報告存到 ${HTML_FILE}，格式：
   - 標題：📋 個股新聞日報 ${DATE}
   - 每支股票一個區塊：股價快照 + 新聞列表（含風險標記 🟢🟡🔴🔴）
   - 每則新聞標註發布日期
   - 風險摘要總結
   - 使用深藍主色調、卡片式排版
7. 在 SQLite stock_daily_report 表記錄本次報告

只做分析，不要發送任何通知。" \
  --allowedTools '*' \
  --model claude-sonnet-4-6 \
  --max-turns 30 \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] Stock daily news scan completed." >> "$LOG_FILE"
