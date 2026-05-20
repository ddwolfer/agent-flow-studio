# finance-workflows MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Stand up a parallel, thin Python `finance-workflows/` runner driven by `workflow.json`, prove it with one end-to-end `crypto-daily` workflow. `studio/` keeps running Eason unchanged.

**Architecture:** Each `workflows/<name>.json` declares sources, tools, prompts, output, optional history. A small Python orchestrator (`run-workflow.py`) renders a per-workflow `mcp.json`, concatenates the listed prompts with token substitution, invokes `claude -p` headlessly, optionally PDFs the HTML, optionally appends a Haiku-extracted summary to `_history.jsonl`. No UI, no state machine, no SQLite.

**Tech Stack:** Python 3 (orchestrator + MCP servers), FastMCP (`mcp[cli]`), feedparser (RSS), httpx + readability-lxml + markdownify (web extract), yt-dlp (transcripts, reused), pytest. Headless `claude -p` via subprocess. macOS Chrome (existing) for PDF.

**Spec:** `docs/superpowers/specs/2026-05-21-finance-workflows-design.md` · commit `71b208c`. MVP scope from §2.

---

## File Structure

```
finance-workflows/
├── workflows/
│   └── crypto-daily.json
├── mcp/
│   ├── .venv/                                 # Python venv (gitignored)
│   ├── mcp.json.tmpl                          # rendered per run
│   └── servers/
│       ├── ytdlp_server.py                    # copied from studio/mcp/servers
│       ├── rss_server.py                      # NEW
│       └── web_fetch_server.py                # NEW
├── prompts/
│   ├── shared/faithfulness.md
│   └── crypto/{framework,voice,main}.md
├── reports/crypto-daily/                       # outputs (gitignored except _history.jsonl?)
├── tests/                                      # pytest
│   ├── test_workflow.py
│   ├── test_mcp_render.py
│   ├── test_prompt_build.py
│   ├── test_rss_server.py
│   └── test_web_fetch_server.py
├── workflow.py                                 # load/validate workflow.json
├── mcp_render.py                               # render mcp.json from workflow.tools
├── prompt_build.py                             # concatenate prompts + substitute tokens
├── run-workflow.py                             # the orchestrator (CLI entry)
├── requirements.txt
├── cron.example.sh
├── CLAUDE.md
└── README.md
```

`finance-workflows/.gitignore` includes `.venv/`, `reports/*/[0-9]*.html`, `reports/*/[0-9]*.pdf`, `reports/*/_logs/`, `mcp/mcp.json` — but **`_history.jsonl` is tracked** (small, useful in version control).

---

### Task 1: Scaffold + venv + copy proven yt-dlp server

**Files:**
- Create: `finance-workflows/` and the empty subdirs above
- Create: `finance-workflows/requirements.txt`
- Create: `finance-workflows/.gitignore`
- Copy: `studio/mcp/servers/ytdlp_server.py` → `finance-workflows/mcp/servers/ytdlp_server.py`
- Copy if referenced: `studio/mcp/lib/gemma_transcribe.py` → `finance-workflows/mcp/lib/gemma_transcribe.py`
- Create: `finance-workflows/mcp/mcp.json.tmpl`

- [ ] **Step 1: Make the tree + requirements.txt**

```bash
cd /Users/pochenkuo/AI/new_financial-report-system
mkdir -p finance-workflows/{workflows,mcp/servers,mcp/lib,prompts/shared,prompts/crypto,reports/crypto-daily,tests}
```

Create `finance-workflows/requirements.txt`:

```
mcp[cli]>=1.0
yt-dlp>=2024.9.0
requests>=2.31
feedparser>=6.0
httpx>=0.27
readability-lxml>=0.8.1
markdownify>=0.13
pytest>=8.0
```

Create `finance-workflows/.gitignore`:

```
.venv/
__pycache__/
*.pyc
reports/*/[0-9]*.html
reports/*/[0-9]*.pdf
reports/*/_logs/
mcp/mcp.json
.pytest_cache/
```

- [ ] **Step 2: Create venv + install deps**

```bash
cd finance-workflows
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
```

Verify: `.venv/bin/python -c "import feedparser, httpx, readability, markdownify, mcp; print('ok')"` → prints `ok`. If any import fails, STOP and report.

- [ ] **Step 3: Copy the proven yt-dlp server (and its gemma helper if it imports it)**

```bash
cd /Users/pochenkuo/AI/new_financial-report-system
cp studio/mcp/servers/ytdlp_server.py finance-workflows/mcp/servers/ytdlp_server.py
# only copy the gemma helper if ytdlp_server actually imports from ../lib/gemma_transcribe
grep -l "gemma_transcribe" finance-workflows/mcp/servers/ytdlp_server.py >/dev/null && \
  cp studio/mcp/lib/gemma_transcribe.py finance-workflows/mcp/lib/gemma_transcribe.py
```

Smoke: `finance-workflows/.venv/bin/python -c "import sys, importlib.util; sys.path.insert(0,'finance-workflows/mcp/servers'); import ytdlp_server; print('ok')"` → `ok`. (The `sys.path` trick mirrors what the MCP runner does when claude spawns the server.) If it errors on the `from .. import` for gemma helper, the `mkdir`+conditional copy in Step 3 covered it; if it still errors, STOP and report.

- [ ] **Step 4: Create the mcp.json template**

`finance-workflows/mcp/mcp.json.tmpl`:

```json
{
  "mcpServers": {
    "yt-dlp":     { "command": "@PY@", "args": ["@MCPDIR@/servers/ytdlp_server.py"] },
    "rss":        { "command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"] },
    "web-fetch":  { "command": "@PY@", "args": ["@MCPDIR@/servers/web_fetch_server.py"] }
  }
}
```

> Note: each workflow's `tools` field selects which of these servers actually go into the rendered `mcp.json` at runtime (Task 5).

- [ ] **Step 5: Commit + push** (git from repo root)

```bash
git add finance-workflows/requirements.txt finance-workflows/.gitignore \
        finance-workflows/mcp/mcp.json.tmpl \
        finance-workflows/mcp/servers/ytdlp_server.py \
        $(test -f finance-workflows/mcp/lib/gemma_transcribe.py && echo finance-workflows/mcp/lib/gemma_transcribe.py)
git commit -m "feat(finance-workflows): scaffold + venv + copy proven yt-dlp MCP server"
git push origin main
```

---

### Task 2: RSS MCP server

**Files:**
- Create: `finance-workflows/mcp/servers/rss_server.py`
- Test: `finance-workflows/tests/test_rss_server.py`

