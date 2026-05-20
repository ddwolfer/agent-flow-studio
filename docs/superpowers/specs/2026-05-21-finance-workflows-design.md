# finance-workflows — Lean Workflow Runner Design Spec

**Date:** 2026-05-21 · **Status:** approved direction; run-to-completion authorised
**Topic:** Replace `studio/` (Next.js + ReactFlow UI + complex runner) with a thin Python runner driven by per-workflow JSON files. Start fresh with a crypto-daily workflow; migrate Eason later.

---

## 1. Why (with what we explicitly abandon)

The honest reality after a long iteration cycle on `studio/`:

- **The UI was over-engineered for one user.** Reports are read from `runs/<id>/report.html`, not the canvas. Live progress / RunBar / SidePanel pulled meaningful complexity for marginal day-to-day value.
- **The Eason-shaped pipeline doesn't generalise.** Crypto, US-macro, and news workflows don't fit `digest pass → analysis → postprocess (picks) → quality` cleanly. We already saw it with 游庭皓 (no picks, different sections, `/eason-analysis` skill awkward).
- **DB picks tracking is not wanted** (user-confirmed). That alone deletes `eason_training`/`eason_daily`/`eason_picks`, `persistence.md`, the picks Haiku step, and `mcp__sqlite__*` — a whole layer.
- **In 2026, Claude inside Claude Code CLI handles long tool results and multi-step planning natively** — much of the two-pass digest gymnastics existed to work around earlier `claude -p` limits. We can express most of that complexity *out* by writing simpler, higher-level prompts and letting Claude do the chunking.

What we keep: the Python MCP servers, the prompt-engineering know-how (faithfulness rules, transcript-driven analysis, no-fabrication discipline), and the lesson that adding analysts must be config-only.

What's locked (from brainstorm answers):

1. **Auto-cron required** — workflows must be runnable headlessly so we can have morning briefings.
2. **Multi-domain** — crypto YouTubers + crypto news (zombit.info) + US-macro + current TW-stock (Eason). 5–10 workflows over time.
3. **DB picks dropped.** Reports stateless by default. History is **opt-in per workflow** as a thin JSONL append (not SQLite).
4. **Python**, not TypeScript. Stack consistency with existing MCP servers; the only argument for TS was a future UI we no longer want.

## 2. Locked scope vs deferred

### MVP (this spec)
- New parallel top-level dir `finance-workflows/`. **`studio/` is NOT deleted** — left in place, archived later once new structure proves out (no flag day).
- One end-to-end workflow: **`crypto-daily`** using `@crypto_punks` + `@BTV_CN` YouTubers + `zombit.info` news.
- Python runner `run-workflow.py` driving headless `claude -p` (subprocess) with the workflow's MCP set + concatenated prompts.
- MCP servers needed: reuse `yt-dlp` (copy from studio/mcp), add new `rss` (feedparser) and `web-fetch` (httpx + readability) servers. Drop `twse`/`yahoo`/`fred`/`sqlite` for this workflow.
- Prompts: a shared `prompts/shared/faithfulness.md` + a `prompts/crypto/` set (framework, voice, main, digest, transcript).
- Output: `reports/crypto-daily/{YYYY-MM-DD}.html`.
- Optional history: `reports/crypto-daily/_history.jsonl` (one line per run with the workflow-declared fields).
- A `CLAUDE.md` at `finance-workflows/` root explaining how to add a workflow.
- A `cron.example.sh` showing how to schedule.

### Deferred (NOT in this spec)
- Eason migration to the new shape (separate later FU). The current `studio/`-based Eason flow keeps running unchanged in parallel.
- US-macro and macro-news workflows.
- Source ingestion cache decoupled from workflow run (each workflow currently fetches its own sources; cache layer only if/when 2+ workflows actually share sources).
- Web/PDF post-processing beyond the existing Chrome-headless pattern (keep reusing it).
- Any UI of any kind. Reports are opened from the filesystem.

## 3. Architecture (data flow)

