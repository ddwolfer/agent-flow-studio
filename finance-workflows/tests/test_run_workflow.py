import json, os, pathlib, subprocess, sys, textwrap

REPO = pathlib.Path(__file__).parents[2]  # /…/new_financial-report-system
FW = REPO / "finance-workflows"

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
