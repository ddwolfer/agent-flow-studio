#!/usr/bin/env python3
"""finance-workflows orchestrator. Usage: python3 run-workflow.py <name>"""
import argparse, datetime as _dt, json, os, pathlib, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent

# Make sibling modules importable
sys.path.insert(0, str(HERE))
from workflow import load_workflow, resolve_output, WorkflowError  # noqa
from mcp_render import render_mcp, derive_allowed_tools, McpRenderError  # noqa
from prompt_build import build_prompt  # noqa
from history_extract import extract_first_json_object  # noqa


# Tool map: every MCP server in the template + the tool ids it exports.
# Adding a new MCP server = add it to the template + here.
TOOL_MAP = {
    "yt-dlp": [
        "ytdlp_search_videos",
        "ytdlp_latest_from_channel",
        "ytdlp_download_transcript",
        "ytdlp_transcript_page",
    ],
    "rss": ["rss_fetch"],
    "web-fetch": ["web_fetch", "web_extract_article"],
    "fred": ["fred_get_series"],
    "yahoo-finance": ["get_stock_info", "get_historical_stock_prices"],
    "twse": [
        "get_daily_market_trading_info",
        "get_market_index_info",
        "get_margin_trading_info",
        "get_stock_daily_trading",
        "get_foreign_investment_by_industry",
    ],
}


def _load_env_subs(root):
    """Read FRED_API_KEY (and any other @KEY@ env subs) from the inherited
    .env file or current process env. Returns a dict suitable for render_mcp's
    `env_subs=` kwarg; missing values are simply omitted (template's @KEY@ stays
    literal — see render_mcp docstring)."""
    subs = {}
    # 1) process env wins
    if os.environ.get("FRED_API_KEY"):
        subs["FREDKEY"] = os.environ["FRED_API_KEY"]
        return subs
    # 2) fall back to the inherited tool's .env
    env_file = root / ".." / "financial-report-system" / "scripts" / ".env"
    try:
        for line in env_file.read_text("utf-8").splitlines():
            if line.startswith("FRED_API_KEY="):
                subs["FREDKEY"] = line.split("=", 1)[1].strip()
                break
    except FileNotFoundError:
        pass
    return subs


def _resolve_root():
    """Env override → tests; else this file's directory."""
    return pathlib.Path(os.environ.get("FINANCE_WORKFLOWS_ROOT", str(HERE))).resolve()


def _today_iso():
    return os.environ.get("FINANCE_WORKFLOWS_DATE") or _dt.date.today().isoformat()


def _claude_bin():
    return os.environ.get("FINANCE_WORKFLOWS_CLAUDE_BIN") or "claude"


def _python_bin(root):
    env = os.environ.get("FINANCE_WORKFLOWS_PYTHON_BIN")
    if env: return env
    venv_py = root / "mcp" / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.exists() else sys.executable


def main(argv=None):
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
                                   tmpl_path=tmpl, out_path=out_mcp,
                                   env_subs=_load_env_subs(root))
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
            hint = ("Read the following HTML and produce a single JSON object "
                    f"with exactly these keys: {cfg.history.fields}. Prefer a bare "
                    "JSON object, but prose/markdown fences around it are tolerated.\n\n"
                    f"---\n{output_abs.read_text('utf-8')}\n---")
            hist = subprocess.run(
                [bin_, "-p", hint, "--model", cfg.history.summarize_with,
                 "--max-turns", "1"],
                cwd=str(root), capture_output=True, text=True)
            obj = extract_first_json_object(hist.stdout or "")
            if obj is not None:
                obj["date"] = date
                obj["output"] = output_rel
                hist_path = output_abs.parent / "_history.jsonl"
                with hist_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            else:
                print("[history] skipped: stdout did not contain a parseable JSON object",
                      file=sys.stderr)
        except Exception as e:
            print(f"[history] skipped: {e}", file=sys.stderr)

    print(f"[run] ok → {output_abs}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
