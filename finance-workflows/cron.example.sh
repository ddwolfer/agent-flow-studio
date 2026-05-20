#!/usr/bin/env bash
# Example cron driver. Crontab line (weekday 08:30 Asia/Taipei):
#   30 8 * * 1-5  /path/to/cron.example.sh crypto-daily >> /tmp/fw-cron.log 2>&1

set -euo pipefail
WORKFLOW="${1:?usage: cron.example.sh <workflow-name>}"
FW_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$FW_ROOT"
"$FW_ROOT/mcp/.venv/bin/python" run-workflow.py "$WORKFLOW"
