"""Watchdog for the binance-square posting pipeline.

The pipeline runs on in-session Claude crons which die silently (session
restart, reboot, 7-day expiry). This script is the independent heartbeat:
scheduled via launchd (system-level, survives everything the session
doesn't), it checks whether today has at least one entry in the publish
log. If not, it alerts the Telegram topic so the user can re-arm the
session crons with one sentence.

Design notes:
- Deterministic Python, zero LLM. Never raises out (launchd job must not
  flap); all failures degrade to an alert or a stderr line.
- Runs at 14:30 TPE — by 14:02 the long-post fallback must have fired,
  so an empty log at 14:30 means the 10:43 cron did not run.
- Local date (TPE) is used to match the publish log's date field.

Usage:
  python square_watchdog.py            # normal check
  python square_watchdog.py --dry-run  # print verdict, never send TG
"""
import datetime
import json
import os
import pathlib
import sys

import httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent   # finance-workflows/
LOG = ROOT / "reports" / "binance-square" / "_published.jsonl"
ENV = ROOT / ".env"

TELEGRAM_API = "https://api.telegram.org"


def _load_env(path: pathlib.Path) -> dict:
    """Minimal .env loader (export-prefix / quote tolerant, no deps)."""
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


def posts_today(log_path: pathlib.Path, today: str) -> int:
    """Count publish-log entries dated `today`. Malformed lines ignored."""
    if not log_path.exists():
        return 0
    n = 0
    for line in log_path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            if json.loads(line).get("date") == today:
                n += 1
        except Exception:
            continue
    return n


def send_alert(env: dict, text: str) -> bool:
    bot = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = env.get("TELEGRAM_CHAT_ID", "").strip()
    topic = env.get("TELEGRAM_TOPIC_BINANCE_SQUARE", "").strip()
    if not (bot and chat and topic):        # fail-closed: no partial sends
        print("[watchdog] telegram env incomplete — cannot alert",
              file=sys.stderr)
        return False
    try:
        r = httpx.post(f"{TELEGRAM_API}/bot{bot}/sendMessage",
                       data={"chat_id": chat, "message_thread_id": topic,
                             "text": text, "disable_web_page_preview": "true"},
                       timeout=15.0)
        return r.status_code == 200
    except Exception as e:
        print(f"[watchdog] alert send failed: {e}", file=sys.stderr)
        return False


def main(argv=None) -> int:
    dry = "--dry-run" in (argv or sys.argv[1:])
    today = datetime.date.today().strftime("%Y-%m-%d")
    n = posts_today(LOG, today)
    if n > 0:
        print(f"[watchdog] OK — {n} post(s) today ({today})")
        return 0
    msg = (f"🚨 廣場 watchdog:今天({today})到 14:30 還沒有任何發文紀錄。\n\n"
           "in-session cron 很可能已失效(session 重啟 / 7 天過期)。\n"
           "修復:到 Claude 對話說「重掛廣場 cron」即可(重掛指令在 spec "
           "2026-07-15-binance-square-daily-design.md)。")
    if dry:
        print(f"[watchdog] DRY RUN — would alert:\n{msg}")
        return 1
    ok = send_alert(_load_env(ENV), msg)
    print(f"[watchdog] no posts today — alert {'sent' if ok else 'FAILED'}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
