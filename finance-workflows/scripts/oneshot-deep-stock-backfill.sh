#!/usr/bin/env bash
# One-shot backfill for deep-stock-research 2026-05-31.
# Scheduled via ~/Library/LaunchAgents/com.financeworkflows.deep-stock-backfill.plist
# at 2026-06-02 03:30 TPE (Anthropic quota resets at 03:30).
# Self-unloads after running so it doesn't re-fire next year.

set -u

LOG_DIR="$HOME/Library/Logs"
LOG_FILE="$LOG_DIR/financeworkflows-deep-stock-backfill.log"
PLIST="$HOME/Library/LaunchAgents/com.financeworkflows.deep-stock-backfill.plist"
LABEL="com.financeworkflows.deep-stock-backfill"

mkdir -p "$LOG_DIR"

echo "=== oneshot deep-stock backfill start $(date -Iseconds) ===" >> "$LOG_FILE"

cd /Users/pochenkuo/AI/new_financial-report-system/finance-workflows || {
  echo "FATAL: cannot cd to finance-workflows" >> "$LOG_FILE"
  exit 2
}

FINANCE_WORKFLOWS_DATE=2026-05-31 \
  mcp/.venv/bin/python run-workflow.py deep-stock-research \
  >> "$LOG_FILE" 2>&1
RC=$?

echo "=== oneshot deep-stock backfill end rc=$RC $(date -Iseconds) ===" >> "$LOG_FILE"

# Self-cleanup: unload + remove plist regardless of rc, so it doesn't fire
# again next year. If you want to re-arm for another day, edit the plist's
# Month/Day and reload.
launchctl bootout "gui/$(id -u)/$LABEL" 2>>"$LOG_FILE" || true
rm -f "$PLIST"

exit "$RC"
