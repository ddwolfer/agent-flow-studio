#!/usr/bin/env bash
# Cron driver for the crypto-daily workflow.
#
# Two-step (mirrors morning_briefing.sh):
#   1. fetch_btc_cycle.py pre-fetches deterministic market-structure data
#      (幣本位資金費率 / KDJ 4h-1d-1w / 200D MA / 難度 + 礦工投降訊號 / 算力)
#      and writes JSON the prompt then Reads.
#   2. run-workflow.py crypto-daily runs claude -p with the workflow's prompts.
#
# Why pre-fetch instead of letting the LLM compute: every number in §大週期
# must be deterministic and reproducible — same rule as compute_zones.py.
# The LLM narrates the JSON, it never calculates.
#
# Idempotent: re-running on the same day overwrites that day's _extras + HTML.
set -euo pipefail

FW_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$FW_ROOT"

# LOCAL date, to match run-workflow.py's _today_iso() — see morning_briefing.sh
# for the full explanation of why UTC would desync the _extras path.
DATE="${FINANCE_WORKFLOWS_DATE:-$(date +%F)}"
PY="$FW_ROOT/mcp/.venv/bin/python"

EXTRAS_DIR="$FW_ROOT/reports/crypto-daily/_extras"
mkdir -p "$EXTRAS_DIR"
EXTRAS_PATH="$EXTRAS_DIR/$DATE.json"

echo "[crypto-daily] step 1: pre-fetch BTC cycle data → $EXTRAS_PATH"
# fetch_btc_cycle is fail-isolated per source (each block gets its own "error"
# key), so a single dead API degrades one section instead of killing the run.
"$PY" "$FW_ROOT/scripts/fetch_btc_cycle.py" --output "$EXTRAS_PATH"

if [[ ! -s "$EXTRAS_PATH" ]]; then
    echo "[crypto-daily] FATAL: $EXTRAS_PATH missing or empty after pre-fetch" >&2
    exit 5
fi

echo "[crypto-daily] step 2: run workflow"
exec "$PY" "$FW_ROOT/run-workflow.py" crypto-daily
