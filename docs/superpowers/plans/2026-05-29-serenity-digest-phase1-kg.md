# Serenity Digest Phase 1 + KG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `serenity-digest` as the 5th finance-workflows workflow — scrapes `analysissite.vercel.app` daily at 06:00 TPE, produces an HTML archive + a Telegram-bound Markdown brief with Tier 1/2/3 + 相關訊號 layout, and reads/writes the project's knowledge-graph MCP from day 1.

**Architecture:** Folds into the existing `run-workflow.py` orchestrator as `workflows/serenity-digest.json` + `prompts/serenity-digest/{framework,voice,main}.md`. Two paired runner extensions support it: (a) `mcp_render` gains an `@ROOT@` substitution so workflow MCPs can reach `mcp/knowledge-graph` which lives one level above `finance-workflows/`; (b) `notify_telegram.py` learns to prefer a co-located `_brief.md` as the Telegram body when present. `claude -p` is invoked with `--bare` to disable the project-level Claude Code hooks (which would otherwise spawn an Opus auto-capture session per workflow run). All KG calls are prompt-driven, not hook-driven.

**Tech Stack:** Python 3 (existing finance-workflows runner), Node.js (existing knowledge-graph MCP server), Claude CLI (`claude -p`), `web-fetch` MCP for scraping, `knowledge-graph` MCP for retrieval/storage, launchd for daily scheduling, Telegram Bot API for delivery.

**Background:** Reference spec lives at `serenity-digest-spec/`. KG MCP schema was verified to enforce anti-fabrication (principle requires quote; inference cannot create must_precede/reason_for edges) — see `mcp/knowledge-graph/tools/knowledge-tools.js:30-35,136-145`. Hooks live in `.claude/settings.json` at project root and would otherwise fire inside the workflow subprocess. Existing TELEGRAM_TOPIC_* env-var convention is reused.

---

## File Structure

### Create
- `finance-workflows/workflows/serenity-digest.json` — workflow config (sources, tools, model, post)
- `finance-workflows/prompts/serenity-digest/framework.md` — domain framework (tier rule, news 0-100 scoring, KG mapping)
- `finance-workflows/prompts/serenity-digest/voice.md` — voice rules + anti-pattern banned phrases
- `finance-workflows/prompts/serenity-digest/main.md` — orchestration prompt (fetch → diff → KG retrieve → score → HTML → _brief.md → KG write)
- `finance-workflows/tests/test_serenity_workflow_loads.py` — smoke test that workflow JSON loads without error
- `~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist` — daily 06:00 cron

### Modify
- `finance-workflows/mcp_render.py` — add `@ROOT@` substitution + new `root_dir` kwarg
- `finance-workflows/tests/test_mcp_render.py` — add tests for `@ROOT@` substitution
- `finance-workflows/mcp/mcp.json.tmpl` — add `knowledge-graph` entry using `@ROOT@`
- `finance-workflows/run-workflow.py` — pass `root_dir=str(root.parent)` to render_mcp; add `knowledge-graph` to TOOL_MAP; add `--bare` to claude argv
- `finance-workflows/scripts/notify_telegram.py` — prefer co-located `_brief.md` over history-based summary
- `finance-workflows/tests/test_notify_telegram.py` — add tests for `_brief.md` preference behaviour
- `finance-workflows/.env` — add `TELEGRAM_TOPIC_SERENITY=<id>` (user-supplied value)

### Not modified
- `.claude/settings.json` — hooks remain configured for the main Claude Code session; workflow uses `--bare` to skip them
- Existing 4 workflows (`crypto-daily`, `eason-tw-stock`, `us-macro`, `deep-stock-research`) — they automatically gain KG access via the TOOL_MAP/template change, but their own `tools` lists don't include `knowledge-graph` so they're unaffected at runtime

---

## Architectural decisions baked into this plan

1. **Day-1 KG read+write** (option C from prior discussion) — KG MCP enforces the anti-fab schema server-side, so writes are safe.
2. **Source tagging convention**: every Serenity-written node uses `source="serenity-digest"` and `metadata={"workflow": "serenity-digest", "site": "analysissite", "ticker": "<T>"}`. This is a soft separation (search_memory doesn't filter on metadata), but enables `list_knowledge`-based audits.
3. **Hard daily caps**: ≤20 `store_knowledge` calls, ≤30 `connect_knowledge` calls per run, enforced by the prompt and surfaced as policy. Matches `serenity-digest-spec/docs/04-daily-workflow.md` Step G.
4. **`--bare` is applied to *all* workflows**, not just Serenity. Other workflows weren't using hooks for value anyway (the auto-capture Opus call after each run was an unintended cost).
5. **Persona Layer (`SKILL.md` distillation) deferred** — requires ~30 days of accumulated snapshots per the spec. Phase 1 runs in "樸素模式".
6. **Weekly/monthly/quarterly cadences deferred** — not in user's ask.
7. **Reports live at `finance-workflows/reports/serenity-digest/`**, NOT `~/Desktop/serenity-digest/`. Consistent with existing 4 workflows; spec's Desktop location was for a different host architecture.
8. **`_brief.md` is the Telegram body**; HTML is the archive. PDF disabled for this workflow (the brief is short and Markdown-native).

---

## Task 1: `@ROOT@` substitution in mcp_render

**Files:**
- Modify: `finance-workflows/mcp_render.py:10-46`
- Test: `finance-workflows/tests/test_mcp_render.py` (add 2 tests)

**Why this task first:** `mcp/knowledge-graph/main.js` lives at the project root, one level above `finance-workflows/`. The existing `@MCPDIR@` placeholder only covers `finance-workflows/mcp/`. We need a clean way to reach above without hard-coding absolute paths in the template.

- [ ] **Step 1: Write the failing tests**

Add two test functions at the end of `finance-workflows/tests/test_mcp_render.py`:

```python
def test_render_substitutes_root(tmp_path):
    """@ROOT@ in args resolves to root_dir, distinct from @MCPDIR@."""
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "kg": {"command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"]}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["kg"], mcp_dir=str(tmp_path / "fw" / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out,
                 root_dir=str(tmp_path / "root"))
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["kg"]["args"][0] == \
        f"{tmp_path / 'root'}/mcp/knowledge-graph/main.js"


def test_render_root_unset_leaves_placeholder_literal(tmp_path):
    """If root_dir is None, @ROOT@ stays literal (parallel to env_subs behaviour)
    so a misconfigured caller fails loud at MCP startup, not silently."""
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"
    tmpl.write_text("""{
      "mcpServers": {
        "kg": {"command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"]}
      }
    }""", "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["kg"], mcp_dir=str(tmp_path / "fw" / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out)
    cfg = json.loads(out.read_text("utf-8"))
    assert cfg["mcpServers"]["kg"]["args"][0] == \
        "@ROOT@/mcp/knowledge-graph/main.js"
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `mcp/.venv/bin/python -m pytest tests/test_mcp_render.py -v -k "root"` (from `finance-workflows/`)
Expected: 2 tests FAIL — `test_render_substitutes_root` errors with `TypeError: render_mcp() got an unexpected keyword argument 'root_dir'`; `test_render_root_unset_leaves_placeholder_literal` passes accidentally (no substitution attempted) or fails. Confirm the first fails for the right reason.

- [ ] **Step 3: Implement `@ROOT@` substitution**

Edit `finance-workflows/mcp_render.py`. Change the `render_mcp` signature and body:

```python
def render_mcp(*, tools, mcp_dir, python_bin, tmpl_path, out_path,
               env_subs=None, root_dir=None):
    """Read tmpl, parse JSON, retain only the requested server keys, substitute
    @PY@/@MCPDIR@/@ROOT@ in command/args and any `@KEY@` from `env_subs` in env
    values, write to out_path. Returns the absolute out_path as a string.

    @ROOT@ is the project root (one level above finance-workflows/), used by
    MCPs that live outside finance-workflows (e.g. mcp/knowledge-graph).

    Servers whose template has an env entry referencing `@KEY@` but `env_subs`
    does not include that KEY are still rendered — their `@KEY@` placeholder
    remains literal so failures are visible at MCP startup rather than silent.
    @ROOT@ follows the same rule: if root_dir is None, it stays literal.

    Raises McpRenderError if any requested tool isn't in the template.
    """
    tmpl = json.loads(pathlib.Path(tmpl_path).read_text("utf-8"))
    available = set(tmpl.get("mcpServers", {}).keys())
    unknown = [t for t in tools if t not in available]
    if unknown:
        raise McpRenderError(f"unknown MCP server(s) in workflow.tools: {unknown}; "
                             f"template has: {sorted(available)}")
    env_subs = env_subs or {}
    rendered = {"mcpServers": {}}
    for name in tools:
        entry = json.loads(json.dumps(tmpl["mcpServers"][name]))  # deep copy
        entry["command"] = entry["command"].replace("@PY@", python_bin)
        def _sub(s):
            s = s.replace("@MCPDIR@", mcp_dir).replace("@PY@", python_bin)
            if root_dir is not None:
                s = s.replace("@ROOT@", root_dir)
            return s
        entry["args"] = [_sub(a) for a in entry.get("args", [])]
        if "env" in entry:
            new_env = {}
            for k, v in entry["env"].items():
                vs = v
                for sk, sv in env_subs.items():
                    vs = vs.replace(f"@{sk}@", sv)
                new_env[k] = vs
            entry["env"] = new_env
        rendered["mcpServers"][name] = entry
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rendered, indent=2, ensure_ascii=False), "utf-8")
    return str(out)
