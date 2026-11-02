"""End-to-end runner tests where post-processing ACTUALLY runs (2026-11-02).

The first salvage tests configured no history and no Telegram, so _post_process
was a no-op and mutations like "return at the top of _post_process" passed.
Here a fake `claude` binary serves both the main run and the history call, the
real scripts/notify_telegram.py is used, and only the network is stubbed:
httpx.Client (report push) and urllib.request.urlopen (failure alert)."""
import importlib.util, io, json, os, pathlib, shutil, sys, textwrap, time
import urllib.error

import pytest

FW = pathlib.Path(__file__).parents[1]
DATE = "2026-11-02"
LIMIT = "You've hit your 5-hour limit · resets 8:30am (Asia/Taipei)"


def _load_runner():
    spec = importlib.util.spec_from_file_location("run_workflow_pp", FW / "run-workflow.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class Net:
    """Captures every Telegram call; `md_reject` makes Markdown sends fail 400."""
    def __init__(self, md_reject=False):
        self.pushes, self.alerts, self.md_reject = [], [], md_reject

    def client(self, *a, **k):
        net = self

        class R:
            def __init__(self, code, text=""):
                self.status_code, self.text = code, text

        class C:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def post(self, url, data=None, files=None):
                net.pushes.append({"url": url, "data": dict(data or {}),
                                   "file": bool(files)})
                if net.md_reject and (data or {}).get("parse_mode") == "Markdown":
                    return R(400, "Bad Request: can't parse entities")
                return R(200)
        return C()

    def urlopen(self, url, data=None, timeout=None):
        from urllib.parse import parse_qs
        fields = {k: v[0] for k, v in parse_qs(data.decode()).items()}
        self.alerts.append(fields)
        if self.md_reject and fields.get("parse_mode") == "Markdown":
            raise urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(b""))
        return io.BytesIO(b"{}")

    def messages(self):
        return [p["data"]["text"] for p in self.pushes if p["url"].endswith("sendMessage")]


@pytest.fixture
def env(tmp_path, monkeypatch):
    root = tmp_path
    (root / "workflows").mkdir()
    (root / "prompts" / "x").mkdir(parents=True)
    (root / "prompts" / "x" / "main.md").write_text("write to ${OUTPUT_PATH} please\n")
    (root / "mcp" / "servers").mkdir(parents=True)
    (root / "mcp" / "mcp.json.tmpl").write_text(json.dumps({"mcpServers": {
        "rss": {"command": "@PY@", "args": ["@MCPDIR@/servers/rss_server.py"]}}}))
    (root / "scripts").mkdir()
    shutil.copy(FW / "scripts" / "notify_telegram.py", root / "scripts")
    (root / "workflows" / "demo.json").write_text(json.dumps({
        "name": "demo", "model": "m", "max_turns": 5,
        "sources": [{"kind": "rss", "name": "z", "url": "https://example.com"}],
        "tools": ["rss"], "prompts": ["prompts/x/main.md"],
        "output": "reports/demo/{date}.html",
        "post": {"pdf": False, "telegram": "TELEGRAM_TOPIC_DEMO"},
        "history": {"format": "jsonl", "summarize_with": "h",
                    "fields": ["overall_stance", "confidence", "top_signals"]},
    }))
    for k, v in {"FINANCE_WORKFLOWS_ROOT": str(root), "FINANCE_WORKFLOWS_DATE": DATE,
                 "FINANCE_WORKFLOWS_PYTHON_BIN": sys.executable,
                 "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c",
                 "TELEGRAM_TOPIC_DEMO": "9"}.items():
        monkeypatch.setenv(k, v)
    sys.modules.pop("notify_telegram", None)       # import the tmp-root copy
    yield root
    sys.modules.pop("notify_telegram", None)


def _fake_claude(root, monkeypatch, main_body, stance="今天的觀點 BTCUSD_PERP"):
    """main run executes `main_body`; the history call (--max-turns 1) prints JSON."""
    hist = json.dumps({"overall_stance": stance, "confidence": 6,
                       "top_signals": ["資金費率 BTCUSD_PERP 轉正"]}, ensure_ascii=False)
    script = root / "fake-claude.sh"
    script.write_text("#!/usr/bin/env bash\n" + textwrap.dedent(f"""\
        PROMPT=""; HIST=0
        while [[ $# -gt 0 ]]; do
          case "$1" in
            -p) PROMPT="$2"; shift 2;;
            --max-turns) [[ "$2" == "1" ]] && HIST=1; shift 2;;
            *) shift;;
          esac
        done
        if [[ $HIST == 1 ]]; then echo '{hist}'; exit 0; fi
        OUT=$(printf "%s" "$PROMPT" | grep -oE 'write to [^ ]+' | awk '{{print $3}}')
        """) + textwrap.dedent(main_body))
    script.chmod(0o755)
    monkeypatch.setenv("FINANCE_WORKFLOWS_CLAUDE_BIN", str(script))