- [ ] **Step 1: Write the failing test** — `finance-workflows/tests/test_rss_server.py`:

```python
import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "rss_server.py"
    spec = importlib.util.spec_from_file_location("rss_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_FAKE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Demo</title>
  <item>
    <title>First post</title>
    <link>https://example.com/1</link>
    <pubDate>Mon, 21 May 2026 09:00:00 +0000</pubDate>
    <description>One liner.</description>
  </item>
  <item>
    <title>Second post</title>
    <link>https://example.com/2</link>
    <pubDate>Mon, 21 May 2026 08:00:00 +0000</pubDate>
    <description>Another.</description>
  </item>
</channel></rss>"""

def test_rss_fetch_parses_items(monkeypatch):
    m = _load()
    # Patch the network reader to return our fixture XML
    monkeypatch.setattr(m, "_fetch_bytes", lambda url, timeout=30: _FAKE_RSS.encode("utf-8"))
    out = m.rss_fetch("https://example.com/feed", max_items=10)
    assert len(out) == 2
    assert out[0]["title"] == "First post"
    assert out[0]["link"] == "https://example.com/1"
    assert "2026-05-21" in out[0]["published"]
    assert out[0]["summary"].startswith("One liner")

def test_rss_fetch_caps_max_items(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_fetch_bytes", lambda url, timeout=30: _FAKE_RSS.encode("utf-8"))
    out = m.rss_fetch("https://example.com/feed", max_items=1)
    assert len(out) == 1

def test_rss_fetch_returns_empty_on_404(monkeypatch):
    m = _load()
    def raise_404(url, timeout=30):
        raise m._FetchError("404 not found")
    monkeypatch.setattr(m, "_fetch_bytes", raise_404)
    out = m.rss_fetch("https://example.com/missing")
    assert out == []
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_rss_server.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `finance-workflows/mcp/servers/rss_server.py`:

```python
"""RSS MCP server — one tool: rss_fetch(url, max_items=20)."""
import feedparser, httpx
from mcp.server.fastmcp import FastMCP


class _FetchError(Exception):
    """Raised when the underlying HTTP fetch fails (network/HTTP error)."""


def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "finance-workflows/0.1"})
        if r.status_code >= 400:
            raise _FetchError(f"HTTP {r.status_code}")
        return r.content
    except (httpx.RequestError, _FetchError) as e:
        raise _FetchError(str(e))


def _norm_date(entry) -> str:
    # feedparser exposes published_parsed (struct_time) when it can; else fall back to raw string
    if getattr(entry, "published_parsed", None):
        t = entry.published_parsed
        return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
    return getattr(entry, "published", "") or ""


mcp = FastMCP("rss")


@mcp.tool()
def rss_fetch(url: str, max_items: int = 20):
    """Fetch and parse an RSS/Atom feed. Returns a list of items or [] on failure.

    Each item: {title, link, published (YYYY-MM-DD if parseable), summary}.
    Never raises — returns [] if the URL is unreachable or not a feed.
    """
    try:
        raw = _fetch_bytes(url)
    except _FetchError:
        return []
    parsed = feedparser.parse(raw)
    out = []
    for e in parsed.entries[: max(int(max_items), 1)]:
        out.append({
            "title": getattr(e, "title", "") or "",
            "link": getattr(e, "link", "") or "",
            "published": _norm_date(e),
            "summary": (getattr(e, "summary", "") or "")[:1000],
        })
    return out


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_rss_server.py -v
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit + push**

```bash
git add finance-workflows/mcp/servers/rss_server.py finance-workflows/tests/test_rss_server.py
git commit -m "feat(mcp): rss_server (feedparser, never-raises, caps max_items)"
git push origin main
```

---

### Task 3: web-fetch MCP server

**Files:**
- Create: `finance-workflows/mcp/servers/web_fetch_server.py`
- Test: `finance-workflows/tests/test_web_fetch_server.py`

- [ ] **Step 1: Write the failing tests** — `finance-workflows/tests/test_web_fetch_server.py`:

```python
import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "web_fetch_server.py"
    spec = importlib.util.spec_from_file_location("web_fetch_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_HTML = """<!doctype html><html><head><title>Hello Title</title>
<meta name="author" content="Jane Doe">
</head><body>
<header>nav stuff</header>
<article><h1>Hello Title</h1>
<p>First paragraph of the real article body. Has enough words to be picked up.</p>
<p>Second paragraph with more content for the readability extractor to like.</p>
</article>
<footer>cookie banner</footer>
</body></html>"""

class _R:
    def __init__(self, text, status=200, ct="text/html"):
        self.text = text; self.status_code = status
        self.headers = {"content-type": ct}; self.content = text.encode()

def test_web_fetch_returns_status_and_text(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R(_HTML))
    r = m.web_fetch("https://example.com/article")
    assert r["status"] == 200
    assert "Hello Title" in r["text"]
    assert r["content_type"].startswith("text/html")

def test_web_fetch_non_200_still_returns_shape(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R("nope", status=404, ct="text/plain"))
    r = m.web_fetch("https://example.com/missing")
    assert r["status"] == 404
    assert r["text"] == "nope"

def test_web_extract_article_strips_chrome(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R(_HTML))
    r = m.web_extract_article("https://example.com/article")
    assert r["title"] == "Hello Title"
    md = r["text_markdown"]
    assert "First paragraph of the real article body" in md
    # The readability+markdownify pass should drop nav/footer chrome
    assert "nav stuff" not in md
    assert "cookie banner" not in md

def test_web_fetch_network_error_returns_status_0(monkeypatch):
    m = _load()
    def boom(url, timeout=30):
        raise m._WebError("connection refused")
    monkeypatch.setattr(m, "_http_get", boom)
    r = m.web_fetch("https://no-such-host.invalid")
    assert r["status"] == 0
    assert "connection refused" in r["text"]
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_web_fetch_server.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `finance-workflows/mcp/servers/web_fetch_server.py`:

```python
"""web-fetch MCP server — two tools: web_fetch(url) and web_extract_article(url)."""
import httpx
from mcp.server.fastmcp import FastMCP

# readability-lxml + markdownify for article extraction
from readability import Document
from markdownify import markdownify


class _WebError(Exception):
    """Raised by _http_get when the underlying HTTP fetch fails (network error)."""


def _http_get(url: str, timeout: int = 30):
    try:
        return httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "finance-workflows/0.1"})
    except httpx.RequestError as e:
        raise _WebError(str(e))


mcp = FastMCP("web-fetch")


