#!/usr/bin/env bash
# nightly.sh
#
# Cowork 排程任務的主入口腳本。
# 在 06:00 觸發，按順序執行：抓取 → 組 brief → 推送 → 寫日誌
#
# 這個 shell 版本用於不透過 LLM 直接跑時的 fallback。
# 正式上線時建議用 prompts/daily-brief.md 讓 Claude 主導，
# 才能用到 Persona Layer 與 KG retrieval。
#
# 用法：
#   bash scripts/nightly.sh

set -e

DIGEST_DIR="$HOME/Desktop/serenity-digest"
DATA_DIR="$DIGEST_DIR/data"
BRIEFS_DIR="$DIGEST_DIR/briefs"
LOGS_DIR="$DIGEST_DIR/logs"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

DATE=$(date +%Y-%m-%d)
NOW=$(date -Iseconds)
LOG="$LOGS_DIR/$DATE.log"

mkdir -p "$DATA_DIR" "$BRIEFS_DIR" "$LOGS_DIR"

log() {
  echo "$(date -Iseconds) [$1] $2" | tee -a "$LOG" >&2
}

log INFO "nightly start"

# ===== 階段 A：抓取 =====
log INFO "stage A: scrape"
if node "$SCRIPT_DIR/scrape-snapshot.mjs" 2>>"$LOG"; then
  log INFO "scrape success"
else
  log ERROR "scrape failed"
  exit 1
fi

# ===== 階段 E：組 brief =====
log INFO "stage E: compose"
BRIEF_OUT="$BRIEFS_DIR/$DATE.md"
if node "$SCRIPT_DIR/compose-brief.mjs" > "$BRIEF_OUT" 2>>"$LOG"; then
  LEN=$(wc -c < "$BRIEF_OUT")
  log INFO "brief composed: $LEN chars"
else
  log ERROR "compose failed"
  exit 1
fi

# ===== 階段 F：推送 =====
log INFO "stage F: telegram"
if bash "$SCRIPT_DIR/send-telegram.sh" < "$BRIEF_OUT" 2>>"$LOG"; then
  log INFO "telegram send success"
else
  log ERROR "telegram send failed"
  # 存到 UNDELIVERED
  mkdir -p "$BRIEFS_DIR/UNDELIVERED"
  cp "$BRIEF_OUT" "$BRIEFS_DIR/UNDELIVERED/$DATE.md"
fi

# ===== 階段 H：index =====
TOP_TICKERS=$(jq -r '[.hotStocks[0:3][].ticker] | join(",")' "$DATA_DIR/$DATE.json")
ACTIVE=$(jq -r '.metrics.activeSignals // "null"' "$DATA_DIR/$DATE.json")

echo "{\"date\":\"$DATE\",\"topTickers\":\"$TOP_TICKERS\",\"activeSignals\":$ACTIVE,\"briefLength\":$LEN,\"status\":\"ok\"}" \
  >> "$DATA_DIR/index.jsonl"

log INFO "nightly complete"
