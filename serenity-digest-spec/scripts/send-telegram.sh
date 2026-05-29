#!/usr/bin/env bash
# send-telegram.sh
#
# 從 stdin 讀 brief markdown，發送到 Telegram。
# 自動處理：
#   - URL encode
#   - 訊息分段（超過 4000 chars）
#   - retry（2 次，間隔 30s, 60s）
#
# 用法：
#   cat brief.md | bash scripts/send-telegram.sh
#   bash scripts/send-telegram.sh < brief.md
#
# 環境：
#   config.json 在 ~/.config/serenity-digest/config.json

set -e
set -o pipefail

CONFIG="$HOME/.config/serenity-digest/config.json"
if [ ! -f "$CONFIG" ]; then
  echo "[ERROR] config not found: $CONFIG" >&2
  exit 2
fi

TOKEN=$(jq -r '.telegram.bot_token' "$CONFIG")
CHAT=$(jq -r '.telegram.chat_id' "$CONFIG")

if [ -z "$TOKEN" ] || [ "$TOKEN" = "null" ] || [ "$TOKEN" = "PLACEHOLDER_REPLACE_ME" ]; then
  echo "[ERROR] telegram.bot_token not set in config" >&2
  exit 2
fi
if [ -z "$CHAT" ] || [ "$CHAT" = "null" ] || [ "$CHAT" = "PLACEHOLDER_REPLACE_ME" ]; then
  echo "[ERROR] telegram.chat_id not set in config" >&2
  exit 2
fi

BRIEF=$(cat)
LEN=${#BRIEF}

API="https://api.telegram.org/bot${TOKEN}/sendMessage"

send_once() {
  local text="$1"
  local attempt=0
  while [ $attempt -lt 3 ]; do
    HTTP=$(curl -s -o /tmp/tg-resp.json -w "%{http_code}" \
      "$API" \
      -d "chat_id=$CHAT" \
      -d "parse_mode=Markdown" \
      -d "disable_web_page_preview=true" \
      --data-urlencode "text=$text")
    if [ "$HTTP" = "200" ]; then
      MSG_ID=$(jq -r '.result.message_id' /tmp/tg-resp.json 2>/dev/null || echo "?")
      echo "[INFO] telegram send: 200 OK, message_id $MSG_ID" >&2
      return 0
    fi
    attempt=$((attempt + 1))
    DELAY=$((30 * attempt))
    echo "[WARN] telegram send failed (HTTP $HTTP), retry in ${DELAY}s" >&2
    sleep $DELAY
  done
  echo "[ERROR] telegram send failed after 3 attempts" >&2
  cat /tmp/tg-resp.json >&2
  return 1
}

if [ $LEN -le 3900 ]; then
  send_once "$BRIEF"
else
  # 分段
  HALF=$((LEN / 2))
  # 找最近的換行作為切點
  SPLIT=$(echo "$BRIEF" | head -c $HALF | tail -c 500 | grep -on $'\n' | tail -1 | cut -d: -f1)
  SEG1=$(echo "$BRIEF" | head -c $((HALF - 500 + SPLIT)))
  SEG2=$(echo "$BRIEF" | tail -c $((LEN - (HALF - 500 + SPLIT))))

  send_once "$SEG1
(1/2)"
  sleep 1
  send_once "(2/2)
$SEG2"
fi
