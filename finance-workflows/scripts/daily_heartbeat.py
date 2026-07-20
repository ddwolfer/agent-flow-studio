"""Daily heartbeat — one launchd job that checks everything ran today.

Supersedes square_watchdog.py (which only watched the Square pipeline).
Runs at 15:00 TPE via launchd (system-level, survives session death and
auth expiry — the exact failure it exists to catch). Checks that today's
expected outputs exist; if anything is missing, sends ONE Telegram alert
listing the gaps + the command to re-run each. All-clear = silent (or a
one-line OK on stdout).

What it checks (as of 2026-07-20):
  launchd workflow reports (HTML on disk):
    - morning-briefing  (daily)
    - crypto-daily      (daily)
    - us-macro          (weekdays only)
  binance-square publish log:
    - >= 1 long post (variant A/B) expected by 15:00 (10:43 pick +
      14:02 fallback should both have passed)

Why this matters: 2026-07-20 all three `claude -p` launchd jobs failed
silently with "Not logged in" after auth expired — no single place said
"today is incomplete". This is that place.

Usage:
  python daily_heartbeat.py            # normal check + alert
  python daily_heartbeat.py --dry-run  # print verdict, never send TG
"""
import datetime
import json
import os
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent          # finance-workflows/
REPORTS = ROOT / "reports"
ENV = ROOT / ".env"
SQUARE_LOG = REPORTS / "binance-square" / "_published.jsonl"
TELEGRAM_API = "https://api.telegram.org"

# workflow -> runs on which weekdays (0=Mon..6=Sun); None = every day
LAUNCHD_WORKFLOWS = {
    "morning-briefing": None,
    "crypto-daily": None,
    "us-macro": {0, 1, 2, 3, 4},          # Mon-Fri
}


def _load_env(path: pathlib.Path) -> dict:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def check_launchd_reports(today: str, weekday: int) -> list[str]:
    """Return list of gap descriptions for missing workflow reports."""
    gaps = []
    for name, days in LAUNCHD_WORKFLOWS.items():
        if days is not None and weekday not in days:
            continue                      # not scheduled today
        html = REPORTS / name / f"{today}.html"
        if not html.exists():
            gaps.append(
                f"• {name}:今日無報告 → 補跑 "
                f"`cd finance-workflows && mcp/.venv/bin/python run-workflow.py {name}`"
            )
    return gaps


def check_square(today: str) -> list[str]:
    """Return gap if today has no long post (A/B) in the publish log."""
    if not SQUARE_LOG.exists():
        return ["• binance-square:發文日誌不存在"]
    longs = 0
    for line in SQUARE_LOG.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            p = json.loads(line)
        except Exception:
            continue
        if p.get("date") == today and p.get("variant") in ("A", "B"):
            longs += 1
    if longs == 0:
        return ["• binance-square:今日無長文 → 到 Claude 對話選文或說「重掛廣場 cron」"]
    return []


def send_alert(env: dict, text: str) -> bool:
    bot = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = env.get("TELEGRAM_CHAT_ID", "").strip()
    # heartbeat alerts go to the morning topic (ops), fall back to no-topic
    topic = env.get("TELEGRAM_TOPIC_MORNING", "").strip()
    if not (bot and chat):
        print("[heartbeat] telegram creds incomplete — cannot alert",
              file=sys.stderr)
        return False
    data = {"chat_id": chat, "text": text, "disable_web_page_preview": "true"}
    if topic:
        data["message_thread_id"] = topic
    try:
        r = httpx.post(f"{TELEGRAM_API}/bot{bot}/sendMessage", data=data,
                       timeout=15.0)
        return r.status_code == 200
    except Exception as e:
        print(f"[heartbeat] alert send failed: {e}", file=sys.stderr)
        return False


def main(argv=None) -> int:
    dry = "--dry-run" in (argv or sys.argv[1:])
    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    weekday = now.weekday()

    gaps = check_launchd_reports(today, weekday) + check_square(today)

    if not gaps:
        print(f"[heartbeat] OK — all expected outputs present ({today})")
        return 0

    header = f"🩺 每日巡檢 · {today} 15:00 · 發現 {len(gaps)} 個缺口:\n\n"
    body = header + "\n".join(gaps)
    body += ("\n\n最常見原因:Claude auth 過期(需 /login)導致 claude -p 排程"
             "集體失敗。/login 後用上面指令補跑。")

    if dry:
        print(f"[heartbeat] DRY RUN — would alert:\n{body}")
        return 1
    ok = send_alert(_load_env(ENV), body)
    print(f"[heartbeat] {len(gaps)} gap(s) — alert {'sent' if ok else 'FAILED'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
