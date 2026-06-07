---
name: finance-loop
description: Use when the user invokes /finance-loop <workflow-name> (e.g. `/finance-loop crypto-daily`, `/finance-loop us-macro`, `/finance-loop serenity-digest`). Runs one of the finance-workflows pipelines entirely inside this interactive Claude Code session — no `claude -p` subprocess, no `run-workflow.py`. Reads `workflows/<name>.json` + the prompts it declares, executes the analysis with the configured MCPs, writes HTML, generates PDF (if `post.pdf`), pushes Telegram (if `post.telegram`). Designed for both manual one-shot runs and `/loop <interval> /finance-loop <workflow>` after 2026-06-15 (if `/loop` turns out to bill from the interactive subscription pool instead of the new programmatic credit pool — TBD pending Anthropic billing dashboard data post-cutover).
---

# finance-loop

The user wants to run one of the finance-workflows pipelines (`args` = workflow name) inline in this interactive session.

## Parse args

`args` should be a single workflow name. Known set (from `finance-workflows/workflows/*.json`):

- `crypto-daily`
- `serenity-digest`
- `us-macro`
- `eason-tw-stock` (currently paused but skill still supports it)
- `deep-stock-research` (prefer using `/deep-research-stock` for custom watchlists; this skill runs the JSON's default watchlist)

If `args` is empty or doesn't match a known workflow, ask the user:
> 「請告訴我要跑哪個 workflow:`crypto-daily` / `serenity-digest` / `us-macro` / `eason-tw-stock` / `deep-stock-research`」
and stop until they answer.

## Load workflow config

Read `finance-workflows/workflows/<name>.json`. Capture these fields:

| field | how to use |
|---|---|
| `model`, `max_turns` | **ignore** — your context window governs this run |
| `sources` | pass to the prompt as `${SOURCES_JSON}` (JSON-stringified) |
| `tools` | the MCPs the prompt expects to call. Verify each is loaded (see below); warn the user if any is missing |
| `prompts` | array of prompt files (relative to `finance-workflows/`) — read in declared order |
| `output` | template like `reports/<name>/{date}.html`; substitute `{date}` with today's date in Asia/Taipei (use `date +%Y-%m-%d` via Bash if needed) |
| `post.pdf` | bool — if true, generate PDF after HTML |
| `post.telegram` | string env-var name (e.g. `TELEGRAM_TOPIC_CRYPTO`) or null — if set, push Telegram |
| `history` | optional — see below |

### MCP availability check

Root `.mcp.json` should declare each of: `yt-dlp`, `rss`, `web-fetch`, `fred`, `yahoo-finance`, `twse`, `edgar`, `knowledge-graph`. Confirm `args.tools` ⊆ available. If not, tell the user which MCP is missing and stop — do not attempt to run with degraded tools (would silently fabricate / fail).

## Read prompts

Read every file in `prompts` from `finance-workflows/` (in declared order). Treat the combination as the binding spec for this run. The order is usually: `faithfulness.md` → domain `framework.md` → domain `voice.md` → optional `digest.md`/`transcript.md` → `main.md`. Read all of them; do not skip any.

Substitute `${TOKEN}` placeholders mentally as you execute (the prompts assume runner substitution, but you're the runner now):

- `${WORKFLOW_NAME}` → workflow name
- `${DATE}` → today's date in Asia/Taipei (YYYY-MM-DD)
- `${SOURCES_JSON}` → JSON-stringified `sources` array
- `${OUTPUT_PATH}` → `output` with `{date}` substituted

## Execute

Follow `main.md` literally — it tells you what MCP tools to call, what to gather, and what HTML structure to write. The other prompt files set the rules:

- `faithfulness.md` — **anti-fabrication rules, override everything else**
- `framework.md` — analytical structure (sections, depth, fields)
- `voice.md` — tone (neutral analyst, not cheerleader, conditional language)
- `digest.md` / `transcript.md` (if present) — sub-step specs (e.g. transcript cleaning before analysis)

Use only the MCPs declared in `tools`. Do not invent new tool calls.

For `serenity-digest`: after writing the HTML, **also write `_brief.md`** next to it — that's what gets used as the Telegram body (see Post-processing → Telegram).

## Post-processing

### 1. PDF (if `post.pdf` is true)

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless \
  --print-to-pdf=finance-workflows/reports/<name>/<today>.pdf \
  finance-workflows/reports/<name>/<today>.html
```

(Skip silently if `post.pdf` is false — e.g. `serenity-digest` doesn't want PDF.)

### 2. Telegram (if `post.telegram` is set)

`scripts/notify_telegram.py` doesn't have a CLI entry — call its `notify()` function programmatically:

```bash
cd finance-workflows && mcp/.venv/bin/python <<'PY'
import os, pathlib, sys
ENV = pathlib.Path(".env")
for line in ENV.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, _, v = line.partition("=")
    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
sys.path.insert(0, "scripts")
from notify_telegram import notify
notify(
    workflow_name="<WORKFLOW>",
    date="<DATE>",
    output_html=pathlib.Path("reports/<WORKFLOW>/<DATE>.html"),
    history_path=pathlib.Path("reports/<WORKFLOW>/_history.jsonl"),
    topic_env="<TELEGRAM_TOPIC_ENV_VAR_NAME>",
)
print("notify ok")
PY
```

Replace `<WORKFLOW>` / `<DATE>` / `<TELEGRAM_TOPIC_ENV_VAR_NAME>` with the actual values. The function picks `_brief.md` over history-derived summary if it exists next to the HTML.

If the Telegram call returns non-200, the script logs to stderr. Surface that to the user — don't pretend success.

### 3. History (optional, recommended skip for skill runs)

If `cfg.history` is declared, the launchd-driven run uses Haiku to summarize into `_history.jsonl`. For skill runs this is optional:

- **Skip** by default — the report HTML is the artifact, history is auxiliary
- **Or write one line manually** to `reports/<WORKFLOW>/_history.jsonl` with the fields specified in `cfg.history.fields`. **Strings in Traditional Chinese (繁體中文). Any `confidence` / `avg_confidence` field on the 0-10 scale.** Anything else breaks tomorrow's diff.

If you skip, mention it in the wrap-up so the user knows tomorrow's diff won't reference today.

## Wrap up

Report to the user:

1. HTML path + size
2. PDF path (or `(post.pdf=false, skipped)`)
3. Telegram result (`200 / message_id N / thread M` or error text)
4. History decision (written / skipped)

## Hard rules

- **NEVER** spawn `claude -p`, **NEVER** run `run-workflow.py`. The whole point of this skill is that it stays inline so the work bills against the interactive subscription pool (post-2026-06-15 Anthropic billing split).
- `faithfulness.md` rules dominate everything. Inference labelled as inference; no fabricated numbers; cite sources for quotations.
- If any required MCP is missing from this session, stop and tell the user — do not run partial / mock.
- If a `web-fetch` / `yt-dlp` / `rss` source returns nothing, mark that section "資料不可用,本次跳過" in the HTML and continue. Don't abort the whole report for one source failure.
- Do not run a different workflow than `args` says. If you suspect the user wanted a different one, ask first.

## Why this skill exists (context)

Anthropic 2026-06-15: `claude -p` headless + Agent SDK + Claude Code GitHub Actions move from subscription limits to a separate monthly dollar credit (Pro $20 / Max 5x $100 / Max 20x $200, API rates, no rollover). Interactive Claude Code terminal sessions are explicitly NOT affected.

This skill turns each finance-workflow into something runnable from an interactive session, eligible for two billing strategies:

1. **Manual** — `cd /Users/pochenkuo/AI/new_financial-report-system && claude` → `/finance-loop crypto-daily`. Cleanest, stays on subscription, but requires you to remember to run it.
2. **`/loop <interval>` inside a tmux'd `claude` session** — `/loop 1d /finance-loop crypto-daily`. Automated but billing classification of `/loop` is **not officially confirmed** as of writing — could still fall into the new credit pool. The plan is: after 2026-06-15, do one or two `/loop` runs and check Anthropic's usage dashboard to see which pool they hit. If subscription: migrate all 3 daily workflows. If new pool: stay with launchd `claude -p` since the result is equivalent and launchd is more reliable than a tmux'd long-running claude session.

Either way, `deep-stock-research` is the one workflow that **shouldn't** use this skill for routine runs — its watchlist varies week to week, so manual `/deep-research-stock <tickers>` is the right pattern there. Reserve `/finance-loop deep-stock-research` for "run today's default watchlist exactly as the workflow JSON declares it".
