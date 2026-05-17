#!/usr/bin/env bash
out="${FAKE_CLAUDE_OUT:?FAKE_CLAUDE_OUT required}"
echo "<html><body>fake report</body></html>" > "$out"
exit "${FAKE_CLAUDE_EXIT:-0}"
