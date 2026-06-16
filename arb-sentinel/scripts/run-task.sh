#!/usr/bin/env bash
set -euo pipefail
TASK="${1:?usage: run-task.sh <task>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec "$ROOT/.venv/bin/python" -m arb_sentinel --task "$TASK"
