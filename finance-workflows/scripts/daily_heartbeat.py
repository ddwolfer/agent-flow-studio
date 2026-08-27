"""Daily heartbeat — one launchd job that checks everything ran today.

Supersedes square_watchdog.py (which only watched the Square pipeline).
Runs at 15:00 TPE via launchd (system-level, survives session death and
auth expiry — the exact failure it exists to catch). Checks that today's
expected outputs exist; if anything is missing, sends ONE Telegram alert
listing the gaps + the command to re-run each. All-clear = silent (or a
one-line OK on stdout).

What it checks:
  launchd workflow reports (HTML on disk) — which days each is DUE is read
    straight from that workflow's plist, never hardcoded here (see below)
Why this matters: 2026-07-20 all three `claude -p` launchd jobs failed
silently with "Not logged in" after auth expired — no single place said
"today is incomplete". This is that place.

Why the schedule is parsed from the plists (2026-08-02): this file used to
carry its own copy of each workflow's schedule, and it drifted —
morning-briefing's plist is Mon-Fri, but the table here said "daily", so
the heartbeat cried wolf every Saturday and Sunday. On 2026-07-26 that
false alarm caused a pointless backfill of a report that was never due.
A monitor that lies on weekends trains you to ignore it, so the schedule
now has exactly one source of truth: the plist that launchd itself runs.

The binance-square check was removed on 2026-08-19: the Write-to-Earn
experiment ended (user: 「廣場發文幫我取消 到這邊就夠了」), so "today has no
long post" is now the *intended* state, not a gap. A monitor that reports
the intended state as a failure is the same cry-wolf bug as the weekend
false alarm above.

Usage:
  python daily_heartbeat.py           # normal check + alert
  python daily_heartbeat.py --dry-run  # print verdict, never send TG
"""
import datetime
import os
import pathlib
import plistlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent          # finance-workflows/
REPORTS = ROOT / "reports"
LAUNCHD_DIR = ROOT / "launchd"
ENV = ROOT / ".env"
TELEGRAM_API = "https://api.telegram.org"

# Workflows worth watching. The days each one runs are NOT listed here — they
# are read from launchd/com.financeworkflows.<name>.plist. Adding a workflow
# means adding its name here; changing its schedule means editing only the
# plist, and this file follows automatically.
WATCHED_WORKFLOWS = ["morning-briefing", "crypto-daily", "us-macro"]


def plist_weekdays(name: str, launchd_dir: pathlib.Path | None = None):
    """Which weekdays this workflow is due, as Python weekday ints (0=Mon).

    Returns None for "every day" (a plist with no Weekday keys), or a set of
    0-6. Also returns None when the plist is missing or unreadable — an
    unknown schedule must degrade to "check every day" so a genuinely broken
    job still gets caught; the cost is a possible false alarm, which is the
    safer side to err on than silently never checking.

    launchd's Weekday is 0-7 with BOTH 0 and 7 meaning Sunday; Python's
    weekday() is 0=Mon..6=Sun. That off-by-one-and-wrapped mapping is the
    whole reason this lives in a tested function.
    """
    d = launchd_dir or LAUNCHD_DIR
    path = d / f"com.financeworkflows.{name}.plist"
    if not path.exists():
        return None
    try:
        with open(path, "rb") as f:
            pl = plistlib.load(f)
    except Exception:
        return None

    cal = pl.get("StartCalendarInterval")
    if cal is None:
        return None
    entries = cal if isinstance(cal, list) else [cal]
    days = set()
    for e in entries:
        if "Weekday" not in e:
            return None                   # any unrestricted entry ⇒ every day
        launchd_dow = int(e["Weekday"]) % 7        # 7 → 0 (both are Sunday)
        days.add((launchd_dow - 1) % 7)            # launchd Sun=0 → Python Sun=6
    return days or None


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


# Some workflows have driver shell scripts that do deterministic pre-fetch
# before invoking run-workflow.py. Backfilling with plain run-workflow.py
# skips the pre-fetch and produces reports with silent gaps (§大週期 空的
# is the crypto-daily failure mode — 2026-08-27 fix).
_DRIVER_SCRIPTS = {
    "morning-briefing": "scripts/morning_briefing.sh",
    "crypto-daily":     "scripts/crypto_daily.sh",
}


def _backfill_cmd(name: str) -> str:
    """Prefer the driver shell script when one exists; else fall back to runner."""
    if name in _DRIVER_SCRIPTS:
        return f"bash {_DRIVER_SCRIPTS[name]}"
    return f"mcp/.venv/bin/python run-workflow.py {name}"


def check_launchd_reports(today: str, weekday: int) -> list[str]:
    """Return list of gap descriptions for missing workflow reports."""
    gaps = []
    for name in WATCHED_WORKFLOWS:
        days = plist_weekdays(name)
        if days is not None and weekday not in days:
            continue                      # not scheduled today
        html = REPORTS / name / f"{today}.html"
        if not html.exists():
            gaps.append(
                f"• {name}:今日無報告 → 補跑 "
                f"`cd finance-workflows && {_backfill_cmd(name)}`"
            )
    return gaps


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

    gaps = check_launchd_reports(today, weekday)

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