```

- [ ] **Step 4: Run the new tests to confirm they pass**

Run: `mcp/.venv/bin/python -m pytest tests/test_mcp_render.py -v` (from `finance-workflows/`)
Expected: all mcp_render tests PASS (the 5 original + 2 new = 7).

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run: `mcp/.venv/bin/python -m pytest tests/ -v` (from `finance-workflows/`)
Expected: all previously-passing tests still pass. `run-workflow.py` does not yet call `render_mcp` with `root_dir` — that's the next task — but its existing tests should still work because `root_dir` has a default of `None`.

- [ ] **Step 6: Commit**

```bash
git add finance-workflows/mcp_render.py finance-workflows/tests/test_mcp_render.py
git commit -m "$(cat <<'EOF'
feat(mcp_render): add @ROOT@ substitution for MCPs outside finance-workflows

The knowledge-graph MCP lives at <project-root>/mcp/knowledge-graph/, one
level above finance-workflows/. @MCPDIR@ only covers finance-workflows/mcp/,
so workflows that want KG need a way to reach the project root without
hard-coding absolute paths in the template. @ROOT@ fills that gap. Like
@KEY@ env subs, it stays literal when unset so misconfiguration fails loud
at MCP startup rather than masquerading as a missing file.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 2: Wire `root_dir` from run-workflow.py + register knowledge-graph in the template

**Files:**
- Modify: `finance-workflows/run-workflow.py:17-40, 198-205`
- Modify: `finance-workflows/mcp/mcp.json.tmpl`

- [ ] **Step 1: Pass `root_dir` into `render_mcp`**

In `finance-workflows/run-workflow.py`, change the `render_mcp` call. Locate the block at lines 201-207:

```python
    try:
        mcp_json_path = render_mcp(tools=cfg.tools, mcp_dir=mcp_dir,
                                   python_bin=_python_bin(root),
                                   tmpl_path=tmpl, out_path=out_mcp,
                                   env_subs=_load_env_subs(root))
    except (FileNotFoundError, McpRenderError) as e:
        print(f"[mcp_render] {e}", file=sys.stderr); return 3
```

Replace with:

```python
    try:
        mcp_json_path = render_mcp(tools=cfg.tools, mcp_dir=mcp_dir,
                                   python_bin=_python_bin(root),
                                   tmpl_path=tmpl, out_path=out_mcp,
                                   env_subs=_load_env_subs(root),
                                   root_dir=str(root.parent))
    except (FileNotFoundError, McpRenderError) as e:
        print(f"[mcp_render] {e}", file=sys.stderr); return 3
```

`root` here is `finance-workflows/`; `root.parent` is the project root where `mcp/knowledge-graph/` lives.

- [ ] **Step 2: Add `knowledge-graph` to TOOL_MAP**

In `finance-workflows/run-workflow.py`, add an entry to `TOOL_MAP` (around lines 17-40). Place after the `"edgar"` entry:

```python
    "knowledge-graph": [
        "store_knowledge", "connect_knowledge", "update_knowledge",
        "forget_knowledge", "search_memory", "get_knowledge",
        "list_knowledge", "traverse_graph",
        "record_experience", "recall_experience",
        "maintain_graph", "memory_stats",
    ],
```

These are the 12 tools defined in `mcp/knowledge-graph/tools/`.

- [ ] **Step 3: Register `knowledge-graph` in mcp.json.tmpl**

Edit `finance-workflows/mcp/mcp.json.tmpl`. Add a new entry after `"edgar"`:

```json
    "edgar":         { "command": "@PY@", "args": ["@MCPDIR@/servers/edgar_server.py"] },
    "knowledge-graph": { "command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"] }
```

Watch JSON commas. The file becomes:

```json
{
  "mcpServers": {
    "yt-dlp":        { "command": "@PY@", "args": ["@MCPDIR@/servers/ytdlp_server.py"] },
    "rss":           { "command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"] },
    "web-fetch":     { "command": "@PY@", "args": ["@MCPDIR@/servers/web_fetch_server.py"] },
    "fred":          { "command": "@PY@", "args": ["@MCPDIR@/servers/fred_server.py"], "env": { "FRED_API_KEY": "@FREDKEY@" } },
    "yahoo-finance": { "command": "@PY@", "args": ["@MCPDIR@/servers/yahoo_server.py"] },
    "twse":          { "command": "@PY@", "args": ["@MCPDIR@/servers/twse_server.py"] },
    "edgar":         { "command": "@PY@", "args": ["@MCPDIR@/servers/edgar_server.py"] },
    "knowledge-graph": { "command": "node", "args": ["@ROOT@/mcp/knowledge-graph/main.js"] }
  }
}
```

- [ ] **Step 4: Verify rendering manually with a one-liner**

Run from `finance-workflows/`:

```bash
mcp/.venv/bin/python -c "
import sys, pathlib, json
sys.path.insert(0, '.')
from mcp_render import render_mcp
out = render_mcp(tools=['knowledge-graph'], mcp_dir='/abs/mcp',
                 python_bin='/abs/py',
                 tmpl_path=pathlib.Path('mcp/mcp.json.tmpl'),
                 out_path=pathlib.Path('/tmp/mcp-kg-test.json'),
                 root_dir='/abs/root')
print(open(out).read())
"
```

Expected output: a JSON whose `args[0]` is `"/abs/root/mcp/knowledge-graph/main.js"`. Confirm the path resolves to `mcp/knowledge-graph/main.js` relative to the substituted root.

Then delete the scratch file: `rm /tmp/mcp-kg-test.json`.