@mcp.tool()
def web_fetch(url: str):
    """Raw HTTP GET. Returns {status, content_type, text}. Never raises;
    on network error returns {status:0, content_type:'', text:<error>}.
    """
    try:
        r = _http_get(url)
    except _WebError as e:
        return {"status": 0, "content_type": "", "text": str(e)}
    return {"status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "text": r.text}


@mcp.tool()
def web_extract_article(url: str):
    """Extract a readable article from a URL using readability + markdownify.
    Returns {title, byline, published, text_markdown}. Never raises;
    on failure returns the dict with empty fields.
    """
    try:
        r = _http_get(url)
    except _WebError:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    if r.status_code >= 400:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    try:
        doc = Document(r.text)
        title = (doc.short_title() or "").strip()
        body_html = doc.summary(html_partial=True)
        md = markdownify(body_html, heading_style="ATX").strip()
    except Exception:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    return {"title": title, "byline": "", "published": "", "text_markdown": md}


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_web_fetch_server.py -v
```

Expected: PASS (4/4).

- [ ] **Step 5: Commit + push**

```bash
git add finance-workflows/mcp/servers/web_fetch_server.py finance-workflows/tests/test_web_fetch_server.py
git commit -m "feat(mcp): web_fetch_server (httpx + readability + markdownify, never-raises)"
git push origin main
```

---

### Task 4: workflow.json loader + validator

**Files:**
- Create: `finance-workflows/workflow.py`
- Test: `finance-workflows/tests/test_workflow.py`

- [ ] **Step 1: Write the failing tests** — `finance-workflows/tests/test_workflow.py`:

```python
import importlib.util, json, pathlib, tempfile

def _load():
    p = pathlib.Path(__file__).parents[1] / "workflow.py"
    spec = importlib.util.spec_from_file_location("workflow", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_VALID = {
    "name": "demo",
    "model": "claude-sonnet-4-6",
    "max_turns": 30,
    "sources": [{"kind": "youtube", "handle": "@x", "search_query": "x"}],
    "tools": ["yt-dlp"],
    "prompts": ["prompts/shared/faithfulness.md", "prompts/crypto/main.md"],
    "output": "reports/demo/{date}.html",
    "post": {"pdf": True},
}

def test_load_valid_workflow(tmp_path):
    w = _load()
    p = tmp_path / "wf.json"
    p.write_text(json.dumps(_VALID), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert cfg.name == "demo"
    assert cfg.model == "claude-sonnet-4-6"
    assert cfg.max_turns == 30
    assert cfg.tools == ["yt-dlp"]
    assert cfg.post.pdf is True
    assert cfg.history is None

def test_load_with_history(tmp_path):
    w = _load()
    payload = {**_VALID, "history": {"format": "jsonl", "summarize_with": "claude-haiku-4-5",
                                     "fields": ["stance", "confidence"]}}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(payload), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert cfg.history.format == "jsonl"
    assert cfg.history.summarize_with == "claude-haiku-4-5"
    assert cfg.history.fields == ["stance", "confidence"]

def test_missing_required_field_raises(tmp_path):
    w = _load()
    bad = {k: v for k, v in _VALID.items() if k != "tools"}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(bad), "utf-8")
    try:
        w.load_workflow_from_path(p)
    except w.WorkflowError as e:
        assert "tools" in str(e)
        return
    raise AssertionError("expected WorkflowError")

def test_empty_tools_raises(tmp_path):
    w = _load()
    bad = {**_VALID, "tools": []}
    p = tmp_path / "wf.json"; p.write_text(json.dumps(bad), "utf-8")
    try:
        w.load_workflow_from_path(p); raise AssertionError("expected WorkflowError")
    except w.WorkflowError:
        pass

def test_resolve_output_substitutes_date(tmp_path):
    w = _load()
    p = tmp_path / "wf.json"; p.write_text(json.dumps(_VALID), "utf-8")
    cfg = w.load_workflow_from_path(p)
    assert w.resolve_output(cfg, "2026-05-21") == "reports/demo/2026-05-21.html"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_workflow.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `finance-workflows/workflow.py`:

```python
"""workflow.json loader + validator. Plain dataclasses, no third-party deps."""
from __future__ import annotations
import json, pathlib
from dataclasses import dataclass, field
from typing import Optional


class WorkflowError(Exception):
    pass


@dataclass
class Source:
    kind: str
    # free-form per kind:
    handle: str = ""
    search_query: str = ""
    name: str = ""
    url: str = ""
    rss: str = ""


@dataclass
class Post:
    pdf: bool = False


@dataclass
class History:
    format: str  # "jsonl"
    summarize_with: str
    fields: list


@dataclass
class Workflow:
    name: str
    model: str
    max_turns: int
    sources: list  # list[Source]
    tools: list    # list[str]
    prompts: list  # list[str] (relative paths)
    output: str
    post: Post
    description: str = ""
    history: Optional[History] = None


def _require(d: dict, key: str, label: str):
    if key not in d or d[key] in (None, "", []):
        raise WorkflowError(f"workflow missing required field '{key}' in {label}")


def load_workflow_from_path(path: pathlib.Path | str) -> Workflow:
    p = pathlib.Path(path)
    try:
        raw = json.loads(p.read_text("utf-8"))
    except FileNotFoundError:
        raise WorkflowError(f"workflow file not found: {p}")
    except json.JSONDecodeError as e:
        raise WorkflowError(f"invalid JSON in {p}: {e}")

    for k in ("name", "model", "max_turns", "sources", "tools", "prompts", "output"):
        _require(raw, k, str(p))
    if not isinstance(raw["tools"], list) or len(raw["tools"]) == 0:
        raise WorkflowError(f"'tools' must be a non-empty list in {p}")
    if not isinstance(raw["prompts"], list) or len(raw["prompts"]) == 0:
        raise WorkflowError(f"'prompts' must be a non-empty list in {p}")

    sources = [Source(**{**{"kind": ""}, **s}) for s in raw["sources"]]
    post = Post(**raw.get("post", {}))
    history = None
    if "history" in raw and raw["history"]:
        h = raw["history"]
        for k in ("format", "summarize_with", "fields"):
            _require(h, k, f"{p} .history")
        history = History(format=h["format"], summarize_with=h["summarize_with"],
                          fields=list(h["fields"]))

    return Workflow(
        name=raw["name"], model=raw["model"], max_turns=int(raw["max_turns"]),
        sources=sources, tools=list(raw["tools"]), prompts=list(raw["prompts"]),
        output=raw["output"], post=post, history=history,
        description=raw.get("description", ""),
    )


def load_workflow(name: str, root: pathlib.Path | str) -> Workflow:
    """Convenience: load workflows/<name>.json from a given finance-workflows/ root."""
    return load_workflow_from_path(pathlib.Path(root) / "workflows" / f"{name}.json")


def resolve_output(cfg: Workflow, date_iso: str) -> str:
    """Substitute {date} (and only {date}) in the output template."""
    return cfg.output.replace("{date}", date_iso)
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_workflow.py -v
```

Expected: PASS (5/5).

- [ ] **Step 5: Commit + push**

```bash
git add finance-workflows/workflow.py finance-workflows/tests/test_workflow.py
git commit -m "feat(finance-workflows): workflow.json loader + validator (dataclasses, no deps)"
git push origin main
```

---

### Task 5: mcp.json renderer (per-workflow allow-list)

**Files:**
- Create: `finance-workflows/mcp_render.py`
- Test: `finance-workflows/tests/test_mcp_render.py`

- [ ] **Step 1: Write the failing tests** — `finance-workflows/tests/test_mcp_render.py`:

```python
import importlib.util, json, pathlib, tempfile

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp_render.py"
    spec = importlib.util.spec_from_file_location("mcp_render", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_TMPL = """{
  "mcpServers": {
    "yt-dlp":    { "command": "@PY@", "args": ["@MCPDIR@/servers/ytdlp_server.py"] },
    "rss":       { "command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"] },
    "web-fetch": { "command": "@PY@", "args": ["@MCPDIR@/servers/web_fetch_server.py"] }
  }
}"""

def test_render_keeps_only_requested_servers(tmp_path):
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"; tmpl.write_text(_TMPL, "utf-8")
    out = tmp_path / "mcp.json"
    m.render_mcp(tools=["rss", "web-fetch"], mcp_dir=str(tmp_path / "mcp"),
                 python_bin="/x/py", tmpl_path=tmpl, out_path=out)
    cfg = json.loads(out.read_text("utf-8"))
    assert set(cfg["mcpServers"].keys()) == {"rss", "web-fetch"}
    assert cfg["mcpServers"]["rss"]["command"] == "/x/py"
    assert cfg["mcpServers"]["rss"]["args"][0] == f"{tmp_path / 'mcp'}/servers/rss_server.py"

def test_render_rejects_unknown_tool(tmp_path):
    m = _load()
    tmpl = tmp_path / "mcp.json.tmpl"; tmpl.write_text(_TMPL, "utf-8")
    try:
        m.render_mcp(tools=["coingecko"], mcp_dir=str(tmp_path / "mcp"),
                     python_bin="/x/py", tmpl_path=tmpl, out_path=tmp_path / "mcp.json")
        raise AssertionError("expected error")
    except m.McpRenderError as e:
        assert "coingecko" in str(e)

def test_derive_allowed_tools_from_servers():
    m = _load()
    out = m.derive_allowed_tools(["rss", "yt-dlp"], {
        "rss": ["rss_fetch"],
        "yt-dlp": ["ytdlp_search_videos", "ytdlp_transcript_page"],
        "web-fetch": ["web_fetch", "web_extract_article"],
    })
    assert out == [
        "mcp__rss__rss_fetch",
        "mcp__yt-dlp__ytdlp_search_videos",
        "mcp__yt-dlp__ytdlp_transcript_page",
        "Write", "Read",
    ]
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_mcp_render.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `finance-workflows/mcp_render.py`:

```python
"""Render finance-workflows/mcp/mcp.json from the template, keeping only the
servers a workflow declares in its `tools` field, with paths/python resolved."""
from __future__ import annotations
import json, pathlib


class McpRenderError(Exception):
    pass


def render_mcp(*, tools: list, mcp_dir: str, python_bin: str,
               tmpl_path: pathlib.Path, out_path: pathlib.Path) -> str:
    """Read tmpl, parse JSON, retain only the requested server keys, substitute
    @PY@/@MCPDIR@, write to out_path. Returns the absolute out_path as a string.

    Raises McpRenderError if any requested tool isn't in the template.
    """
    tmpl = json.loads(pathlib.Path(tmpl_path).read_text("utf-8"))
    available = set(tmpl.get("mcpServers", {}).keys())
    unknown = [t for t in tools if t not in available]
    if unknown:
        raise McpRenderError(f"unknown MCP server(s) in workflow.tools: {unknown}; "
                             f"template has: {sorted(available)}")
    rendered = {"mcpServers": {}}
    for name in tools:
        entry = json.loads(json.dumps(tmpl["mcpServers"][name]))  # deep copy
        entry["command"] = entry["command"].replace("@PY@", python_bin)
        entry["args"] = [a.replace("@MCPDIR@", mcp_dir).replace("@PY@", python_bin)
                         for a in entry.get("args", [])]
        # env passthrough untouched (no @FREDKEY@ etc. for the three MVP servers)
        rendered["mcpServers"][name] = entry
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rendered, indent=2, ensure_ascii=False), "utf-8")
    return str(out)


