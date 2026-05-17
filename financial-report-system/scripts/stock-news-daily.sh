#!/bin/bash
# Daily Stock News - every day 8:00am
# Searches today's news for holdings + watchlist, sends to Discord
# Discord webhook: dedicated channel for stock news

DATE=$(date +%Y-%m-%d)
LOG_FILE="/mnt/c/FINANCIAL/reports/stock-news-${DATE}.log"
WATCHLIST="/mnt/c/FINANCIAL/watchlist.txt"
# Read webhook from env (this script uses a separate Discord channel from main briefing)
[ -f "$(dirname "$0")/.env" ] && set -a && source "$(dirname "$0")/.env" && set +a
: "${STOCK_NEWS_DISCORD_WEBHOOK:?STOCK_NEWS_DISCORD_WEBHOOK env var required}"
DISCORD_WEBHOOK="$STOCK_NEWS_DISCORD_WEBHOOK"

mkdir -p /mnt/c/FINANCIAL/reports
echo "[$(date)] Starting daily stock news search..." > "$LOG_FILE"

# Build watchlist section for prompt
WATCHLIST_SECTION=""
if [ -f "$WATCHLIST" ]; then
  WATCHLIST_CONTENT=$(cat "$WATCHLIST")
  WATCHLIST_SECTION="

另外也搜尋以下觀察名單的新聞：
${WATCHLIST_CONTENT}
"
fi

cd /mnt/c/FINANCIAL
claude -p "你是台股新聞助理。今天是 ${DATE}。請執行以下任務：

## 1. 搜尋今日新聞

用 WebSearch 搜尋以下**持倉股票**的當日新聞：
（請從 SQLite stock_watchlist 表讀取 active=1 的個股，或在此處硬編寫個股清單）
範例格式：
- TICKER NAME（產業描述）
- TICKER NAME（產業描述）
${WATCHLIST_SECTION}

搜尋關鍵字用中文（個股名稱 + 主要題材），也可搜尋產業關鍵字。

## 2. 篩選規則
- **時間窗口：上一個交易日 13:30 收盤後 → 現在**
  - 週二~週五早上 8 點跑：涵蓋昨天 13:30 → 今天 8:00（約 18-19 小時）
  - 週一早上 8 點跑：涵蓋上週五 13:30 → 週一 8:00（含週末，約 66 小時）
  - 重點是要抓到盤後新聞（外資進出、法說、深度分析多在前一交易日 13:30-23:00 發布）
- 嚴格驗證每則新聞的發布日期/時間，超出窗口的舊聞一律剔除
- 沒有找到新聞的股票直接跳過，不要硬加
- 如果全部都沒新聞，就只輸出「今日無重大持倉相關新聞」

## 3. 輸出格式
直接輸出純文字（Discord markdown），不要用程式碼區塊包裹整段訊息：

📰 **持倉新聞日報** — ${DATE}

**個股名稱 (代號)**
- 新聞標題 — 來源
  一句話摘要

**個股名稱 (代號)**
- 新聞標題 — 來源
  一句話摘要

（沒新聞的股票不列出）

如果有觀察名單新聞，用另一個區塊：

📋 **觀察名單**
...

## 重要
- 不要輸出任何多餘的解釋或開場白，直接輸出新聞內容
- 控制在 1800 字元以內（Discord 上限 2000）
- 如果超過就精簡摘要
" 2>> "$LOG_FILE" | while IFS= read -r line; do
  # Accumulate output
  echo "$line"
done > /tmp/stock-news-msg.txt 2>> "$LOG_FILE"

MSG=$(cat /tmp/stock-news-msg.txt)

# Send to Discord (handle message length)
MSG_LEN=${#MSG}
echo "[$(date)] Message length: ${MSG_LEN}" >> "$LOG_FILE"

if [ -z "$MSG" ] || [ "$MSG_LEN" -lt 10 ]; then
  MSG="📰 **持倉新聞日報** — ${DATE}\n\n今日無重大持倉相關新聞"
fi

if [ "$MSG_LEN" -le 2000 ]; then
  curl -s -H "Content-Type: application/json" \
    -d "$(python3 -c "import json,sys; print(json.dumps({'content': sys.stdin.read()}))" <<< "$MSG")" \
    "$DISCORD_WEBHOOK" >> "$LOG_FILE" 2>&1
else
  # Split into chunks of 1900 chars
  echo "$MSG" | fold -w 1900 -s | while IFS= read -r chunk; do
    curl -s -H "Content-Type: application/json" \
      -d "$(python3 -c "import json,sys; print(json.dumps({'content': sys.stdin.read()}))" <<< "$chunk")" \
      "$DISCORD_WEBHOOK" >> "$LOG_FILE" 2>&1
    sleep 1
  done
fi

echo "[$(date)] Stock news daily completed." >> "$LOG_FILE"