- [ ] **Step 5: Run the full test suite**

Run: `mcp/.venv/bin/python -m pytest tests/ -v` (from `finance-workflows/`)
Expected: all tests PASS. Existing tests still don't request `knowledge-graph` so behaviour is unchanged for them.

- [ ] **Step 6: Commit**

```bash
git add finance-workflows/run-workflow.py finance-workflows/mcp/mcp.json.tmpl
git commit -m "$(cat <<'EOF'
feat(mcp): register knowledge-graph MCP for workflow access

Wires the project-root knowledge-graph MCP server into the workflow MCP
template using the new @ROOT@ substitution. TOOL_MAP picks up the 12 tools
the server exports (store/search/connect/forget + experience + maintenance).
Existing workflows don't declare "knowledge-graph" in their tools list, so
this is a no-op for them. Upcoming serenity-digest workflow will consume it.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 3: Add `--bare` to the claude invocation

**Files:**
- Modify: `finance-workflows/run-workflow.py:223-230`

**Why:** The project-root `.claude/settings.json` registers hooks (auto-recall on prompt, search-enforcer on PreToolUse, Opus auto-capture on Stop, session-start). These are intended for the main Claude Code session, not for headless `claude -p` workflow runs. The Stop hook in particular spawns a `claude-opus-4-6` agent on every workflow exit, which is a per-day cost we never wanted. `--bare` is the documented switch to skip hooks/LSP/plugins.

- [ ] **Step 1: Add `--bare` to the argv**

In `finance-workflows/run-workflow.py`, locate the `argv_` construction near line 225:

```python
    argv_ = [bin_, "-p", prompt,
            "--model", cfg.model,
            "--max-turns", str(cfg.max_turns),
            "--mcp-config", str(mcp_json_path),
            "--strict-mcp-config",
            "--allowedTools", ",".join(allowed)]
```

Replace with:

```python
    argv_ = [bin_, "-p", prompt,
            "--model", cfg.model,
            "--max-turns", str(cfg.max_turns),
            "--mcp-config", str(mcp_json_path),
            "--strict-mcp-config",
            # --bare skips Claude Code hooks (session-start, auto-recall,
            # search-enforcer, Stop=auto-capture). Workflows are headless
            # batch jobs; hooks were never the cost we wanted to pay per run.
            # KG access is via the MCP server above, called explicitly from
            # the workflow's prompt (no hook needed).
            "--bare",
            "--allowedTools", ",".join(allowed)]
```

- [ ] **Step 2: Verify the `claude --help` recognises `--bare`**

Run: `claude --help 2>&1 | grep -E "^\s+--bare"`
Expected: a line like `  --bare                                Minimal mode: skip hooks, LSP, plugin...`. Confirms the flag exists.

- [ ] **Step 3: Run the full test suite**

Run: `mcp/.venv/bin/python -m pytest tests/ -v` (from `finance-workflows/`)
Expected: all PASS. The existing `test_run_workflow.py` retry tests use an injected `runner`, so they don't depend on argv shape.

- [ ] **Step 4: Commit**

```bash
git add finance-workflows/run-workflow.py
git commit -m "$(cat <<'EOF'
fix(run): pass --bare to claude so workflow runs skip Claude Code hooks

The project's .claude/settings.json registers session-start / auto-recall /
search-enforcer / Stop=auto-capture hooks meant for interactive Claude Code
sessions. Headless workflow runs were also firing them — most damagingly,
the Stop hook spawned an extra Opus agent after every nightly run, which
was a real per-day cost for zero workflow value. --bare is the documented
switch to disable them. KG access (used by the upcoming serenity-digest
workflow) is via the MCP server, called explicitly from the prompt.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 4: `notify_telegram.py` prefers `_brief.md` over history-based summary

**Files:**
- Modify: `finance-workflows/scripts/notify_telegram.py`
- Test: `finance-workflows/tests/test_notify_telegram.py` (add 2 tests)

**Why:** Serenity needs a specific Tier 1 / Tier 2 / Tier 3 / 相關訊號 layout in its Telegram message — the current generic `📊基調 / 🔑Top signals / ⚠️Top risks` shape doesn't fit. By letting the workflow produce a sibling `_brief.md` and having the notifier prefer it when present, we don't lose the existing history-driven path for the other 4 workflows.

- [ ] **Step 1: Write the failing tests**

Append to `finance-workflows/tests/test_notify_telegram.py`:

```python
def test_brief_md_wins_over_history(monkeypatch, tmp_path):
    """If a _brief.md sits next to the output HTML, its content IS the
    Telegram message body — history-based summary is bypassed."""
    m = _load()
    monkeypatch.setattr(m.httpx, "Client", _FakeClient)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
    monkeypatch.setenv("TELEGRAM_TOPIC_S", "99")
    html = tmp_path / "r.html"; html.write_text("<p>x</p>", "utf-8")
    brief = tmp_path / "_brief.md"; brief.write_text(
        "📊 *Tier 1 NVDA* — testing _brief.md path", "utf-8")
    # history exists but should be ignored
    hist = _write_history(tmp_path, "2026-05-29",
                          {"overall_stance": "SHOULD NOT APPEAR"})
    m.notify("serenity-digest", "2026-05-29", html, hist, "TELEGRAM_TOPIC_S")
    assert len(_FakeClient.posts) == 1  # message only, no PDF
    sent = _FakeClient.posts[0]["data"]["text"]
    assert "Tier 1 NVDA" in sent
    assert "SHOULD NOT APPEAR" not in sent


def test_no_brief_md_falls_back_to_history(monkeypatch, tmp_path):
    """Existing behaviour preserved for workflows without a _brief.md."""
    m = _load()
    monkeypatch.setattr(m.httpx, "Client", _FakeClient)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
    html = tmp_path / "r.html"; html.write_text("<p>x</p>", "utf-8")
    hist = _write_history(tmp_path, "2026-05-29",
                          {"overall_stance": "Bullish baseline"})
    m.notify("us-macro", "2026-05-29", html, hist, None)
    assert len(_FakeClient.posts) == 1
    assert "Bullish baseline" in _FakeClient.posts[0]["data"]["text"]
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `mcp/.venv/bin/python -m pytest tests/test_notify_telegram.py -v -k "brief_md"` (from `finance-workflows/`)
Expected: `test_brief_md_wins_over_history` FAILS — without the implementation, the text will contain `SHOULD NOT APPEAR`. The fallback test passes already.

- [ ] **Step 3: Implement `_brief.md` preference**

Edit `finance-workflows/scripts/notify_telegram.py`. Modify the `notify` function — after computing `hist`, check for `_brief.md` and use it if present. Replace the block starting `hist = _latest_history(...)`:

```python
        hist = _latest_history(pathlib.Path(history_path), date) if history_path else None
        # Prefer a workflow-authored _brief.md sibling to the HTML output. When
        # present it IS the Telegram body, bypassing the history-derived summary.
        # Used by serenity-digest (Tier 1/2/3 layout) and any future workflow
        # that wants a custom Markdown shape.
        brief_md = pathlib.Path(output_html).with_name("_brief.md")
        if brief_md.exists():
            text = brief_md.read_text("utf-8")
        else:
            text = _build_message(workflow_name, date, hist)
        base = {"chat_id": chat}
