import importlib.util, json, os, pathlib, subprocess, sys, textwrap

REPO = pathlib.Path(__file__).parents[2]  # /…/new_financial-report-system
FW = REPO / "finance-workflows"


def _load_runner():
    p = FW / "run-workflow.py"
    spec = importlib.util.spec_from_file_location("run_workflow", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_load_dotenv_reads_local_env_without_overriding(tmp_path, monkeypatch):
    m = _load_runner()
    (tmp_path / ".env").write_text(
        "# comment\n\nFRED_API_KEY=fred123\nGROQ_API_KEY=gsk_abc\nBLANKLINE\n", "utf-8")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "shell_wins")  # existing env must win
    m._load_dotenv(tmp_path)
    assert os.environ["FRED_API_KEY"] == "fred123"   # loaded from .env
    assert os.environ["GROQ_API_KEY"] == "shell_wins"  # not overridden


def test_load_dotenv_missing_file_is_silent(tmp_path):
    m = _load_runner()
    m._load_dotenv(tmp_path / "nope")  # no .env here — must not raise


# ── claude retry-on-transient ──────────────────────────────────────────────────

def test_is_transient_detects_known_patterns():
    m = _load_runner()
    assert m._is_transient("blah blah\nAPI Error: The socket connection was closed unexpectedly\n")
    assert m._is_transient("Server disconnected without sending a response")
    assert m._is_transient("connect ECONNRESET")
    assert m._is_transient("connect ETIMEDOUT")
    # HTTP-level timeouts (regression: 5/26 crypto-daily failure surfaced
    # literally as "Request timed out", missed by the original whitelist).
    assert m._is_transient("Request timed out")
    assert m._is_transient("Operation timed out")
    assert m._is_transient("fetch failed")
    # DNS failures (regression: 2026-09-01 07:00 morning-briefing + crypto-daily
    # both died with "API Error: Can't reach the API server ... (ENOTFOUND)".
    # Neither had a matching pattern → no retry → user got no reports).
    assert m._is_transient(
        "API Error: Can't reach the API server — check your internet or DNS (ENOTFOUND)"
    )
    assert m._is_transient("Error: getaddrinfo ENOTFOUND api.anthropic.com")
    assert m._is_transient("getaddrinfo EAI_AGAIN")
    # Anthropic 5xx mid-stream (regression: 2026-09-02 07:00 morning-briefing
    # died on this exact string after reading extras + news files. Only that
    # one workflow failed — not auth, not DNS).
    assert m._is_transient(
        "API Error: Server error mid-response. The response above may be incomplete."
    )
    assert m._is_transient('{"type":"overloaded_error"}')
    assert m._is_transient("500 Internal server error")
    assert not m._is_transient("Error: max-turns exceeded")
    assert not m._is_transient("")


def test_retry_returns_immediately_on_success(tmp_path):
    m = _load_runner()
    calls = []
    runner = lambda *a, **k: (calls.append(1), (0, ""))[1]
    slept = []
    rc = m._run_claude_with_retry(["claude"], tmp_path / "l", tmp_path,
                                  runner=runner, sleeper=slept.append)
    assert rc == 0 and len(calls) == 1 and slept == []


def test_retry_on_transient_then_succeed(tmp_path):
    m = _load_runner()
    results = [(1, "API Error: socket connection was closed"), (0, "")]
    calls = []
    def runner(*a, **k):
        calls.append(1); return results.pop(0)
    slept = []
    rc = m._run_claude_with_retry(["claude"], tmp_path / "l", tmp_path,
                                  attempts=3, backoff=5,
                                  runner=runner, sleeper=slept.append)
    assert rc == 0 and len(calls) == 2 and slept == [5]


def test_no_retry_on_non_transient(tmp_path):
    m = _load_runner()
    calls = []
    def runner(*a, **k):
        calls.append(1); return (1, "Error: max-turns exceeded")
    slept = []
    rc = m._run_claude_with_retry(["claude"], tmp_path / "l", tmp_path,
                                  runner=runner, sleeper=slept.append)
    assert rc == 1 and len(calls) == 1 and slept == []  # surfaced immediately


def test_retry_gives_up_after_all_attempts(tmp_path):
    m = _load_runner()
    calls = []
    def runner(*a, **k):
        calls.append(1); return (1, "Server disconnected without sending a response")
    slept = []
    rc = m._run_claude_with_retry(["claude"], tmp_path / "l", tmp_path,
                                  attempts=3, backoff=2,
                                  runner=runner, sleeper=slept.append)
    assert rc == 1 and len(calls) == 3 and slept == [2, 6]  # backoff *=3 each time

def test_orchestrator_writes_report_with_fake_claude(tmp_path):
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

    # Fake claude: writes a stub HTML to whatever path follows "write to "
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
