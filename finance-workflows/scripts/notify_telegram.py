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
    """Return the latest history.jsonl entry, preferring one matching `date`."""
    if not history_path.exists():
        return None
    matched = None
    last_any = None
    for line in history_path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        last_any = obj
        if obj.get("date") == date:
            matched = obj
    return matched or last_any


def _list_item(x):
    """Render one signal/risk entry (string or dict) as a short bullet."""
    if isinstance(x, str):
        return x[:280]
    if isinstance(x, dict):
        for k in ("signal", "risk", "summary", "description"):
            if k in x and isinstance(x[k], str):
                return x[k][:280]
        return json.dumps(x, ensure_ascii=False)[:280]
    return str(x)[:280]


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
        lines.append(f"\n📊 *基調*: {s[:400]}" + ("…" if len(s) > 400 else ""))
    if conf is not None:
        lines.append(f"💡 *信心*: {conf}/10")
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
        text = _build_message(workflow_name, date, hist)
        base = {"chat_id": chat}
        if topic:
            base["message_thread_id"] = topic
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{TELEGRAM_API}/bot{bot}/sendMessage",
                       data={**base, "text": text, "parse_mode": "Markdown",
                             "disable_web_page_preview": "true"})
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
