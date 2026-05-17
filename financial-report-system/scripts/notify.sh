#!/bin/bash
# Shared notification functions for Discord + LINE
# Usage: source this file, then call send_discord / send_line
#
# Required env vars (set in .env or shell before sourcing):
#   DISCORD_WEBHOOK   — Discord channel webhook URL
#   LINE_TOKEN        — LINE Messaging API channel access token
#   LINE_GROUP_ID     — Target LINE group/user ID
#   IMGHOST_KEY       — freeimage.host API key (for screenshot upload)

: "${DISCORD_WEBHOOK:?DISCORD_WEBHOOK env var required}"
: "${LINE_TOKEN:?LINE_TOKEN env var required}"
: "${LINE_GROUP_ID:?LINE_GROUP_ID env var required}"
: "${IMGHOST_KEY:?IMGHOST_KEY env var required}"

# Send text + PDF to Discord
send_discord() {
  local MSG="$1"
  local PDF_FILE="$2"

  local UA="DiscordBot (https://financial.local, 1.0)"

  if [ -n "$PDF_FILE" ] && [ -f "$PDF_FILE" ]; then
    curl -s -A "$UA" \
      -F "content=$(echo "$MSG")" \
      -F "file1=@${PDF_FILE}" \
      "$DISCORD_WEBHOOK"
  else
    curl -s -A "$UA" -H "Content-Type: application/json" \
      -d "{\"content\": $(echo "$MSG" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}" \
      "$DISCORD_WEBHOOK"
  fi
}

# Send text + 2 report images to LINE group
# Args: $1 = summary text, $2 = HTML file path
send_line() {
  local MSG="$1"
  local HTML_FILE="$2"
  MSG="${MSG:0:4990}"

  # If HTML file provided, screenshot + split + upload
  if [ -n "$HTML_FILE" ] && [ -f "$HTML_FILE" ]; then
    local TMPDIR=$(mktemp -d)
    local FULL_IMG="${TMPDIR}/full.png"
    local TOP_IMG="${TMPDIR}/top.png"
    local BOT_IMG="${TMPDIR}/bottom.png"

    # Full page screenshot (8000px to capture long reports)
    google-chrome --headless --disable-gpu --no-sandbox \
      --screenshot="$FULL_IMG" \
      --window-size=800,8000 \
      "$HTML_FILE" 2>/dev/null

    # Crop to actual content, then split into 2 halves
    # NOTE: requires PIL. If conda python is in PATH, this may fail —
    # cron uses /usr/bin/python3 which has PIL via apt (python3-pil).
    python3 << PYEOF
from PIL import Image
import numpy as np

img = Image.open("${FULL_IMG}")
w, h = img.size

# Find actual content bottom (trim white space)
arr = np.array(img)
row_means = arr.mean(axis=(1,2))
content_rows = np.where(row_means < 250)[0]
actual_h = content_rows[-1] + 50 if len(content_rows) > 0 else h

img_cropped = img.crop((0, 0, w, actual_h))
mid = actual_h // 2
img_cropped.crop((0, 0, w, mid)).save("${TOP_IMG}", optimize=True)
img_cropped.crop((0, mid, w, actual_h)).save("${BOT_IMG}", optimize=True)
PYEOF

    # Upload to image host
    local URL1=$(curl -s -X POST "https://freeimage.host/api/1/upload" \
      -F "key=${IMGHOST_KEY}" \
      -F "source=@${TOP_IMG}" \
      -F "format=json" | python3 -c "import json,sys; print(json.load(sys.stdin)['image']['url'])" 2>/dev/null)

    local URL2=$(curl -s -X POST "https://freeimage.host/api/1/upload" \
      -F "key=${IMGHOST_KEY}" \
      -F "source=@${BOT_IMG}" \
      -F "format=json" | python3 -c "import json,sys; print(json.load(sys.stdin)['image']['url'])" 2>/dev/null)

    # Send text + 2 images (3 messages)
    if [ -n "$URL1" ] && [ -n "$URL2" ]; then
      curl -s -X POST https://api.line.me/v2/bot/message/push \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LINE_TOKEN}" \
        -d "{
          \"to\": \"${LINE_GROUP_ID}\",
          \"messages\": [
            {\"type\": \"text\", \"text\": $(echo "$MSG" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')},
            {\"type\": \"image\", \"originalContentUrl\": \"${URL1}\", \"previewImageUrl\": \"${URL1}\"},
            {\"type\": \"image\", \"originalContentUrl\": \"${URL2}\", \"previewImageUrl\": \"${URL2}\"}
          ]
        }"
    else
      # Fallback: text only
      curl -s -X POST https://api.line.me/v2/bot/message/push \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${LINE_TOKEN}" \
        -d "{
          \"to\": \"${LINE_GROUP_ID}\",
          \"messages\": [{\"type\": \"text\", \"text\": $(echo "$MSG" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}]
        }"
    fi

    rm -rf "$TMPDIR"
  else
    # Text only
    curl -s -X POST https://api.line.me/v2/bot/message/push \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer ${LINE_TOKEN}" \
      -d "{
        \"to\": \"${LINE_GROUP_ID}\",
        \"messages\": [{\"type\": \"text\", \"text\": $(echo "$MSG" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')}]
      }"
  fi
}