```
cron / manual ──► run-workflow.py <name>
                          │
                          │ reads
                          ▼
            finance-workflows/workflows/<name>.json
                          │
                          │ (renders mcp.json with only the workflow's tools,
                          │  concatenates prompts into a single -p invocation,
                          │  substitutes ${DATE}/${OUTPUT_PATH}/etc.)
                          ▼
                  subprocess.run(
                    ["claude", "-p", PROMPT,
                     "--model", model,
                     "--mcp-config", mcp.json,
                     "--strict-mcp-config",
                     "--allowedTools", "...",
                     "--max-turns", N],
                    cwd=finance-workflows/)
                          │
                          │  Claude inside this turn:
                          │   - calls MCP tools to fetch sources
                          │   - writes report HTML to ${OUTPUT_PATH}
                          ▼
              reports/<name>/{date}.html
                          │
                          │ (if workflow.history: runner asks Claude for a
                          │  one-line JSON summary → appends to _history.jsonl)
                          ▼
              reports/<name>/_history.jsonl
                          │
                          │ (post step: headless Chrome → PDF, optional)
                          ▼
              reports/<name>/{date}.pdf
```

No background server, no API routes, no UI, no SQLite, no shallow-merged run.json state machine. The runner is one Python file; the workflow definition is one JSON file; the report is one HTML file.

## 4. workflow.json schema (concrete)

```json
{
  "$schema_version": 1,
  "name": "crypto-daily",
  "description": "Daily crypto + crypto-adjacent macro briefing",
  "model": "claude-sonnet-4-6",
  "max_turns": 60,
  "sources": [
    { "kind": "youtube", "handle": "@crypto_punks", "search_query": "crypto_punks" },
    { "kind": "youtube", "handle": "@BTV_CN", "search_query": "BTV_CN" },
    { "kind": "web", "name": "zombit", "url": "https://zombit.info/", "rss": "https://zombit.info/feed/" }
  ],
  "tools": ["yt-dlp", "rss", "web-fetch"],
  "prompts": [
    "prompts/shared/faithfulness.md",
    "prompts/crypto/framework.md",
    "prompts/crypto/voice.md",
    "prompts/crypto/main.md"
  ],
  "output": "reports/crypto-daily/{date}.html",
  "post": { "pdf": true },
  "history": {
    "format": "jsonl",
    "summarize_with": "claude-haiku-4-5",
    "fields": ["overall_stance", "confidence", "top_signals", "top_risks"]
  }
}
```

Validated at runner load-time with a Python dataclass + `pydantic` (small, optional dep) or a hand-written validator (no dep — fine for MVP).