def derive_allowed_tools(servers: list, tool_map: dict) -> list:
    """Given the requested server names and a {server: [tool_ids]} map, return
    the flat allowedTools list claude -p expects, plus Write+Read at the end."""
    out = []
    for s in servers:
        for t in tool_map.get(s, []):
            out.append(f"mcp__{s}__{t}")
    out.extend(["Write", "Read"])
    return out
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_mcp_render.py -v
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit + push**

```bash
git add finance-workflows/mcp_render.py finance-workflows/tests/test_mcp_render.py
git commit -m "feat(finance-workflows): mcp.json renderer + derive_allowed_tools"
git push origin main
```

---

### Task 6: Prompt builder + token substitution

**Files:**
- Create: `finance-workflows/prompt_build.py`
- Test: `finance-workflows/tests/test_prompt_build.py`

- [ ] **Step 1: Write the failing tests** — `finance-workflows/tests/test_prompt_build.py`:

```python
import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "prompt_build.py"
    spec = importlib.util.spec_from_file_location("prompt_build", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_concat_and_substitute(tmp_path):
    pb = _load()
    a = tmp_path / "a.md"; a.write_text("Faithfulness rules.\n", "utf-8")
    b = tmp_path / "b.md"; b.write_text("Write to ${OUTPUT_PATH} on ${DATE}.\nName: ${WORKFLOW_NAME}\n", "utf-8")
    out = pb.build_prompt(
        prompt_paths=[a, b],
        substitutions={
            "DATE": "2026-05-21",
            "OUTPUT_PATH": "/tmp/r.html",
            "WORKFLOW_NAME": "crypto-daily",
            "SOURCES_JSON": '[{"kind":"youtube"}]',
        },
    )
    assert "Faithfulness rules." in out
    assert "Write to /tmp/r.html on 2026-05-21." in out
    assert "Name: crypto-daily" in out

def test_missing_file_raises(tmp_path):
    pb = _load()
    try:
        pb.build_prompt(prompt_paths=[tmp_path / "nope.md"], substitutions={})
        raise AssertionError("expected error")
    except FileNotFoundError:
        pass

def test_unsubstituted_token_kept_as_is(tmp_path):
    pb = _load()
    a = tmp_path / "a.md"; a.write_text("Has ${UNKNOWN} placeholder.\n", "utf-8")
    out = pb.build_prompt(prompt_paths=[a], substitutions={"DATE": "2026-05-21"})
    # We intentionally do NOT raise on unknown tokens — leave the literal so the
    # author can spot it in the assembled prompt during debugging.
    assert "${UNKNOWN}" in out
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_prompt_build.py -v
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `finance-workflows/prompt_build.py`:

```python
"""Concatenate prompt .md files in order, then substitute ${TOKEN} placeholders
with values from a dict. Unknown tokens are left literal (debug visibility)."""
from __future__ import annotations
import pathlib