```

The rest of the function stays unchanged (PDF attachment still goes through normally).

- [ ] **Step 4: Run the notify tests**

Run: `mcp/.venv/bin/python -m pytest tests/test_notify_telegram.py -v` (from `finance-workflows/`)
Expected: all 6 tests PASS (4 original + 2 new).

- [ ] **Step 5: Run the full suite for regressions**

Run: `mcp/.venv/bin/python -m pytest tests/ -v` (from `finance-workflows/`)
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add finance-workflows/scripts/notify_telegram.py finance-workflows/tests/test_notify_telegram.py
git commit -m "$(cat <<'EOF'
feat(telegram): prefer co-located _brief.md as Telegram body when present

Lets a workflow author a custom Markdown shape for its Telegram message
without changing the notifier. When _brief.md sits next to the output HTML,
its raw content becomes the sendMessage text. Otherwise, the existing
history.jsonl-derived summary path is used unchanged — so the 4 existing
workflows are unaffected. Built for serenity-digest's Tier 1/2/3 layout
but reusable by any workflow.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 5: Write Serenity prompts (framework, voice, main)

**Files:**
- Create: `finance-workflows/prompts/serenity-digest/framework.md`
- Create: `finance-workflows/prompts/serenity-digest/voice.md`
- Create: `finance-workflows/prompts/serenity-digest/main.md`

**Why:** This is where the actual Serenity-specific intelligence lives. The other tasks are plumbing; this task is the product.

- [ ] **Step 1: Create the prompts directory**

Run: `mkdir -p finance-workflows/prompts/serenity-digest` (from project root)

- [ ] **Step 2: Write `framework.md`**

Create `finance-workflows/prompts/serenity-digest/framework.md` with this exact content:

```markdown
# Serenity Digest — analytical framework

You are reading `analysissite.vercel.app`, a US-stock KOL aggregator. The site
exposes:

- **priorityQueue (top 3)**: KOL's most actively-flagged tickers today, each
  with a priority number (higher = stronger flag), a stance label, a 1-2
  sentence reasoning summary, and tags.
- **hotStocks (top 10)**: full priority queue.
- **feedItems (10-20 latest)**: timeline of AI/news/discussion items, each
  linked to a ticker, with a badge (e.g. "GPT xhigh", "看多") and a timestamp.
- **metrics**: activeSignals, coverage, delta24h/7d/30d, newsDriven.
- **distribution**: 5-category headcount (觀察, 積極觀察, 高風險觀察,
  謹慎, 高風險偏多).

## Stance vocabulary

The site uses a Chinese stance taxonomy. Map to canonical labels for KG storage:

| Site phrase | Canonical stance |
|---|---|
| 看多 + 高風險偏多 | `bull_high_risk` |
| 中性 + 高風險觀察 | `watch_high_risk` |
| 看多 | `bull` |
| 看空 | `bear` |
| 謹慎 | `caution` |
| 中性 | `neutral` |

Use these in `metadata.stance` when calling `store_knowledge`.

## Tier rule (adaptive)

Decide today's Tier 1 size (3-5 tickers) by the cluster-cutoff rule:

```
top_priority   = priorityQueue[0].priority
cutoff         = top_priority * 0.95
tier1_count    = count(stocks where priority >= cutoff, capped at 5)
tier1_count    = max(tier1_count, 3)
```

If `priorityQueue` is empty (parsing failure), fall back to `hotStocks[:3]`.

Tier 2 = `hotStocks[tier1_count : tier1_count + 8]` (8 entries, short-form).

Tier 3 = diff vs yesterday (computed in Step 2 of main.md).

## News importance score (0-100)

For each feedItem score on five dimensions:

| Dimension | Max | Rule |
|---|---:|---|
| 標的優先級對應度 | 30 | ticker ∈ today's hotStocks → score = 30 - 2×(rank-1). Not in top 10 → 0. |
| 新聞具體性 | 25 | Contains 數字/百分比/公司名/具體事件/日期 → +5 each, cap 25. |
| 來源權威性 | 15 | Reuters/Bloomberg/CNBC/官方公告/SEC → 15; 一般媒體 → 8; 推文/未署名 → 3. |
| 時效性 | 15 | ≤24h → 15; ≤72h → 8; >72h → 0. |
| 與 KG 關係 | 15 | aligns_to / refines an existing KG node for that ticker → 15. contradicts → 15 AND mark with ⚠️ in 相關訊號 段. Unknown → 5. |

Pick **top 3** for the 相關訊號 section. If any scored item has the `contradicts` flag, it is forced into the top 3 regardless of rank.

## KG mapping

The Serenity Digest writes knowledge for two purposes:

1. **Record what the KOL said today** — `trust: principle`, `quote` required.
2. **Record Claude's own extrapolation** — `trust: inference`, NEVER claim it's
   the KOL's view.

Edge usage:

- Today's principle ↔ yesterday's principle (same ticker, stance unchanged, priority ↑): `refines`
- Today's principle ↔ yesterday's principle (same ticker, stance reversed): `contradicts`
- Claude inference → an existing principle node it elaborates: `aligns_to`
- Claude inference → an existing principle node it pushes back on: `contradicts`

**Forbidden** (the KG MCP will reject):
- `must_precede` or `reason_for` edges involving any `trust: inference` node.
- `store_knowledge` with `trust: principle` but no `quote`.

If you can't extract a clean ≤50-character verbatim quote for a KOL view, downgrade `trust` to `pattern` (no quote needed; means you observed it from the site as a pattern, but not literally).

## Daily caps

- ≤ 20 `store_knowledge` calls across the whole workflow run.
- ≤ 30 `connect_knowledge` calls.

Allocate budget like this:
- 5 principle nodes (priorityQueue top 5) — highest priority
- 5-10 edges connecting today's nodes to yesterday's (refines/contradicts)
- 3 inference nodes (your top 3 extrapolations)
- 3-5 edges from inferences to existing principles (aligns_to / contradicts)
- Reserve the rest for unexpected high-value writes.
```

- [ ] **Step 3: Write `voice.md`**

Create `finance-workflows/prompts/serenity-digest/voice.md` with this exact content:

```markdown
# Serenity Digest — voice rules

All Telegram brief content is **Traditional Chinese** (繁體中文). Keep ticker
symbols (NVDA, TSM, etc.) and English proper nouns verbatim. Convert any
Simplified Chinese in source material to Traditional in your output.

## Banned phrases (anti-pattern)

If your draft contains any of the following, REWRITE that sentence before
emitting `_brief.md`. These are the KOL's "what they never say" markers and
also fall under our private-use disclaimer hygiene:

- 強烈推薦 / 强烈推荐 / strong buy
- 目標價 / 目标价 / target price
- 翻倍 / 倍數 / double / 100%
- 必漲 / 必跌 / 必涨 / 必跌 / 穩漲 / 穩跌
- 絕對 / 肯定 / 百分百

If a source uses these, paraphrase: 強烈推薦 → 列為重點觀察; 目標價 → 估值
區間; 翻倍 → 顯著上行空間; 必漲 → 偏向上行.

## Preferred phrasing

Use the KOL-style validation framing wherever possible:

- "需要核驗 X、Y、Z" rather than "我覺得 X 會發生"
- "邊際變化 / 邊際影響" for incremental shifts
- "叙事 vs 證據" when distinguishing narrative from data
- "外溢效應" for cross-sector transmission
- "映射" for mapping one signal onto another
- "拆解" for decomposing a thesis

## Citation discipline

- Anything the KOL said (paraphrased) needs no special marker — the whole
  brief carries the "📍 分析框架蒸餾自 analysissite.vercel.app" footer.
- Any extension or extrapolation YOU added must be marked `_[AI 推論]_` in
  italics, inline.
- Never paraphrase more than 30 consecutive Chinese characters from the KOL's
  text; cite or compress instead.

## Length budget