- `model` / `max_turns` map directly to `claude -p` args.
- `sources` is a list whose `kind` informs which MCP tools are wired and how the prompts can reference them. The schema is open-ended on purpose (new `kind` = new MCP server + prompt support).
- `tools` is the **per-workflow MCP allow-list** (analogous to `allowed_tools` in studio's per-pipeline yaml). The runner builds an `mcp.json` containing **only these MCP servers**, and passes `--allowedTools` listing every tool exported by them + `Write` + `Read`.
- `prompts` are read top-to-bottom and concatenated (with token substitution) into one `-p` body. The shared faithfulness block goes first.
- `output` uses `{date}` substitution → `runs/...{YYYY-MM-DD}.html` style.
- `post.pdf` = run Chrome headless after `claude` finishes (reuses the proven invocation from studio).
- `history` is **optional**. If absent, no history file is written.

## 5. File structure

```
finance-workflows/
├── workflows/
│   └── crypto-daily.json            ← MVP's one workflow
├── mcp/
│   ├── mcp.json.tmpl                ← rendered to mcp.json per run
│   ├── .venv/                       ← shared Python venv for all MCP servers
│   └── servers/
│       ├── ytdlp_server.py          ← copied from studio/mcp/servers/ (proven)
│       ├── rss_server.py            ← NEW (feedparser)
│       └── web_fetch_server.py      ← NEW (httpx + readability-lxml)
├── prompts/
│   ├── shared/
│   │   └── faithfulness.md          ← write-rules common to every workflow
│   └── crypto/
│       ├── framework.md             ← crypto top-down: BTC dominance, on-chain, sentiment, macro tie-ins
│       ├── voice.md                 ← analytic, data-driven, not shilly
│       └── main.md                  ← report structure + workflow steps
├── reports/
│   └── crypto-daily/
│       ├── 2026-05-21.html
│       ├── 2026-05-21.pdf
│       └── _history.jsonl
├── run-workflow.py                  ← the runner (≤200 LoC target)
├── cron.example.sh                  ← example cron entries
├── CLAUDE.md                        ← how to add a workflow
├── pyproject.toml                   ← runner + MCP server deps
└── README.md
```

Top-level repo (after this MVP) looks like:

```
new_financial-report-system/
├── studio/                          ← OLD, still working, will be archived after new shape proves
├── financial-report-system/         ← inherited legacy (unchanged)
├── finance-workflows/               ← NEW (this spec)
└── docs/
```

## 6. Component responsibilities

### `run-workflow.py` (≤ 200 LoC target)

Inputs: a workflow name (CLI arg).

Steps:
1. Load `workflows/<name>.json`, validate.
2. Render `mcp/mcp.json` from `mcp.json.tmpl` containing only the servers in `workflow.tools` (FRED key etc. injected from a `.env` if any server needs it; if env var missing, omit that server and warn — gracefully degraded).
3. Read all `workflow.prompts` files in order, concatenate.
4. Substitute placeholders (two distinct conventions):
   - **Path-template** (used only in workflow.json `output:` field): `{date}` → today's ISO date. Resolved by the runner BEFORE invoking Claude.
   - **Prompt-text** (used inside `.md` prompt files): `${DATE}` → today's ISO; `${OUTPUT_PATH}` → absolute resolved HTML path; `${SOURCES_JSON}` → `json.dumps(workflow.sources, ensure_ascii=False)`; `${WORKFLOW_NAME}` → the workflow's `name`.
5. Build the `claude` argv: `claude -p PROMPT --model ... --max-turns ... --mcp-config mcp.json --strict-mcp-config --allowedTools <derived>` (derived = every tool from each MCP server in `workflow.tools` + `Write` + `Read`, no `*` ever).
6. `subprocess.run(...)` from the `finance-workflows/` working dir; tee stdout/stderr to `reports/<name>/_logs/{date}-{ts}.log`.
7. If `workflow.post.pdf` and HTML exists → `chrome --headless --print-to-pdf=... ...html`.
8. If `workflow.history` declared and HTML exists → second tiny `claude -p` call with a Haiku model and a strict "produce ONLY a single-line JSON with these fields: ..." instruction, append the result to `_history.jsonl`.
9. Exit 0 on success, non-zero with a clear message on failure.

The runner does NOT track per-stage progress (no run.json state machine). The log file + exit code + file artifacts are the observability surface. If you want to know what happened, you `tail` the log.

### MCP servers (Python FastMCP, same pattern as studio/mcp)

- **`ytdlp_server.py`** — copy verbatim from `studio/mcp/servers/ytdlp_server.py`. Same `ytdlp_search_videos`, `ytdlp_download_transcript`, `ytdlp_transcript_page` tools. Already proven.
- **`rss_server.py`** — single tool `rss_fetch(url, max_items=20)`. Uses `feedparser`. Returns `[{title, link, published, summary, content?}]`.
- **`web_fetch_server.py`** — two tools:
  - `web_fetch(url)` → `{status, content_type, text}` (raw fetch via `httpx`, with a sane user-agent, 30s timeout, follows redirects).
  - `web_extract_article(url)` → `{title, byline, published, text_markdown}` (readability extraction via `readability-lxml` + `markdownify`).

Security: web-fetch is **arbitrary internet access**. We accept that for a single-user local tool; we do NOT add domain whitelisting in MVP (it's a friction trap). Document the trust assumption in CLAUDE.md.

### Prompts (the actual product)

- `prompts/shared/faithfulness.md` — no-fabrication rules, only-what-source-said discipline, "原因不明，持續觀察" fallback. Reused across all workflows.
- `prompts/crypto/framework.md` — top-down crypto framework: BTC dominance, ETH/BTC ratio, total supply, sector flows (DeFi/L2/AI tokens), macro tie-ins (DXY, real yields, Fed expectations).
- `prompts/crypto/voice.md` — analytic, neutral, *not* shilly, no "to the moon" rhetoric, label uncertainty.
- `prompts/crypto/main.md` — concrete steps: use `ytdlp_search_videos` for each YT handle to find latest, page transcripts with `ytdlp_transcript_page`, use `rss_fetch` on zombit to read today's articles, use `web_extract_article` for headlines that look macro-relevant, then synthesise a 5-section report (市場快照 / 加密總覽 / 影片+文章重點 / 風險 / 報告總結), write HTML to `${OUTPUT_PATH}`.

No `transcript.md` / `digest.md` two-pass machinery — we trust modern Claude to chunk a 13k-char transcript on its own. We can re-introduce a two-pass if a real run shows it's needed; YAGNI for the spec.

## 7. crypto-daily concrete details

- **YouTube sources**: `@crypto_punks` and `@BTV_CN` (both confirmed daily-update). Searched via `ytdlp_search_videos` with `search_query` = handle name; main.md instructs Claude to pick today's video if any, else most recent.
- **News source**: `zombit.info`. Try RSS first (`https://zombit.info/feed/` — common WordPress convention; runner does NOT validate, the rss MCP returns empty list if URL 404s and main.md falls back to `web_extract_article` on the homepage to find article links).
- **Allowed tools** (derived from `tools: ["yt-dlp", "rss", "web-fetch"]`):
  - `mcp__yt-dlp__ytdlp_search_videos`
  - `mcp__yt-dlp__ytdlp_download_transcript`
  - `mcp__yt-dlp__ytdlp_transcript_page`
  - `mcp__rss__rss_fetch`
  - `mcp__web-fetch__web_fetch`
  - `mcp__web-fetch__web_extract_article`
  - `Write`
  - `Read`
- **Model**: `claude-sonnet-4-6`. `max_turns: 60` (more than studio's 50 because the workflow is doing fetch+synthesis in one pass, not split across two passes).
- **History fields**: `overall_stance` (偏多/中性/偏空), `confidence` (0–10), `top_signals` (≤3), `top_risks` (≤3) — extracted by Haiku from the produced HTML.

## 8. Migration path / studio/ relationship

- `studio/` continues to work; no change required.
- This MVP introduces `finance-workflows/` alongside. **Both can run.** Eason still goes through `studio/` via the canvas + the proven runner.
- Once 2–3 new workflows in `finance-workflows/` are running daily and proven, **migrate Eason** as a separate FU: convert `studio/config/pipelines/eason.yaml` + `studio/prompts/eason/*` into `finance-workflows/workflows/eason-tw-stock.json` + `finance-workflows/prompts/tw-stock/*`. At that point archive `studio/` (move to `archive/studio/`, leave README pointing to new shape).
- No flag day. No service interruption. Git can revert anything.

## 9. Error handling

- Workflow JSON validation fails → exit 2 with the validation error.
- mcp.json render fails (e.g. missing API key) → log warning, render mcp.json with the available servers only, continue (graceful degrade — Claude will say it couldn't reach that data).
- `claude -p` non-zero exit → exit code mirrored; logs preserved.
- Chrome PDF fail → log warning, HTML report still counts as success.
- History step fail → log warning, HTML report still counts as success (history is opt-in/non-critical).

No silent failures; every degraded path writes to the log. The exit code reflects only whether the HTML report was written.

## 10. Honest limitations (not glossed)

- **`web_fetch` is unrestricted internet access.** Document the trust assumption in CLAUDE.md; we accept it for a local single-user tool. Future option: per-workflow URL allow-list, but not in MVP.
- **No retries on transient failures** (the same `claude -p socket closed` issue we saw on `studio`). MVP behaviour: log and exit non-zero; cron's natural daily retry cycle handles it. If transient failures become common, add a 1-retry wrapper in the runner.
- **No source caching.** If two workflows reference the same source, both fetch independently. We accept the duplication until we have 2+ workflows actually sharing sources.
- **No web preview of `_history.jsonl` trends.** It's a file you `tail` or `jq`. If we want a trend view later, a one-off Python script can render it; we don't add a service.
- **PDF generation depends on macOS Chrome at the known path.** Same constraint as studio. Cross-platform later if needed.
- **First-time `claude -p` runs from cron may need `claude` to already be authenticated.** Document this in CLAUDE.md ("run `claude` interactively once before cron").

## 11. Acceptance criteria (MVP done = all hold)

1. `python3 finance-workflows/run-workflow.py crypto-daily` exits 0 and produces `reports/crypto-daily/{today}.html` containing the 5 required sections and citing real content from the 2 YT channels + zombit.
2. `reports/crypto-daily/{today}.pdf` exists (Chrome headless ran).
3. `reports/crypto-daily/_history.jsonl` has a new line with the 4 declared fields.
4. `_logs/{today}-{ts}.log` shows the full claude stdout/stderr.
5. Adding a 2nd workflow (say, a US-macro stub) is **just**: drop `workflows/us-macro.json` + `prompts/us-macro/*` + (maybe) one new MCP server. No edits to `run-workflow.py` or any other workflow.
6. `studio/` still runs Eason unchanged (zero collision).
7. `finance-workflows/` `CLAUDE.md` answers: how to add a workflow, how to add a source kind, how to add a MCP server, how to schedule cron.
