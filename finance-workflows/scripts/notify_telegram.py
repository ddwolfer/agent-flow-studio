"""Telegram notification for finance-workflows post-run.

Posts a Markdown summary + PDF attachment to a Telegram supergroup topic after
a workflow finishes. Reusable across workflows: the supergroup chat_id + bot
token are shared (env), the per-workflow message_thread_id (forum topic) comes
from a workflow-specified env var.

Failure is silent (logged to stderr only) — the report has already been written
to disk; Telegram is auxiliary and must never fail the overall run.

Env vars (read at call time, not import):
  TELEGRAM_BOT_TOKEN   — required, the bot's token from @BotFather
  TELEGRAM_CHAT_ID     — required, the supergroup's chat_id (usually negative)
  <topic_env_var>      — optional, holds this workflow's message_thread_id;
                         the name is passed as `topic_env` to notify()
"""
import json, os, pathlib, sys
import httpx

TELEGRAM_API = "https://api.telegram.org"


def _latest_history(history_path: pathlib.Path, date: str):
    """Return the latest history.jsonl entry for `date`, or None.

    Never falls back to another day's entry: when today's summary step failed
    (e.g. the 2026-11-02 usage-limit hit), the old "else latest entry" fallback
    would have pushed YESTERDAY's stance/signals under TODAY's header. No
    summary ("報告已產出,無摘要資料") is honest; a stale one is not."""
    if not history_path.exists():
        return None
    matched = None
    for line in history_path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("date") == date:
            matched = obj
    return matched


# Legacy Telegram Markdown treats _ * ` [ as entity markers. History values are
# LLM prose with tickers like "BTCUSD_PERP": a single unpaired "_" makes Telegram
# reject the whole message (HTTP 400 "can't parse entities"). That silently
# dropped the summary on 2026-10-31 and 2026-11-01 — only the PDF arrived.
_MD_SPECIAL = ("_", "*", "`", "[")   # the four legacy-Markdown escapables


def _md_escape(s: str) -> str:
    for ch in _MD_SPECIAL:
        s = s.replace(ch, "\\" + ch)
    return s


# A _brief.md belongs to the run that wrote the HTML next to it. The file name
# carries no date, so a leftover from an earlier run (salvaged or --post-only
# run whose model never reached the brief step, or a backfill of another date)
# would be pushed as today's body. Same run ⇒ written within minutes.
BRIEF_MAX_SKEW_SEC = 1800


def _brief_for(output_html: pathlib.Path):
    brief = pathlib.Path(output_html).with_name("_brief.md")
    try:
        skew = abs(brief.stat().st_mtime - pathlib.Path(output_html).stat().st_mtime)
    except OSError:
        return None
    if skew > BRIEF_MAX_SKEW_SEC:
        print(f"[telegram] ignoring stale _brief.md ({skew/3600:.1f}h from the HTML)",
              file=sys.stderr)
        return None
    return brief.read_text("utf-8")


def _list_item(x):
    """Render one signal/risk entry (string or dict) as a short bullet."""
    if isinstance(x, str):
        return _md_escape(x[:280])
    if isinstance(x, dict):
        for k in ("signal", "risk", "summary", "description"):
            if k in x and isinstance(x[k], str):
                return _md_escape(x[k][:280])
        return _md_escape(json.dumps(x, ensure_ascii=False)[:280])
    return _md_escape(str(x)[:280])


def _build_message(workflow_name: str, date: str, hist) -> str:
    head = f"📰 *{workflow_name}* — `{date}`"
    if not hist:
        return head + "\n\n(報告已產出,無摘要資料)"
    lines = [head]
    stance = hist.get("overall_stance") or hist.get("overall_market_view")
    conf = hist.get("confidence")
    if conf is None:
        conf = hist.get("avg_confidence")
    if stance:
        s = str(stance)
        lines.append(f"\n📊 *基調*: {_md_escape(s[:400])}" + ("…" if len(s) > 400 else ""))
    if conf is not None:
        lines.append(f"💡 *信心*: {_md_escape(str(conf))}/10")
    sigs = hist.get("top_signals") or []
    if sigs:
        lines.append("\n🔑 *Top signals*")
        for x in sigs[:5]:
            lines.append(f"• {_list_item(x)}")
    risks = hist.get("top_risks") or []
    if risks:
        lines.append("\n⚠️ *Top risks*")
        for x in risks[:3]:
            lines.append(f"• {_list_item(x)}")
    return "\n".join(lines)


def notify(workflow_name: str, date: str, output_html: pathlib.Path,
           history_path, topic_env: str | None) -> None:
    """Best-effort Telegram notify. Returns nothing; silent on any failure."""
    try:
        bot = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
        chat = (os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        if not bot or not chat:
            return  # creds not configured → silently skip
        topic = ""
        if topic_env:
            topic = (os.environ.get(topic_env) or "").strip()
        hist = _latest_history(pathlib.Path(history_path), date) if history_path else None
        # Prefer a workflow-authored _brief.md sibling to the HTML output. When
        # present it IS the Telegram body, bypassing the history-derived summary.
        # Used by serenity-digest (Tier 1/2/3 layout) and any future workflow
        # that wants a custom Markdown shape.
        text = _brief_for(output_html) or _build_message(workflow_name, date, hist)
        base = {"chat_id": chat}
        if topic:
            base["message_thread_id"] = topic
        with httpx.Client(timeout=30.0) as c:
            msg = {**base, "text": text, "disable_web_page_preview": "true"}
            r = c.post(f"{TELEGRAM_API}/bot{bot}/sendMessage",
                       data={**msg, "parse_mode": "Markdown"})
            if r.status_code == 400 and "parse entities" in r.text:
                # Authored _brief.md (or anything the escaper missed): deliver
                # the words as plain text rather than not at all.
                print(f"[telegram] Markdown rejected ({r.text[:120]}); resending plain",
                      file=sys.stderr)
                r = c.post(f"{TELEGRAM_API}/bot{bot}/sendMessage", data=msg)
            if r.status_code != 200:
                print(f"[telegram] sendMessage {r.status_code}: {r.text[:200]}",
                      file=sys.stderr)
            pdf = pathlib.Path(output_html).with_suffix(".pdf")
            if pdf.exists():
                with open(pdf, "rb") as f:
                    r2 = c.post(f"{TELEGRAM_API}/bot{bot}/sendDocument",
                                data=base,
                                files={"document": (pdf.name, f, "application/pdf")})
                    if r2.status_code != 200:
                        print(f"[telegram] sendDocument {r2.status_code}: {r2.text[:200]}",
                              file=sys.stderr)
    except Exception as e:
        print(f"[telegram] notify failed (silent): {e}", file=sys.stderr)
