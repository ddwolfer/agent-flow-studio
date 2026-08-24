#!/usr/bin/env bash
# Cron driver for the morning-briefing workflow.
#
# Two-step:
#   1. fetch_extras.py pre-fetches keyless data sources (Binance fapi /
#      CBOE VIX / Treasury auctions / DefiLlama stablecoins) and writes
#      JSON the prompt then reads.
#   2. run-workflow.py morning-briefing runs claude -p with the workflow's
#      prompts, which Read the extras JSON + pull from MCP sources.
#
# Designed for launchd (or plain cron). Logs to ~/Library/Logs/.
# Idempotent: re-running on the same day overwrites that day's _extras +
# HTML output.
set -euo pipefail

FW_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$FW_ROOT"

# Use LOCAL date (TPE for the user's machine) to match run-workflow.py's
# `_today_iso()` — otherwise _extras/<UTC-date>.json and HTML <local-date>.html
# would diverge by 1 calendar day when the job fires at 07:00 TPE (= 23:00 UTC
# the previous day) and the prompt's Read on _extras/${DATE}.json would 404.
DATE="${FINANCE_WORKFLOWS_DATE:-$(date +%F)}"
PY="$FW_ROOT/mcp/.venv/bin/python"

EXTRAS_DIR="$FW_ROOT/reports/morning-briefing/_extras"
NEWS_DIR="$FW_ROOT/reports/morning-briefing/_news"
mkdir -p "$EXTRAS_DIR" "$NEWS_DIR"
EXTRAS_PATH="$EXTRAS_DIR/$DATE.json"
NEWS_PATH="$NEWS_DIR/$DATE.json"

echo "[morning-briefing] step 1a: pre-fetch extras → $EXTRAS_PATH"
# fetch_extras is fail-isolated per source — exit code is always 0 unless
# the CLI itself errors. We still want to fail the cron job if THAT happens
# (the prompt depends on the file existing).
"$PY" "$FW_ROOT/scripts/fetch_extras.py" --output "$EXTRAS_PATH"

if [[ ! -s "$EXTRAS_PATH" ]]; then
    echo "[morning-briefing] FATAL: $EXTRAS_PATH missing or empty after pre-fetch" >&2
    exit 5
fi

# 1b: news digest. Non-fatal — if all news feeds are down, the workflow still
# runs with the tape/calendar data. The prompt handles a missing file by
# stating "昨日新聞:資料不可用" and continuing.
echo "[morning-briefing] step 1b: aggregate news digest → $NEWS_PATH"
"$PY" "$FW_ROOT/scripts/fetch_news_digest.py" --out "$NEWS_PATH" \
    || echo "[morning-briefing] WARN: news digest fetch failed (non-fatal)" >&2

echo "[morning-briefing] step 2: run workflow"
exec "$PY" "$FW_ROOT/run-workflow.py" morning-briefing
