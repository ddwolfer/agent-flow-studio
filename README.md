# finance-workflows

Daily personal financial reports produced by a lean Python workflow runner that
orchestrates `claude -p` + a small set of local MCP servers. Reports land as
HTML / Markdown / (optional) PDF on disk and ship to a private Telegram
supergroup.

> Repo name `agent-flow-studio` is historical — the active codebase is now
> `finance-workflows/`. See `CLAUDE.md` for project-level rules and
> `finance-workflows/CLAUDE.md` for runner-level rules.

## Layout

- `finance-workflows/` — the runner, MCP servers, workflows, prompts, tests
- `mcp/knowledge-graph/` — local long-term memory (SQLite + sqlite-vec + FTS5)
  used by the main Claude Code session and by the `serenity-digest` workflow
- `serenity-digest-spec/` — design doc for the serenity-digest workflow
- `docs/superpowers/{specs,plans}/` — design & implementation history

## Workflows (scheduled via launchd)

| Workflow | Schedule (TPE) | Source | What it does |
|---|---|---|---|
| `serenity-digest` | daily 06:00 | analysissite.vercel.app | KOL daily distillation + KG memory |
| `crypto-daily` | daily 07:30 | 6 YouTube + 1 web | crypto news / social digest |
| `eason-tw-stock` | (paused) | YouTube channel | TW-stock analyst transcripts |
| `us-macro` | Mon–Fri 09:30 | FRED + Yahoo + Fed press | Fed / growth / inflation brief |
| `deep-stock-research` | Sun 10:00 | 12-ticker watchlist | weekly deep research |

## Run a workflow manually

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py <name>
```

Reports land at `finance-workflows/reports/<name>/<date>.html` (and `.pdf`
if `post.pdf: true`). Logs at `finance-workflows/reports/<name>/_logs/<date>-<ts>.log`.

A workflow that authors `_brief.md` next to its HTML output gets that file's
content used verbatim as the Telegram message body — see
`finance-workflows/scripts/notify_telegram.py`.

## Add a workflow

Config + prompts only. See `finance-workflows/CLAUDE.md` "Add a new workflow".

## Telegram

All workflows post to a shared supergroup with per-workflow forum topic IDs
held in `finance-workflows/.env` (gitignored). The env-var name is declared
in each workflow's `post.telegram` field.

## License

Private personal use.
