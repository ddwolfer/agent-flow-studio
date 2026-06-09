#!/usr/bin/env python3
"""finance-workflows orchestrator. Usage: python3 run-workflow.py <name>"""
import argparse, datetime as _dt, json, os, pathlib, signal, subprocess, sys, time
import urllib.request, urllib.parse

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
    "edgar": [
        "edgar_resolve_ticker",
        "edgar_latest_annual",
        "edgar_fetch_text",
    ],
    "knowledge-graph": [
        "store_knowledge", "connect_knowledge", "update_knowledge",
        "forget_knowledge", "search_memory", "get_knowledge",
        "list_knowledge", "traverse_graph",
        "record_experience", "recall_experience",
        "maintain_graph", "memory_stats",
    ],
}


def _load_dotenv(root):
    """Load finance-workflows/.env into os.environ (existing env wins, so the
    shell/cron can still override). This makes secrets like GROQ_API_KEY and
    FRED_API_KEY available to the child `claude` process and the MCP servers it
    spawns. Self-contained: no dependency on the legacy financial-report-system
    folder, so it can be deleted independently."""
    env_file = root / ".env"
    try:
        for line in env_file.read_text("utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if k and k not in os.environ:
                os.environ[k] = v
    except FileNotFoundError:
        pass


def _load_env_subs(root):
    """FRED_API_KEY → render_mcp's @FREDKEY@ template sub. Reads from os.environ
    (populated by _load_dotenv); missing value is simply omitted (template's
    @KEY@ stays literal — see render_mcp docstring)."""
    subs = {}
    if os.environ.get("FRED_API_KEY"):
        subs["FREDKEY"] = os.environ["FRED_API_KEY"]
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


# ── claude invocation: orphan-safe + retry-on-transient ────────────────────────
# Two production issues we hit (5/23 and 5/25 mornings):
#   1. `API Error: socket connection was closed unexpectedly` from claude — an
#      Anthropic API hiccup that kills the run with exit 1. Single point of
#      failure for a cron job. → retry on transient patterns only.
#   2. When claude dies mid-run (case above), its child MCP servers can outlive
#      it (orphaned), and one was found burning whisper CPU for 2.5h. → put
#      claude in its own process group and SIGTERM the whole group after wait.

_TRANSIENT_PATTERNS = (
    "socket connection was closed",
    "Server disconnected",
    "Connection reset",
    "ECONNRESET",
    "ETIMEDOUT",
    # HTTP-level timeouts — claude surfaces these literally when its request to
    # Anthropic times out (real hit on 5/26: "Request timed out"). Added after
    # discovering the original whitelist only covered socket-level disconnects.
    "Request timed out",
    "Operation timed out",
    "Read timeout",
    "Connect timeout",
    "fetch failed",
)


def _is_transient(log_tail: str) -> bool:
    return any(p in log_tail for p in _TRANSIENT_PATTERNS)


def _run_claude_once(argv_, log_path, root, timeout=3600):
    """Run claude once; reap orphan MCP children on exit. Returns (rc, log_tail)."""
    with log_path.open("a", encoding="utf-8") as logf:
        proc = subprocess.Popen(
            argv_, cwd=str(root), stdout=logf, stderr=subprocess.STDOUT,
            start_new_session=True,  # PG leader so we can reap its children
        )
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                rc = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                rc = 124  # convention: timeout
        finally:
            # Always SIGTERM the whole process group — reaps orphan MCP servers
            # that may outlive a crashed/killed claude. Harmless if nothing left.
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    try:
        tail = log_path.read_text("utf-8", errors="replace")[-4000:]
    except FileNotFoundError:
        tail = ""
    return rc, tail


def _run_claude_with_retry(argv_, log_path, root, *, attempts=3, backoff=30,
                           runner=_run_claude_once, sleeper=time.sleep):
    """Run claude with retries on TRANSIENT errors only (matches `_is_transient`).
    Non-transient failures surface immediately — never mask a real bug."""
    cur = backoff
    rc, tail = 0, ""
    for attempt in range(1, attempts + 1):
        rc, tail = runner(argv_, log_path, root)
        if rc == 0:
            return rc
        if attempt < attempts and _is_transient(tail):
            print(f"[claude] attempt {attempt} hit transient error; retrying in {cur}s",
                  file=sys.stderr)
            with log_path.open("a", encoding="utf-8") as logf:
                logf.write(f"\n=== retry after attempt {attempt} (transient) ===\n\n")
            sleeper(cur)
            cur *= 3  # 30 → 90 → (no further)
            continue
        return rc
    return rc


def _telegram_alert_failure(workflow_name, date, topic_env, rc, log_path):
    """Best-effort: post a failure alert to the same Telegram topic that would
    have received the success message. Silent on any error — alerting must
    never make the runner crash worse than it already has."""
    try:
        bot = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        if not (bot and chat and topic_env):
            return
        topic = (os.environ.get(topic_env) or "").strip()
        if not topic:
            return
        tail = ""
        try:
            tail = log_path.read_text("utf-8").splitlines()[-12:]
            tail = "\n".join(tail)[-1500:]
        except Exception:
            pass
        text = (f"⚠️ *{workflow_name}* `{date}` 跑失敗 (rc={rc})\n"
                f"Log: `{log_path.name}`\n"
                f"```\n{tail}\n```")
        data = urllib.parse.urlencode({
            "chat_id": chat, "message_thread_id": topic,
            "text": text, "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        }).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot}/sendMessage",
            data=data, timeout=15)
    except Exception as e:
        print(f"[telegram-alert] silent fail: {e}", file=sys.stderr)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="workflow name (workflows/<name>.json)")
    args = ap.parse_args(argv)
    root = _resolve_root()
    _load_dotenv(root)

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
                                   env_subs=_load_env_subs(root),
                                   root_dir=str(root.parent))
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
            # Skip the project-level .claude/settings.json (which registers
            # session-start / auto-recall / search-enforcer / Stop=auto-capture
            # hooks intended for the interactive Claude Code session). The Stop
            # hook in particular spawned an Opus agent at the end of every
            # workflow run — a real per-day cost for zero workflow value.
            # We previously tried --bare but it disables credentials loading
            # ("Not logged in"). --setting-sources user keeps auth + user-level
            # config while dropping the project hooks. KG access is via the
            # MCP server above, called explicitly from the workflow prompt.
            "--setting-sources", "user",
            "--allowedTools", ",".join(allowed)]
    print(f"[run] {cfg.name} → {output_abs}", file=sys.stderr)
    with log_path.open("w", encoding="utf-8") as logf:
        logf.write(f"=== argv ===\n{argv_[:1] + ['-p', '<...prompt elided...>'] + argv_[3:]}\n\n")
    rc = _run_claude_with_retry(argv_, log_path, root)
    if rc != 0:
        print(f"[claude] exited {rc} — see {log_path}", file=sys.stderr)
        _telegram_alert_failure(cfg.name, date, cfg.post.telegram, rc, log_path)
        return rc
    if not output_abs.exists():
        print(f"[claude] exit 0 but no HTML at {output_abs} — see {log_path}", file=sys.stderr)
        _telegram_alert_failure(cfg.name, date, cfg.post.telegram, 4, log_path)
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
                    "JSON object, but prose/markdown fences around it are tolerated.\n"
                    "Language rule: ALL string values (stance / signals / risks / "
                    "any prose) MUST be in Traditional Chinese (繁體中文). Keep "
                    "ticker symbols, English proper nouns, and numeric units verbatim.\n"
                    "Confidence rule: any 'confidence' / 'avg_confidence' field is on "
                    "a 0–10 integer scale (use one decimal at most). If the source "
                    "expresses a percentage (e.g. '60% confidence'), convert to the "
                    "0–10 scale (60% → 6).\n\n"
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

    # Optional Telegram notify (best-effort; never fails the run)
    if cfg.post.telegram:
        try:
            sys.path.insert(0, str(root / "scripts"))
            import notify_telegram  # noqa: E402
            hist_path = output_abs.parent / "_history.jsonl" if cfg.history else None
            notify_telegram.notify(cfg.name, date, output_abs, hist_path, cfg.post.telegram)
        except Exception as e:
            print(f"[telegram] skipped: {e}", file=sys.stderr)

    print(f"[run] ok → {output_abs}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