Default `depth_preference` for Serenity = **medium**.

| Section | Target |
|---|---|
| Tier 1 (今日優先) | 3-5 entries, 60-100 chars each |
| Tier 2 (掃描清單) | 8 entries, ≤40 chars each |
| Tier 3 (昨日變化) | 4 lines max |
| KOL 對照 | 1-2 lines (omit on day 1 — KG empty) |
| 相關訊號 | top 3 from scoring |
| Footer | 3 lines |

Total target: ~2500 characters. Telegram hard limit: 4096; the runner splits at >3900.
```

- [ ] **Step 4: Write `main.md`**

Create `finance-workflows/prompts/serenity-digest/main.md` with this exact content:

```markdown
# Serenity Digest — orchestration

You are producing today's Serenity Digest. Today is ${DATE} (Asia/Taipei).
Workflow name: ${WORKFLOW_NAME}.

## Output paths (absolute)

- HTML archive: `${OUTPUT_PATH}`
- Telegram brief: same directory, filename `_brief.md`
- History line:  same directory, filename `_history.jsonl` (append, one line)

You can derive the directory in your head: it's `${OUTPUT_PATH}` without the
`<date>.html` tail. Use the Write tool with the full absolute path.

## Step 1 — Fetch and parse the site

Call `mcp__web-fetch__web_fetch` on `https://analysissite.vercel.app/`.

Extract the following structures from the rendered HTML. The site uses
Simplified Chinese internally; convert to Traditional Chinese for your output
where applicable.

- `priorityQueue` (top 3): array of `{ rank, ticker, priority, stance, summary, tags, updatedAt }`.
- `hotStocks` (top 10): same shape.
- `feedItems` (latest 10-20): array of `{ id, ticker, kind, title, body, badges, publishedAt }`.
- `metrics`: `{ activeSignals, coverage, delta24h, delta7d, delta30d, newsDriven }`.
- `distribution`: dict of the 5 category headcounts.

If the fetched body has < 1000 Chinese characters, treat it as a parsing
failure: continue with empty arrays and set a `[STATUS] 抓取異常` banner in
the brief. Do NOT retry the fetch yourself; the runner's retry layer covers
transient claude-level failures separately.

Map the KOL's Chinese stance labels to canonical English labels per
`framework.md`'s stance vocabulary table.

## Step 2 — Diff vs yesterday

The directory containing `${OUTPUT_PATH}` should hold a `_history.jsonl` file
from prior runs. Use the Read tool on it.

Parse each line as JSON. Find the most recent entry whose `date` is
strictly less than ${DATE}. If none exists (first run):

- Set `newInTop10 = []`, `droppedFromTop10 = []`, `priorityMovers = []`
- Mark "首次運行,無昨日對照" in the brief's Tier 3 section.

Otherwise compute:

```
today_tickers   = { s.ticker for s in today.hotStocks }
yest_tickers    = { s.ticker for s in yesterday.hotStocks }
newInTop10      = sorted(today_tickers - yest_tickers)
droppedFromTop10= sorted(yest_tickers - today_tickers)

common = today_tickers ∩ yest_tickers
movers = [(t, today.priority[t] - yesterday.priority[t]) for t in common]
priorityMovers = top 3 by |delta|, excluding delta == 0
```

## Step 3 — KG retrieval (priorityQueue top 3 only)

For each of today's `priorityQueue[0..2].ticker`, call:

```
mcp__knowledge-graph__search_memory({
  query: "{ticker} 觀點演化 stance",
  mode: "hybrid",
  limit: 5,
  compact: false
})
```

Stash the results per ticker. If a search returns 0 hits (no results found),
that ticker has no KG context yet — that's expected on day 1.

If a search errors, log the error to your scratchpad but continue — KG
retrieval is best-effort. The brief simply won't have a "KOL 對照" entry for
that ticker.

## Step 4 — Score and select feedItems

Score every feedItem 0-100 using the five-dimension rule in `framework.md`.
Select the top 3 by score. If any item has the `contradicts` flag (its
content materially conflicts with an existing KG principle for the same
ticker), force-include it and mark with ⚠️.

## Step 5 — Write the HTML archive

Use the Write tool to write `${OUTPUT_PATH}`. Make it a comprehensive,
nicely-styled HTML page with these sections in order:

1. `<header>`: title `Serenity Digest — ${DATE}`, fetched-at timestamp, source link.
2. **Metrics summary** (6 numbers).
3. **Priority queue** (3 entries, full detail).
4. **Hot stocks** (10 entries, table form).
5. **Distribution** (5-category bar).
6. **Diff vs yesterday** (new/dropped/movers).
7. **KG context** (per-ticker for top 3, if any results).
8. **Selected news** (top 3 scored feedItems with score breakdown).
9. **Footer**: attribution to `analysissite.vercel.app`, Persona stage (`Phase 1 樸素模式`), KG node count from `mcp__knowledge-graph__memory_stats` if cheap, run timestamp.

Use light inline CSS for readability; this file is the durable archive a
human will read on their laptop later.

## Step 6 — Write `_brief.md` (Telegram body)

Use the Write tool. The file's raw Markdown becomes the Telegram message
verbatim — keep it under 3900 chars.

Use this exact skeleton (substitute your data; omit sections per the
omission rules):

```
📊 *${DATE} Serenity 日報* (HH:MM 台北)

▎*今日優先*
1. *{TICKER}* · 優先級 {p} · {stance 中文}
   {KOL reasoning summary, 1 sentence}
   需驗證:{2-3 個 validation points 用、分隔}
   _{optional KG context line}_

(repeat for tier1_count entries, 3-5 total)

▎*掃描清單*
{N}. *{TICKER}* {p} {stance 簡寫}
(8 entries)

▎*昨日變化*
🆕 進榜:...
👋 退榜:...
📈 漲幅最大:...
📉 跌幅最大:...

▎*KOL 對照*
• *{TICKER}*: {1-2 sentence context from KG}
(0-2 entries; omit section entirely if KG returned nothing)

▎*相關訊號*
• ⚠️ *{TICKER}* · {source}: {title}
  _{optional alignment note with KG}_
(top 3 scored items; ⚠️ only on contradicts items)

─────────
📍 分析框架蒸餾自 [analysissite.vercel.app](https://analysissite.vercel.app/)
🧠 Phase 1 樸素模式 · KG {N} nodes
🔗 完整看板:https://analysissite.vercel.app/
```

Omission rules:
- No yesterday: replace `▎*昨日變化*` body with `(首次運行,無昨日對照)`.
- KG retrieval returned nothing for any ticker: omit the `▎*KOL 對照*` section entirely (do not write the heading at all).
- feedItems empty: omit `▎*相關訊號*`.
- Site parsing failed (Step 1): insert `⚠️ [STATUS] 今日抓取異常,內容可能不完整。` as the second line after the title.

**Before you finalise the file, scan it once for the banned phrases from
`voice.md`. If any are present, rewrite the offending line.**

## Step 7 — KG write

You have a hard budget: ≤ 20 `store_knowledge` calls, ≤ 30
`connect_knowledge` calls for this entire run. Spend them in this order:

### 7a — KOL principle nodes (priorityQueue top 5)

For each ticker in `priorityQueue[0..4]` (or `hotStocks[0..4]` if priorityQueue is short):

