# finance-workflows

Lean Python runner that produces daily financial reports from declarative
`workflows/*.json` files. Drives headless `claude -p` with a per-workflow
MCP server set and concatenated prompts.

- **Spec:** `../docs/superpowers/specs/2026-05-21-finance-workflows-design.md`
- **How to work here:** [`CLAUDE.md`](CLAUDE.md)

## Quick start

```bash
cd finance-workflows
python3 -m venv mcp/.venv
mcp/.venv/bin/pip install -r requirements.txt
mcp/.venv/bin/python run-workflow.py crypto-daily
open "reports/crypto-daily/$(date +%Y-%m-%d).html"
```

## Architecture (one paragraph)

`run-workflow.py <name>` loads `workflows/<name>.json`, renders a per-workflow
`mcp/mcp.json` containing only the servers the workflow needs, concatenates
the listed `prompts/*.md` with `${DATE}`/`${OUTPUT_PATH}`/`${SOURCES_JSON}`/
`${WORKFLOW_NAME}` substituted, then invokes `claude -p` headlessly. Claude
uses the MCP tools to fetch sources, then writes the report HTML to
`reports/<name>/<date>.html`. Optional PDF via headless Chrome; optional
single-line JSON history via Haiku appended to `_history.jsonl`. No web UI,
no SQLite, no state machine.

## Workflows with pre-fetch step (morning-briefing pattern)

Workflows that need data not covered by the standard MCP set (Binance fapi,
CBOE VIX CSV, Treasury upcoming auctions, DefiLlama stablecoins) follow the
`morning-briefing` pattern:

1. A pre-script (`scripts/<name>_extras.py` or `scripts/<name>.sh`) fetches
   keyless JSON/CSV and writes to `reports/<name>/_extras/<date>.json`.
2. The prompt then `Read`s that file via the standard `${DATE}` substitution.
3. A cron wrapper (`scripts/<name>.sh`) chains pre-fetch → `run-workflow.py`.
4. The launchd plist invokes the wrapper, NOT `run-workflow.py` directly.

`run-workflow.py` stays generic — pre-hooks live in the wrapper, not the
runner. See `scripts/fetch_extras.py` + `scripts/morning_briefing.sh` for
the canonical example.

## Daily schedule (TPE)

| Time | Workflow | Cadence | What it covers |
|------|----------|---------|----------------|
| **07:00** | **morning-briefing** | Mon-Fri | Cross-asset tape + 5 things + today's calendar + TW open hint |
| 07:30 | crypto-daily | Daily | Crypto deep dive |
| 09:30 | us-macro | Mon-Fri | US macro: Fed, growth, inflation, curve, risk regime |
| (TBD) | serenity-digest | Daily | Aggregated KOL digest |

`pmset repeat wakeorpoweron MTWRFSU 06:55:00` covers all of the above
(wakes 5 min before the earliest fire time). macOS allows only one
`pmset repeat` rule, so set it once.