WRITE_HTML = """\
    mkdir -p "$(dirname "$OUT")"
    printf '<html><body>full report</body></html>' > "$OUT"
"""


def _run(monkeypatch, net, *argv):
    import httpx
    monkeypatch.setattr(httpx, "Client", net.client)
    m = _load_runner()
    monkeypatch.setattr(m.urllib.request, "urlopen", net.urlopen)
    return m.main(["demo", *argv])


def _history(root):
    p = root / "reports" / "demo" / "_history.jsonl"
    return [json.loads(l) for l in p.read_text().splitlines()] if p.exists() else []


def test_salvaged_run_alerts_then_pushes_todays_summary(env, monkeypatch):
    _fake_claude(env, monkeypatch, WRITE_HTML + f'echo "{LIMIT}"\nexit 1\n')
    net = Net()
    assert _run(monkeypatch, net) == 0
    alert = net.alerts[0]["text"]
    assert "報告已救回" in alert and "跑失敗" not in alert
    # the NOTE line itself — the log tail inside ``` also contains the CLI text
    assert "額度用完，8:30am (Asia/Taipei) 重置" in alert and "--post-only" in alert
    assert [h["date"] for h in _history(env)] == [DATE]
    msg = net.messages()[0]
    assert "今天的觀點" in msg and "BTCUSD\\_PERP" in msg   # escaped for Markdown


def test_unsalvageable_run_alerts_rerun_and_pushes_nothing(env, monkeypatch):
    _fake_claude(env, monkeypatch, f'echo "{LIMIT}"\nexit 1\n')
    net = Net()
    assert _run(monkeypatch, net) == 1
    assert "需要補跑" in net.alerts[0]["text"] and "跑失敗 (rc=1)" in net.alerts[0]["text"]
    assert net.pushes == [] and _history(env) == []


def test_post_only_pushes_and_never_duplicates_history(env, monkeypatch):
    _fake_claude(env, monkeypatch, 'touch "$OUT.main-called"\nexit 99\n')
    html = env / "reports" / "demo" / f"{DATE}.html"
    html.parent.mkdir(parents=True)
    html.write_text("<html>done earlier</html>")
    net = Net()
    assert _run(monkeypatch, net, "--post-only") == 0
    assert _run(monkeypatch, net, "--post-only") == 0
    assert not pathlib.Path(f"{html}.main-called").exists()
    assert [h["date"] for h in _history(env)] == [DATE]      # one entry, not two
    assert len(net.messages()) == 2


def test_stale_brief_from_earlier_run_is_not_pushed(env, monkeypatch):
    """morning-briefing writes the HTML, then _brief.md one turn later. A run
    salvaged between the two must not push the previous day's brief."""
    out_dir = env / "reports" / "demo"; out_dir.mkdir(parents=True)
    brief = out_dir / "_brief.md"
    brief.write_text("📰 2026-10-30 FRIDAY BRIEF")
    os.utime(brief, (time.time() - 3 * 86400,) * 2)
    _fake_claude(env, monkeypatch, WRITE_HTML + f'echo "{LIMIT}"\nexit 1\n')
    net = Net()
    assert _run(monkeypatch, net) == 0
    msg = net.messages()[0]
    assert "FRIDAY" not in msg and "今天的觀點" in msg


def test_fresh_brief_still_wins(env, monkeypatch):
    _fake_claude(env, monkeypatch, WRITE_HTML + textwrap.dedent("""\
        printf '📰 today brief' > "$(dirname "$OUT")/_brief.md"
        exit 0
    """))
    net = Net()
    assert _run(monkeypatch, net) == 0
    assert net.messages() == ["📰 today brief"]


def test_markdown_rejection_falls_back_to_plain_text(env, monkeypatch):
    _fake_claude(env, monkeypatch, WRITE_HTML + f'echo "{LIMIT}"\nexit 1\n')
    net = Net(md_reject=True)
    assert _run(monkeypatch, net) == 0
    plain_alerts = [a for a in net.alerts if "parse_mode" not in a]
    plain_pushes = [p for p in net.pushes if p["url"].endswith("sendMessage")
                    and "parse_mode" not in p["data"]]
    assert plain_alerts and plain_pushes                     # both still delivered