```
mcp__knowledge-graph__store_knowledge({
  type: "insight",
  trust: "principle",
  name: "{TICKER} ${DATE} {stance}",
  content: "{KOL reasoning, 1-2 sentences, Traditional Chinese}",
  quote: "{20-50 character VERBATIM excerpt from the KOL's text on the site}",
  source: "serenity-digest",
  metadata: {
    workflow: "serenity-digest",
    site: "analysissite",
    ticker: "{TICKER}",
    stance: "{canonical stance, e.g. bull_high_risk}",
    category: "creative",
    first_seen: "${DATE}",
    confidence: 0.8
  }
})
```

If you cannot find a clean ≤50-character verbatim quote, downgrade `trust` to
`"pattern"` and drop the `quote` field. Never fabricate a quote.

Save the returned `id` per ticker for the edge-creation step.

### 7b — Edges to yesterday's nodes

For each ticker that's in BOTH `today.priorityMovers` and yesterday's recorded
principle nodes:

First, find yesterday's node id. If you don't have it cached from
`_history.jsonl`, call:

```
mcp__knowledge-graph__list_knowledge({
  filter: {"source": "serenity-digest"},
  sort_by: "created_at",
  limit: 20
})
```

and find the most recent matching ticker.

Then connect:

- Stance unchanged + delta > 0 → `relation_type: "refines"`
- Stance reversed              → `relation_type: "contradicts"`
- Otherwise                    → skip

```
mcp__knowledge-graph__connect_knowledge({
  source_id: "{today's node id}",
  target_id: "{yesterday's node id}",
  relation_type: "refines" | "contradicts",
  reasoning: "{1 sentence explaining the change}",
  weight: 0.8,
  source_session: "${WORKFLOW_NAME}-${DATE}"
})
```

### 7c — Claude inference nodes (top 3 only)

Pick the 3 priorityQueue tickers where your own analysis goes beyond what the
KOL said today. For each:

```
mcp__knowledge-graph__store_knowledge({
  type: "insight",
  trust: "inference",
  name: "{TICKER} ${DATE} extrapolation",
  content: "{Your extension of the KOL's view, Traditional Chinese, 1-2 sentences}",
  source: "serenity-digest",
  metadata: {
    workflow: "serenity-digest",
    site: "analysissite",
    ticker: "{TICKER}",
    ai_extrapolated: true,
    first_seen: "${DATE}",
    confidence: 0.6
  }
})
```

NO `quote` field — `inference` is your view, not the KOL's.

Then optionally connect to the corresponding `principle` node from Step 7a:

```
mcp__knowledge-graph__connect_knowledge({
  source_id: "{inference id}",
  target_id: "{principle id}",
  relation_type: "aligns_to",   # or "contradicts" if you're pushing back
  reasoning: "{why}",
  weight: 0.7,
  source_session: "${WORKFLOW_NAME}-${DATE}"
})
```

DO NOT use `must_precede` or `reason_for` with an inference node — the KG
server will reject the call.

### 7d — Failure handling

If any KG call returns an error, log it to your scratchpad and continue. Skip
the failing call's downstream edges. Do not fail the workflow over KG issues.

If you exceed the daily caps, stop writing and continue to Step 8.

## Step 8 — Append the history line

Use the Write tool with append semantics (or read-modify-write) on
`<output_dir>/_history.jsonl`. Append a single JSON line:

```json
{
  "date": "${DATE}",
  "fetchedAt": "{ISO timestamp}",
  "metrics": {...},
  "topTickers": ["NVDA", "TSM", ...],
  "stances": {"NVDA": "bull_high_risk", "TSM": "bull", ...},
  "priorities": {"NVDA": 432, "TSM": 311, ...},
  "newInTop10": [...],
  "droppedFromTop10": [...],
  "priorityMovers": [{"ticker": "NVDA", "delta": 5}, ...],
  "writes": {"principles": N, "inferences": M, "edges": K},
  "kg_node_ids": {"NVDA": "uuid", "TSM": "uuid", ...},
  "status": "ok" | "partial" | "failed"
}
```

This is what tomorrow's Step 2 will read for the diff.

## Step 9 — Done

Print one line to stdout summarising the run, e.g.:
```
serenity-digest done: 10 tickers, 4 KG principle nodes, 2 inferences, 5 edges, brief 2347 chars
```