def build_prompt(*, prompt_paths: list, substitutions: dict) -> str:
    parts = []
    for p in prompt_paths:
        parts.append(pathlib.Path(p).read_text("utf-8"))
    text = "\n\n".join(parts)
    for k, v in substitutions.items():
        text = text.replace(f"${{{k}}}", str(v))
    return text
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_prompt_build.py -v
```

Expected: PASS (3/3).

- [ ] **Step 5: Commit + push**

```bash
git add finance-workflows/prompt_build.py finance-workflows/tests/test_prompt_build.py
git commit -m "feat(finance-workflows): prompt_build (concat + \${TOKEN} substitution, unknown left literal)"
git push origin main
```

---

### Task 7: The orchestrator (`run-workflow.py`)

**Files:**
- Create: `finance-workflows/run-workflow.py`
- Test: `finance-workflows/tests/test_run_workflow.py`

This is the wiring task; isolated logic is already TDD'd in Tasks 4–6. The orchestrator test uses a fake `claude` shim to prove the wiring without invoking real Claude.

- [ ] **Step 1: Write the failing test** — `finance-workflows/tests/test_run_workflow.py`:

```python
import json, os, pathlib, subprocess, sys, textwrap

REPO = pathlib.Path(__file__).parents[2]  # /…/new_financial-report-system
FW = REPO / "finance-workflows"

def test_orchestrator_writes_report_with_fake_claude(tmp_path, monkeypatch):
    # Build a fake studio root in tmp_path so we don't touch the real reports/
    workflows = tmp_path / "workflows"; workflows.mkdir()
    prompts = tmp_path / "prompts" / "x"; prompts.mkdir(parents=True)
    (prompts / "main.md").write_text("write to ${OUTPUT_PATH} please\n", "utf-8")
    mcp_dir = tmp_path / "mcp"; (mcp_dir / "servers").mkdir(parents=True)
    (mcp_dir / "mcp.json.tmpl").write_text(json.dumps({
        "mcpServers": {
            "rss": {"command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"]}
        }}), "utf-8")
    (workflows / "demo.json").write_text(json.dumps({
        "name": "demo", "model": "claude-sonnet-4-6", "max_turns": 5,
        "sources": [{"kind": "rss", "name": "z", "url": "https://example.com"}],
        "tools": ["rss"],
        "prompts": ["prompts/x/main.md"],
        "output": "reports/demo/{date}.html",
        "post": {"pdf": False},
    }), "utf-8")

    # Fake claude: writes a stub HTML to whatever path follows "to "
    fake_claude = tmp_path / "fake-claude.sh"
    fake_claude.write_text(textwrap.dedent("""\
        #!/usr/bin/env bash
        # parse the -p prompt; extract the OUTPUT_PATH after 'write to '
        PROMPT=""
        while [[ $# -gt 0 ]]; do
          if [[ "$1" == "-p" ]]; then PROMPT="$2"; shift 2; else shift; fi
        done
        OUT=$(printf "%s" "$PROMPT" | grep -oE 'write to [^ ]+' | awk '{print $3}')
        mkdir -p "$(dirname "$OUT")"
        printf '<html><body>fake report</body></html>' > "$OUT"
        echo "fake claude done"
    """), "utf-8")
    fake_claude.chmod(0o755)

    env = os.environ.copy()
    env["FINANCE_WORKFLOWS_ROOT"] = str(tmp_path)
    env["FINANCE_WORKFLOWS_CLAUDE_BIN"] = str(fake_claude)
    env["FINANCE_WORKFLOWS_PYTHON_BIN"] = sys.executable
    env["FINANCE_WORKFLOWS_DATE"] = "2026-05-21"

    r = subprocess.run([sys.executable, str(FW / "run-workflow.py"), "demo"],
                       env=env, capture_output=True, text=True)
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    out_html = tmp_path / "reports" / "demo" / "2026-05-21.html"
    assert out_html.exists()
    assert "fake report" in out_html.read_text("utf-8")
    # mcp.json was rendered with only rss
    mcp_json = tmp_path / "mcp" / "mcp.json"
    assert mcp_json.exists()
    assert set(json.loads(mcp_json.read_text("utf-8"))["mcpServers"].keys()) == {"rss"}
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_run_workflow.py -v
```

Expected: FAIL — `run-workflow.py` not found.

- [ ] **Step 3: Implement** `finance-workflows/run-workflow.py`:

```python
#!/usr/bin/env python3
"""finance-workflows orchestrator. Usage: python3 run-workflow.py <name>"""
from __future__ import annotations
import argparse, datetime as _dt, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent

# Make sibling modules importable
sys.path.insert(0, str(HERE))
from workflow import load_workflow, resolve_output, WorkflowError  # noqa
from mcp_render import render_mcp, derive_allowed_tools, McpRenderError  # noqa
from prompt_build import build_prompt  # noqa


# Tool map: every MCP server in the template + the tool ids it exports.
# Adding a new MCP server = add it to the template + here.
TOOL_MAP = {
    "yt-dlp": [
        "ytdlp_search_videos",
        "ytdlp_download_transcript",
        "ytdlp_transcript_page",
    ],
    "rss": ["rss_fetch"],
    "web-fetch": ["web_fetch", "web_extract_article"],
}


