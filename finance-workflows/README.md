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