That's it. Do not write anything else outside the paths specified.
```

- [ ] **Step 5: Verify the prompt files parse as text and have no malformed `${...}` substitutions**

Run from `finance-workflows/`:

```bash
for f in prompts/serenity-digest/*.md; do
  echo "=== $f ==="
  wc -l "$f"
  grep -oE '\$\{[A-Z_]+\}' "$f" | sort -u
done
```

Expected: each file's line count is in a reasonable range (framework ~90, voice ~50, main ~250+). The grep output shows only the recognised substitution keys: `${DATE}`, `${OUTPUT_PATH}`, `${WORKFLOW_NAME}`. If unrecognised keys appear (e.g. typos), fix them.

- [ ] **Step 6: Commit**

```bash
git add finance-workflows/prompts/serenity-digest/
git commit -m "$(cat <<'EOF'
feat(prompts): add serenity-digest framework / voice / main prompts

framework.md — stance vocabulary, adaptive tier rule, 5-dim news scoring,
KG mapping (principle vs inference, allowed edge types), daily caps.
voice.md — Traditional Chinese rule, anti-pattern banned phrases,
KOL-style preferred phrasings, citation discipline, length budget.
main.md — full 9-step orchestration: fetch → diff → KG retrieve → score →
HTML archive → _brief.md → KG write (principles + inferences + edges) →
history.jsonl line. Aligns with serenity-digest-spec docs/01-07 but
adapted to finance-workflows' file layout and runner conventions.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 6: Create `workflows/serenity-digest.json`

**Files:**
- Create: `finance-workflows/workflows/serenity-digest.json`
- Create: `finance-workflows/tests/test_serenity_workflow_loads.py`

- [ ] **Step 1: Write the workflow JSON**

Create `finance-workflows/workflows/serenity-digest.json`:

```json
{
  "$schema_version": 1,
  "name": "serenity-digest",
  "description": "Daily distillation of analysissite.vercel.app — Tier 1/2/3 digest + KG memory of KOL views",
  "model": "claude-sonnet-4-6",
  "max_turns": 40,
  "sources": [
    { "kind": "web", "name": "analysissite", "url": "https://analysissite.vercel.app/" }
  ],
  "tools": ["web-fetch", "knowledge-graph"],
  "prompts": [
    "prompts/shared/faithfulness.md",
    "prompts/serenity-digest/framework.md",
    "prompts/serenity-digest/voice.md",
    "prompts/serenity-digest/main.md"
  ],
  "output": "reports/serenity-digest/{date}.html",
  "post": { "pdf": false, "telegram": "TELEGRAM_TOPIC_SERENITY" },
  "history": {
    "format": "jsonl",
    "summarize_with": "claude-haiku-4-5",
    "fields": ["topTickers", "stances", "priorities", "newInTop10", "droppedFromTop10", "priorityMovers", "metrics", "writes", "kg_node_ids", "status"]
  }
}
```

Note: `max_turns: 40` is higher than us-macro's 60 — wait, that's lower. Choose 40 because the orchestration is fanned-out (web_fetch + multiple KG calls + writes) but each step is bounded. If runs come back hitting the cap, raise it.

Note: `pdf: false` — the brief is Markdown-native; the HTML archive is for browsing, not for PDF export.

Note: `history.summarize_with` runs in addition to the workflow's own
`_history.jsonl` write. The Haiku post-step exists to fill in any structured
fields the main prompt missed. Keep its `fields` list aligned with what
Step 8 of main.md emits.

- [ ] **Step 2: Write a smoke test that the JSON loads**

Create `finance-workflows/tests/test_serenity_workflow_loads.py`:

```python
"""Smoke test that workflows/serenity-digest.json parses correctly via the
shared loader, and that its declared tools are all in the MCP template +
TOOL_MAP. Catches typos in the JSON or unregistered MCPs early."""
import importlib.util, json, pathlib


HERE = pathlib.Path(__file__).resolve().parents[1]


def _load(modname, relpath):
    p = HERE / relpath
    spec = importlib.util.spec_from_file_location(modname, p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_serenity_workflow_json_loads():
    workflow = _load("workflow", "workflow.py")
    cfg = workflow.load_workflow("serenity-digest", HERE)
    assert cfg.name == "serenity-digest"
    assert cfg.tools == ["web-fetch", "knowledge-graph"]
    assert cfg.post.telegram == "TELEGRAM_TOPIC_SERENITY"
    assert cfg.post.pdf is False
    assert cfg.output == "reports/serenity-digest/{date}.html"


def test_serenity_tools_are_in_template():
    """Every tool the workflow declares must exist in the MCP template,
    otherwise render_mcp would raise at runtime."""
    tmpl = json.loads((HERE / "mcp" / "mcp.json.tmpl").read_text("utf-8"))
    available = set(tmpl["mcpServers"].keys())
    workflow_json = json.loads(
        (HERE / "workflows" / "serenity-digest.json").read_text("utf-8"))
    for t in workflow_json["tools"]:
        assert t in available, f"workflow tool {t!r} not in mcp.json.tmpl"


def test_serenity_tools_are_in_tool_map():
    """run-workflow's TOOL_MAP must know how to expand every tool the
    workflow uses, otherwise --allowedTools would miss MCP tool ids."""
    text = (HERE / "run-workflow.py").read_text("utf-8")
    # Just sanity-check the strings exist in TOOL_MAP region
    assert '"web-fetch"' in text
    assert '"knowledge-graph"' in text
    assert "store_knowledge" in text
    assert "search_memory" in text
```

- [ ] **Step 3: Run the smoke tests**

Run: `mcp/.venv/bin/python -m pytest tests/test_serenity_workflow_loads.py -v` (from `finance-workflows/`)
Expected: all 3 tests PASS. If any fails:
- JSON parse error → fix the workflow JSON.
- Missing tool in template → revisit Task 2 Step 3.
- Missing entry in TOOL_MAP → revisit Task 2 Step 2.

- [ ] **Step 4: Run the full suite**

Run: `mcp/.venv/bin/python -m pytest tests/ -v` (from `finance-workflows/`)
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add finance-workflows/workflows/serenity-digest.json finance-workflows/tests/test_serenity_workflow_loads.py
git commit -m "$(cat <<'EOF'
feat(workflow): add serenity-digest config + smoke test

Declares web-fetch + knowledge-graph tools, the 4 prompt files (faithfulness
shared, then framework/voice/main), output path under reports/serenity-digest/,
Telegram topic env-var binding, and the history schema fields tomorrow's diff
will need. Smoke test catches typos and verifies the workflow's tools are
both registered in mcp.json.tmpl and known to run-workflow.py's TOOL_MAP.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
git push origin main
```

---

## Task 7: End-to-end manual verification

**Files:**
- Modify: `finance-workflows/.env` (user adds `TELEGRAM_TOPIC_SERENITY=...`)
- Read: `finance-workflows/reports/serenity-digest/2026-05-29.{html,_brief.md,_history.jsonl}` (produced by the run)

**Why:** Everything is wired up. Before scheduling daily cron, we run it once by hand to confirm the brief actually arrives, looks right, and the KG writes succeeded. This is the highest-information step — bugs here mean iterating on prompts or the runner before cron starts firing.

**Note:** This task requires user interaction (Telegram topic creation + .env edit). It is NOT executable by a subagent without user collaboration.

- [ ] **Step 1: User creates the Telegram forum topic**

User action (cannot be automated by the agent): in the shared Telegram supergroup, create a new forum topic named e.g. "Serenity". Get the topic's message_thread_id (typically by sending a test message and reading it from the URL or via Bot API).

- [ ] **Step 2: User adds the topic id to `.env`**

User edits `finance-workflows/.env` (gitignored) to append:

```
TELEGRAM_TOPIC_SERENITY=<the topic id from Step 1>
```

The agent should not write secrets — ask the user to do it.

- [ ] **Step 3: Manually run the workflow**

Run from `finance-workflows/`:

```bash
mcp/.venv/bin/python run-workflow.py serenity-digest
```

Expected: the run completes in ~30-90 seconds. stdout/stderr should show:
- `[run] serenity-digest → <abs path>/<date>.html`
- (no `[claude] exited` errors)
- (no `[mcp_render]` errors)
- (no `[telegram] skipped`)
- A final summary line from main.md Step 9 like `serenity-digest done: 10 tickers, 4 KG principle nodes, ...`

- [ ] **Step 4: Inspect the three produced files**

Run:

```bash
ls -la reports/serenity-digest/
```

Expected: at least these files exist:
- `2026-05-29.html` — the archive
- `_brief.md` — the Telegram body
- `_history.jsonl` — one line for today

Read `_brief.md` and visually verify:
- Header `📊 *2026-05-29 Serenity 日報*`
- Tier 1 has 3-5 entries with ticker/priority/stance/reasoning/驗證 lines
- Tier 2 has 8 entries
- Tier 3 says `首次運行,無昨日對照` (this is the first run)
- KOL 對照 section is OMITTED (KG was empty for these tickers on day 1)
- 相關訊號 has up to 3 items
- Footer has the attribution line and `KG N nodes` count
- All text is Traditional Chinese
- No banned phrases (`grep -E '強烈推薦|目標價|翻倍|必漲|必跌|100%' _brief.md` returns nothing)

Read `_history.jsonl` and verify it has one line with all the schema fields (date, topTickers, stances, priorities, writes, kg_node_ids, status).

Open `2026-05-29.html` in a browser and confirm the archive renders.

- [ ] **Step 5: Verify Telegram delivered**

Open the Telegram group, navigate to the Serenity topic. There should be exactly one new message — the contents of `_brief.md` rendered with Telegram Markdown. No PDF attachment (workflow has `pdf: false`).

If the message is mangled (broken `*` or `_`), the brief had a stray Markdown character. Iterate on `main.md` Step 6's skeleton.

- [ ] **Step 6: Verify KG writes landed**

Run from `finance-workflows/`:

```bash
node ../mcp/knowledge-graph/scripts/import-skills.js --help 2>&1 | head -1 || true
# Quick check: list nodes tagged with our source
node -e "
const db = require('better-sqlite3')('../mcp/knowledge-graph/knowledge.db', {readonly: true});
const rows = db.prepare(\"SELECT id, name, trust, json_extract(metadata, '\$.ticker') AS ticker, created_at FROM nodes WHERE source = 'serenity-digest' ORDER BY created_at DESC LIMIT 20\").all();
console.log('serenity-digest nodes today:', rows.length);
rows.forEach(r => console.log(\`  \${r.created_at}  \${r.trust.padEnd(10)}  \${(r.ticker||'').padEnd(6)}  \${r.name}\`));
"
```

Expected: ≤ 20 nodes from today, mix of `principle` and `inference` trust, ticker symbols filled in metadata. If 0 nodes: KG MCP probably failed to start — check the log at `reports/serenity-digest/_logs/<date>-<ts>.log` for `[mcp]` lines.

- [ ] **Step 7: Iterate on any issues**

If anything in steps 4-6 was off, edit the relevant prompt (most likely `main.md` Step 6 brief skeleton, or Step 7 KG schema), then re-run with `FINANCE_WORKFLOWS_DATE=2026-05-29 mcp/.venv/bin/python run-workflow.py serenity-digest` to overwrite today's outputs.

Once the brief looks right, commit any prompt fixes:

```bash
git add finance-workflows/prompts/serenity-digest/
git commit -m "fix(serenity prompts): <what you fixed>

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
git push origin main
```

- [ ] **Step 8: Mark task complete**

If everything looks good, this task has no commit of its own. The next task installs the cron.

---

## Task 8: Install launchd job for daily 06:00 TPE

**Files:**
- Create: `~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist`

**Why:** All four existing workflow plists live in `~/Library/LaunchAgents/`, not in the repo. We follow the same convention. The job fires `mcp/.venv/bin/python run-workflow.py serenity-digest` at 06:00 every day (Asia/Taipei).

- [ ] **Step 1: Write the plist**

Create `~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist` with this exact content (substitute the absolute repo path if it differs from `/Users/pochenkuo/AI/new_financial-report-system`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.financeworkflows.serenity-digest</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/pochenkuo/AI/new_financial-report-system/finance-workflows/mcp/.venv/bin/python</string>
    <string>/Users/pochenkuo/AI/new_financial-report-system/finance-workflows/run-workflow.py</string>
    <string>serenity-digest</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/pochenkuo/AI/new_financial-report-system/finance-workflows</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/Users/pochenkuo/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>StandardOutPath</key>
  <string>/Users/pochenkuo/Library/Logs/financeworkflows-serenity-digest.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/pochenkuo/Library/Logs/financeworkflows-serenity-digest.log</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>6</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>RunAtLoad</key>
  <false/>
</dict>
</plist>
```

- [ ] **Step 2: Load the job**

Run:

```bash
launchctl load ~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist
```

Expected: silent success (no output). If a "service already loaded" error appears, first unload and retry:

```bash
launchctl unload ~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist
launchctl load ~/Library/LaunchAgents/com.financeworkflows.serenity-digest.plist
```

- [ ] **Step 3: Confirm the job is registered**

Run:

```bash
launchctl list | grep financeworkflows
```

Expected: a line `-  0  com.financeworkflows.serenity-digest` appears alongside the existing 3 (crypto-daily, us-macro, deep-stock-research). The `-` exit code means "not yet run", which is correct.

- [ ] **Step 4: Verify the scheduled time via launchctl print**

Run:

```bash
launchctl print gui/$(id -u)/com.financeworkflows.serenity-digest | grep -A2 "schedule"
```

Expected: shows `hour = 6, minute = 0` in the calendar interval. If your laptop is set to a non-Taipei zone, that's the local clock time — 06:00 means 06:00 wherever you are.

- [ ] **Step 5: Verify `pmset repeat` already covers 06:00**

Run:

```bash
pmset -g sched
```

Expected: includes a line like `wakeorpoweron at 07:25:00 every day` (per memory note). The wake fires 5 minutes before crypto-daily's 07:30. **06:00 is BEFORE the wake** — meaning the laptop will be asleep when the cron should fire. This is a known launchd behaviour: missed jobs run when the machine wakes, but the timing slips to ~07:25.

User decision needed: either accept the slip (Serenity fires at ~07:25 instead of 06:00 on days the lid is closed) OR add an earlier `pmset repeat` wake. If the latter, run (requires sudo):

```bash
sudo pmset repeat wakeorpoweron MTWRFSU 05:55:00
```

Flag this to the user before doing it — it changes their global wake schedule.

- [ ] **Step 6: No commit needed**

Plists are not tracked in the repo (none of the existing ones are). Nothing to commit.

---

## Self-review

**Spec coverage check:** The 9 docs in `serenity-digest-spec/docs/` and the 3 prompts in `serenity-digest-spec/prompts/` define the Phase 1 product. Let me map them to tasks in this plan:

- `00-system-overview.md` (3-layer architecture) → covered by tasks 2, 5, 7 (KG layer + Persona deferred + Automation via launchd)
- `01-scraping.md` (parse rules, error handling) → covered by main.md Step 1 + Step 5 STATUS banner
- `02-knowledge-graph.md` (KG schema for Serenity) → covered by framework.md "KG mapping" + main.md Step 7
- `03-persona-distillation.md` → DEFERRED to Phase 2 per architectural decision #5 above
- `04-daily-workflow.md` (end-to-end timing) → covered by main.md Steps 1-9
- `05-stock-strategy.md` (tier rule) → covered by framework.md "Tier rule"
- `06-news-scoring.md` (5-dim scoring) → covered by framework.md "News importance score"
- `07-telegram-format.md` (Tier 1/2/3 layout) → covered by main.md Step 6 skeleton + voice.md length budget
- `08-storage.md` (folder layout) → ADAPTED: reports under `finance-workflows/reports/serenity-digest/`, KG inherits project-root location. config.json not used (we use `.env`)
- `09-evolution.md` (90-day decisions) → out of scope for Phase 1
- `10-acceptance.md` (verification criteria) → covered by Task 7 Steps 4-6
- `prompts/daily-brief.md` → mostly inlined into main.md Step 6
- `prompts/weekly-reflection.md` → DEFERRED
- `prompts/distillation-bootstrap.md` → DEFERRED

**Placeholder scan:** I searched the plan for "TODO", "TBD", "implement later", "add appropriate", "similar to". None present. The main.md content includes full prompt text; framework.md / voice.md likewise have complete content; tests show full code; commits show full messages.

**Type consistency:** Verified:
- `render_mcp(..., root_dir=...)` signature consistent in Task 1 implementation and Task 2 Step 1 call site.
- `_brief.md` filename consistent across notify_telegram.py change (Task 4 Step 3), main.md Step 6 (Task 5 Step 4), and Task 7 verification.
- `TELEGRAM_TOPIC_SERENITY` env-var name consistent across workflows JSON (Task 6) and .env edit (Task 7 Step 2).
- Source tag `"serenity-digest"` consistent across framework.md, main.md Steps 7a/7c, and the Task 7 Step 6 SQL query.

**Scope check:** Single subsystem (one new workflow + small runner extensions). No decomposition needed.

**Open risk surfaced for user attention:**
1. Task 7 Step 5 — `06:00` wake schedule. User may need to decide whether to adjust `pmset repeat`.
2. Task 1 — `@ROOT@` placeholder will be literal if `root_dir` not passed; existing tests don't pass it. Confirmed via the `test_render_root_unset_leaves_placeholder_literal` test that this is intentional + visible behaviour.
3. Task 5 main.md — instructs the model to do a lot in one prompt (fetch + diff + retrieve + score + write HTML + write brief + write KG + write history). If the model under-spends max_turns, the runner just exits cleanly; if it over-runs, max_turns=40 is the safety net. Iterate after first real run.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-serenity-digest-phase1-kg.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, two-stage review between tasks, fast iteration. Task 7 still requires user action (Telegram topic + `.env` value).

2. **Inline Execution** — I execute tasks in this session using the executing-plans skill, with checkpoints between tasks. You stay in the loop between every commit.

For this plan I'd recommend **Inline Execution** because:
- Task 7 needs your input mid-flight (Telegram topic creation) — easier to handle in conversation than via subagent.
- Several tasks touch the same files (`run-workflow.py` is modified in Tasks 2, 3) — sequential inline avoids merge edge cases.
- Per-slice commit/push cadence (from CLAUDE.md) is naturally what inline does.

Which approach?