def _resolve_root() -> pathlib.Path:
    """Env override → tests; else this file's directory."""
    return pathlib.Path(os.environ.get("FINANCE_WORKFLOWS_ROOT", str(HERE))).resolve()


def _today_iso() -> str:
    return os.environ.get("FINANCE_WORKFLOWS_DATE") or _dt.date.today().isoformat()


def _claude_bin() -> str:
    return os.environ.get("FINANCE_WORKFLOWS_CLAUDE_BIN") or "claude"


def _python_bin(root: pathlib.Path) -> str:
    env = os.environ.get("FINANCE_WORKFLOWS_PYTHON_BIN")
    if env: return env
    venv_py = root / "mcp" / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.exists() else sys.executable


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="workflow name (workflows/<name>.json)")
    args = ap.parse_args(argv)
    root = _resolve_root()

    try:
        cfg = load_workflow(args.name, root)
    except WorkflowError as e:
        print(f"[workflow] {e}", file=sys.stderr); return 2

    date = _today_iso()
    output_rel = resolve_output(cfg, date)
    output_abs = (root / output_rel).resolve()
    output_abs.parent.mkdir(parents=True, exist_ok=True)
    logs_dir = output_abs.parent / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{date}-{int(time.time())}.log"

    # Render mcp.json with just this workflow's tools
    mcp_dir = str(root / "mcp")
    tmpl = root / "mcp" / "mcp.json.tmpl"
    out_mcp = root / "mcp" / "mcp.json"
    try:
        mcp_json_path = render_mcp(tools=cfg.tools, mcp_dir=mcp_dir,
                                   python_bin=_python_bin(root),
                                   tmpl_path=tmpl, out_path=out_mcp)
    except (FileNotFoundError, McpRenderError) as e:
        print(f"[mcp_render] {e}", file=sys.stderr); return 3

    allowed = derive_allowed_tools(cfg.tools, TOOL_MAP)

    # Build the prompt
    prompt = build_prompt(
        prompt_paths=[root / p for p in cfg.prompts],
        substitutions={
            "DATE": date,
            "OUTPUT_PATH": str(output_abs),
            "WORKFLOW_NAME": cfg.name,
            "SOURCES_JSON": json.dumps([s.__dict__ for s in cfg.sources],
                                       ensure_ascii=False),
        },
    )

    # Invoke claude -p
    bin_ = _claude_bin()
    argv_ = [bin_, "-p", prompt,
            "--model", cfg.model,
            "--max-turns", str(cfg.max_turns),
            "--mcp-config", str(mcp_json_path),
            "--strict-mcp-config",
            "--allowedTools", ",".join(allowed)]
    print(f"[run] {cfg.name} → {output_abs}", file=sys.stderr)
    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"=== argv ===\n{argv_[:1] + ['-p', '<...prompt elided...>'] + argv_[3:]}\n\n")
        logf.flush()
        proc = subprocess.run(argv_, cwd=str(root), stdout=logf, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        print(f"[claude] exited {proc.returncode} — see {log_path}", file=sys.stderr)
        return proc.returncode
    if not output_abs.exists():
        print(f"[claude] exit 0 but no HTML at {output_abs} — see {log_path}", file=sys.stderr)
        return 4

    # Optional PDF (best-effort)
    if cfg.post.pdf:
        chrome_candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        ]
        chrome = next((c for c in chrome_candidates if pathlib.Path(c).exists()), None)
        if chrome:
            pdf_path = output_abs.with_suffix(".pdf")
            subprocess.run([chrome, "--headless", f"--print-to-pdf={pdf_path}",
                            str(output_abs)], cwd=str(root), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Optional history (best-effort)
    if cfg.history is not None:
        try:
            hint = ("Read the following HTML and produce ONE LINE of compact JSON "
                    f"with exactly these keys: {cfg.history.fields}. No prose, "
                    "no markdown fences, just one JSON object.\n\n"
                    f"---\n{output_abs.read_text('utf-8')}\n---")
            hist = subprocess.run(
                [bin_, "-p", hint, "--model", cfg.history.summarize_with,
                 "--max-turns", "1"],
                cwd=str(root), capture_output=True, text=True)
            line = (hist.stdout or "").strip().splitlines()[-1] if hist.stdout else ""
            if line.startswith("{") and line.endswith("}"):
                obj = json.loads(line)
                obj["date"] = date
                obj["output"] = output_rel
                hist_path = output_abs.parent / "_history.jsonl"
                with hist_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[history] skipped: {e}", file=sys.stderr)

    print(f"[run] ok → {output_abs}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/test_run_workflow.py -v
```

Expected: PASS (1/1).

- [ ] **Step 5: Full suite**

```bash
cd finance-workflows
.venv/bin/python -m pytest tests/ -v
```

Expected: all PASS (Tasks 2/3/4/5/6/7 tests, ~16 tests).

- [ ] **Step 6: Commit + push**

```bash
git add finance-workflows/run-workflow.py finance-workflows/tests/test_run_workflow.py
git commit -m "feat(finance-workflows): run-workflow.py orchestrator (loader+mcp_render+prompt_build+claude+pdf+history)"
git push origin main
```

---

### Task 8: crypto-daily workflow + prompts

**Files:**
- Create: `finance-workflows/workflows/crypto-daily.json`
- Create: `finance-workflows/prompts/shared/faithfulness.md`
- Create: `finance-workflows/prompts/crypto/{framework,voice,main}.md`

No unit tests (prompts/JSON). Validated by Task 9 confirming run.

- [ ] **Step 1: Create `workflows/crypto-daily.json`:**

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

- [ ] **Step 2: Create `prompts/shared/faithfulness.md`:**

```markdown
# 寫作鐵則（所有 workflow 共用）

- **禁止編造因果**：不可寫「因為 X 所以 Y」、「主戰場」、「演算法在推」這類未經證實的因果論述。
- **只引用來源真實出現的內容**：立場、數字、觀點都必須能對應到逐字稿／文章原文。
- **不確定就省略**，不要硬填。原話引用必須逐字、不可改寫翻譯。
- 若資料缺漏或來源不可用，明確寫「**原因不明，持續觀察**」或「**該段資料不可用**」。
- 不對未來價格做斷言；用機率、條件式語言。
```

- [ ] **Step 3: Create `prompts/crypto/framework.md`:**

```markdown
# 加密貨幣分析框架（top-down）

報告依此推導，避免一上來就跳個股/個幣論述：

1. **總經背景**：DXY、美元實質利率（10Y TIPS）、Fed 政策預期；對風險資產的方向性意義。
2. **加密大盤**：BTC、ETH 24h/7d 變化；BTC dominance；ETH/BTC ratio；總市值；衍生品資金費率與未平倉。
3. **板塊輪動**：DeFi / L2 / AI tokens / RWA / meme 的相對表現；資金從哪流到哪。
4. **新聞 / 監管 / 鏈上事件**：當日具體事件（駭客、ETF 流入流出、監管動作、解鎖、升級）。
5. **總結信號**：偏多 / 中性 / 偏空 + 信心 + 隔日觀察重點。

每一層只寫「來源實際說的 + 來源實際引用的數字」。
```

- [ ] **Step 4: Create `prompts/crypto/voice.md`:**

```markdown
# 加密報告語氣

- 理性、數據導向、**中性偏謹慎**；避免 shilling、「to the moon」、「100x」、「don't miss this」這類辭彙。
- 不確定就標不確定；用機率語言（「短期偏多」、「若 X 跌破 Y 則…」）而非斷言。
- 對影片來源用「他指出 / 他認為 / 他提醒」客觀轉述。
- 加密圈消息真假混雜：明確區分「鏈上事實」、「來源轉述的傳聞」、「個人解讀」。
```

- [ ] **Step 5: Create `prompts/crypto/main.md`:**

```markdown
# 加密貨幣每日簡報任務

你的任務:為 ${WORKFLOW_NAME}(${DATE})產出一份**加密貨幣每日簡報** HTML,寫到 `${OUTPUT_PATH}`。

來源宣告(JSON):
```
${SOURCES_JSON}
```

## 步驟

1. **抓 YouTube 來源**:對每個 `kind=youtube` 的來源,用 `mcp__yt-dlp__ytdlp_search_videos(query=<source.search_query>, maxResults=2)` 找今日(或最近一支)影片;選 `upload_date == ${DATE}` 的那筆,沒有就用日期最新那筆。
2. **逐字稿**:對選定的影片從 `page=0` 起呼叫 `mcp__yt-dlp__ytdlp_transcript_page(video_url, page=<n>, page_size=12000)`,讀 `total_pages`,**逐頁讀到 page == total_pages-1** 拼成完整逐字稿。若 source 是 `none`(無字幕)就在報告中標註該影片不可用、繼續其餘來源。
3. **抓 web/rss 來源**:對 `kind=web` 的來源,先試 `mcp__rss__rss_fetch(url=<source.rss>, max_items=15)` —— 如果回空,改用 `mcp__web-fetch__web_extract_article(url=<source.url>)` 抓首頁找今日(${DATE})文章的連結,再對每個連結 `web_extract_article` 抓內文。重點是**今日新發布**的文章。
4. **綜合分析**:依參考的 framework + voice,做 top-down 整合,**不要對任何一個來源做整段流水帳**,要交叉比對:大家觀點一致 vs 分歧的地方明確列出來。
5. **產出 HTML**:用 `Write` 把完整 HTML 寫到 `${OUTPUT_PATH}`。包含**所有以下段落,順序固定**:
   - **市場快照** —— BTC/ETH 價、24h 變化、總市值、BTC dominance、資金費率;只列觀察事實,不下因果。
   - **加密總覽** —— top-down 整合(總經 → 大盤 → 板塊輪動);區分「鏈上事實」「來源轉述傳聞」「個人解讀」。
   - **影片+文章重點** —— 對每個來源列 3-5 條他的核心觀點 + 他引用的數字 + 1-2 句逐字原話(逐字、不改寫)。
   - **風險** —— 今日具體可觀察的風險點(駭客/解鎖/監管動作/技術指標逼近警戒);不要寫泛論「波動可能很大」這種廢話。
   - **報告總結** —— 整體基調(偏多/中性/偏謹慎) + 信心 0-10 + 3-5 條今日關鍵訊號 + 對隔日的觀察重點。**必須實際寫進 HTML,不可只放在你的回覆訊息**。

## 嚴格規則

- 寫作鐵則(faithfulness.md)優先,違反即任務失敗。
- 若任一來源完全不可用(字幕缺、網站 503、RSS 空),明確在 HTML 中標註該來源不可用,**用剩下的來源繼續產出**,不要因此放棄。
- HTML 要乾淨可讀(基本 CSS、表格、可以有 emoji 訊號塊但不過度);不要寫 broken markup。
- 完成 Write 後即結束,不要做額外步驟。
```

- [ ] **Step 6: Commit + push**

```bash
git add finance-workflows/workflows/crypto-daily.json finance-workflows/prompts
git commit -m "feat(finance-workflows): crypto-daily workflow + prompts (faithfulness/framework/voice/main)"
git push origin main
```

---

### Task 9: CLAUDE.md + README + cron example

**Files:**
- Create: `finance-workflows/CLAUDE.md`
- Create: `finance-workflows/README.md`
- Create: `finance-workflows/cron.example.sh`

- [ ] **Step 1: Create `CLAUDE.md`:**

```markdown
# finance-workflows — instructions for working in this folder

This folder is a lean Python workflow runner for producing daily financial
reports. It is parallel to `../studio/` (which is being archived). Read
`../docs/superpowers/specs/2026-05-21-finance-workflows-design.md` for the
full design.

## Run a workflow manually

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py crypto-daily
```

The HTML lands at `reports/<name>/<YYYY-MM-DD>.html`. Logs are at
`reports/<name>/_logs/<date>-<ts>.log`.

## Add a new workflow

1. Drop `workflows/<new-name>.json` (copy `crypto-daily.json` and edit).
2. Add `prompts/<new-domain>/{framework,voice,main}.md` if it's a new domain.
   For incremental additions reuse existing prompts in `prompts/shared/`.
3. If you need a source kind we don't have yet (e.g. Twitter, Substack), see
   "Add a source kind / MCP server" below.
4. Test: `mcp/.venv/bin/python run-workflow.py <new-name>` — produces HTML;
   inspect, iterate on prompts.

**Adding a workflow MUST be config + prompts only. No edits to `run-workflow.py`
or the existing MCP servers.**

## Add a source kind / MCP server

A "source kind" is wired through an MCP server. To add e.g. CoinGecko:

1. Write `mcp/servers/coingecko_server.py` (FastMCP, follow the patterns in
   `rss_server.py` / `web_fetch_server.py`: tools never raise, return shaped
   dicts on failure).
2. Add tests at `tests/test_coingecko_server.py` (monkeypatch the network
   call, assert returned shape).
3. Add the server to `mcp/mcp.json.tmpl`.
4. Add an entry to `TOOL_MAP` in `run-workflow.py` mapping the server name to
   its tool ids (this is the ONLY edit to runner code per new server).
5. Workflows can now declare `"tools": [..., "coingecko"]` and use
   `mcp__coingecko__<tool>`.

## Trust assumptions

- `web-fetch` makes arbitrary outbound HTTP. This is a local single-user tool;
  we accept this. Don't deploy as a service without adding a URL allow-list.
- `claude` must be authenticated before cron will work — run `claude`
  interactively at least once on this machine.

## Conventions

- All tools must NEVER raise; return shaped failure dicts (status, empty list).
- Prompts use `${TOKEN}` substitution; `{date}` is for the `output:` path
  template only.
- The runner is ≤200 LoC; don't grow it. New capability = new MCP server +
  workflow.json field.
```

- [ ] **Step 2: Create `README.md`:**

```markdown
# finance-workflows

Lean Python runner that produces daily financial reports from declarative
`workflows/*.json` files. Drives headless `claude -p` with a per-workflow
MCP server set and concatenated prompts.

- **Spec:** `../docs/superpowers/specs/2026-05-21-finance-workflows-design.md`
- **How to work here:** `CLAUDE.md`

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
```

- [ ] **Step 3: Create `cron.example.sh`:**

```bash
#!/usr/bin/env bash
# Example cron driver. Crontab line (weekday 08:30 Asia/Taipei):
#   30 8 * * 1-5  /path/to/cron.example.sh crypto-daily >> /tmp/fw-cron.log 2>&1

set -euo pipefail
WORKFLOW="${1:?usage: cron.example.sh <workflow-name>}"
FW_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$FW_ROOT"
"$FW_ROOT/mcp/.venv/bin/python" run-workflow.py "$WORKFLOW"
```

Make it executable:
```bash
chmod +x finance-workflows/cron.example.sh
```

- [ ] **Step 4: Commit + push**

```bash
git add finance-workflows/CLAUDE.md finance-workflows/README.md finance-workflows/cron.example.sh
git commit -m "docs(finance-workflows): CLAUDE.md + README + cron example"
git push origin main
```

---

### Task 10: Confirming run + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

Operational (controller-run).

- [ ] **Step 1:** Free port 3100 (any leftover studio server), then from repo root:

```bash
cd finance-workflows
mcp/.venv/bin/python run-workflow.py crypto-daily
```

Expect ~10–15 min runtime. The shell command runs in foreground; capture exit code + path of produced HTML.

- [ ] **Step 2:** Verify against ground truth (no glossing):
  - `reports/crypto-daily/<today>.html` exists, contains **all 5 required sections** (市場快照 / 加密總覽 / 影片+文章重點 / 風險 / 報告總結) and cites real content from the 2 YT channels + zombit. Open it.
  - `reports/crypto-daily/<today>.pdf` exists.
  - `reports/crypto-daily/_history.jsonl` has a new line with the 4 declared fields (`overall_stance`, `confidence`, `top_signals`, `top_risks`).
  - `_logs/<today>-*.log` shows the claude stdout/stderr trail.
  - `mcp/mcp.json` contains exactly `{yt-dlp, rss, web-fetch}` (no twse/yahoo/fred/sqlite).
  - Adding the 2nd workflow would be config-only: confirm by `grep -rn "crypto-daily\|crypto_punks\|BTV_CN\|zombit" finance-workflows/run-workflow.py finance-workflows/workflow.py finance-workflows/mcp_render.py finance-workflows/prompt_build.py finance-workflows/mcp/servers/ 2>/dev/null` — expect **zero matches** (proves the workflow name and source names live only in JSON/prompts, not in TS/Py code).

- [ ] **Step 3:** Append a dated **"finance-workflows v1 — crypto-daily MVP"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md` with: pass count of the 5 acceptance items, the zero-Py-refs grep result, sample lines from `_history.jsonl`, and any honest caveat (transient `claude -p` socket error → retry; web source unavailable → degraded but completed). Commit + push. KG `record_experience`.

---

## Self-Review

**1. Spec coverage:**
- §2 MVP scope (parallel finance-workflows/, crypto-daily, JSONL history opt-in) → Tasks 1, 7, 8.
- §3 architecture (workflow.json → render mcp → concat prompts → claude -p → HTML → optional PDF/history) → Tasks 5, 6, 7.
- §4 workflow.json schema (incl. history) → Task 4 (dataclass + validator + history sub-shape).
- §5 file structure → Tasks 1 + 7 + 8 collectively create every path.
- §6 component responsibilities → Tasks 2/3 (MCP servers), 4 (loader), 5 (mcp_render), 6 (prompt_build), 7 (orchestrator).
- §7 crypto-daily concrete details → Task 8.
- §8 migration path (studio unaffected) → no code touches studio/ in any task; verified by absence.
- §9 error handling (graceful degrade, exit codes) → orchestrator (Task 7).
- §10 honest limitations → documented in CLAUDE.md (Task 9) + acknowledged in Task 10 evidence.
- §11 acceptance criteria → Task 10 walks each.

**2. Placeholder scan:** No TBD/TODO. Every code/prompt is complete. The fake-claude shim in Task 7's test is fully specified bash; the runner's claude-bin override env var is documented and used.

**3. Type consistency:** `Workflow`/`Source`/`Post`/`History` dataclass fields used by Task 7 match definitions in Task 4. `TOOL_MAP` keys in Task 7 match server names in Task 1's `mcp.json.tmpl` and the `tools` field semantics in Task 4. `derive_allowed_tools(servers, tool_map)` signature consistent across Task 5 def and Task 7 use. `render_mcp` kwargs identical across Task 5 def, Task 5 test, and Task 7 use. `build_prompt(prompt_paths, substitutions)` ditto. Output path resolution: `resolve_output(cfg, date)` returns relative (e.g. `reports/demo/2026-05-21.html`); Task 7 joins it with `root` to form an absolute used in `${OUTPUT_PATH}` and writes the HTML there — consistent end-to-end.

**Open risks (flagged):** (a) `ytdlp_search_videos` heuristic (keyword search, not channel feed) may miss the genuine latest on a slow YouTube ranking day — same limitation as studio's. If Task 10 shows wrong videos picked, a small follow-up adds a channel-feed-based tool. (b) `web_extract_article` on zombit may degrade if their HTML structure breaks readability heuristics; RSS-first fallback (the order in main.md) is the mitigation. (c) PDF depends on macOS Chrome path; on a non-Mac host the PDF step is skipped (best-effort) and that's not a run failure.
