"""Inventory of everything automated on this machine (finance stack).

Aggregates three sources into one table:
  1. launchd jobs (com.financeworkflows.* / com.arbsentinel.*) — schedule
     parsed from the repo's plist files, live status from `launchctl list`
  2. pmset scheduled wakes (so the laptop is awake for the morning jobs)
  3. in-session Claude crons — NOT inspectable from outside the session;
     listed from the manifest below (keep in sync with the spec)

Usage:
  python automation_inventory.py
"""
import pathlib
import plistlib
import re
import subprocess

REPO = pathlib.Path(__file__).resolve().parent.parent.parent   # repo root
PLIST_DIRS = [
    REPO / "finance-workflows" / "launchd",
    REPO / "arb-sentinel" / "launchd",
]

# Manifest of in-session Claude crons (session-only, invisible to launchd).
# Keep in sync with docs/superpowers/specs/2026-07-15-binance-square-daily-design.md
IN_SESSION_CRONS = [
    ("10:43 每日", "binance-square 日更:產 A/B 兩篇 → user 選 → API 發文"),
    ("15:58 每日", "binance-square 短文檢查點 1(事件才發)"),
    ("21:04 每日", "binance-square 短文保底(事件優先,無事件發生活文)"),
    ("14:02 動態", "當日 fallback:未選文自動發推薦篇(日更流程動態建立)"),
]


def _fmt_calendar(cal) -> str:
    """Render StartCalendarInterval dict(s) as human-readable schedule."""
    if isinstance(cal, list):
        return " / ".join(_fmt_calendar(c) for c in cal)
    dow = {0: "日", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六"}
    parts = []
    if "Weekday" in cal:
        parts.append(f"週{dow.get(cal['Weekday'], cal['Weekday'])}")
    if "Month" in cal and "Day" in cal:
        parts.append(f"{cal['Month']}/{cal['Day']}")
    h, m = cal.get("Hour"), cal.get("Minute", 0)
    if h is not None:
        parts.append(f"{h:02d}:{m:02d}")
    return " ".join(parts) or str(dict(cal))


def load_plists() -> list[dict]:
    jobs = []
    for d in PLIST_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("*.plist*")):
            disabled = p.suffix == ".disabled" or p.name.endswith(".plist.disabled")
            try:
                with open(p, "rb") as f:
                    pl = plistlib.load(f)
            except Exception:
                continue
            label = pl.get("Label", p.stem)
            if "StartCalendarInterval" in pl:
                sched = _fmt_calendar(pl["StartCalendarInterval"])
            elif "StartInterval" in pl:
                sec = pl["StartInterval"]
                sched = f"每 {sec//60} 分鐘" if sec >= 60 else f"每 {sec} 秒"
            else:
                sched = "(無排程鍵)"
            prog = " ".join(pl.get("ProgramArguments", []))
            # shorten program for display
            prog_short = re.sub(r"/Users/\S+/(finance-workflows|arb-sentinel)/", r"\1/", prog)
            jobs.append({"label": label, "sched": sched, "prog": prog_short,
                         "disabled": disabled})
    return jobs


def live_status() -> dict:
    """label → (pid, last_exit_code) from launchctl list."""
    out = {}
    try:
        txt = subprocess.run(["launchctl", "list"], capture_output=True,
                             text=True, timeout=10).stdout
    except Exception:
        return out
    for line in txt.splitlines()[1:]:
        cols = line.split("\t")
        if len(cols) >= 3:
            pid, code, label = cols[0], cols[1], cols[2]
            out[label] = (pid, code)
    return out


def pmset_wakes() -> list[str]:
    try:
        txt = subprocess.run(["pmset", "-g", "sched"], capture_output=True,
                             text=True, timeout=10).stdout
        return [l.strip() for l in txt.splitlines() if l.strip()]
    except Exception:
        return ["(pmset 讀取失敗)"]


def main() -> int:
    status = live_status()
    jobs = load_plists()

    print("=" * 78)
    print("這台機器的自動化總覽")
    print("=" * 78)

    print("\n【1. launchd(系統層,重開機自動復活)】\n")
    print(f"{'狀態':<6}{'排程':<16}{'Label':<46}")
    print("-" * 78)
    for j in sorted(jobs, key=lambda x: (x["disabled"], x["sched"])):
        if j["disabled"]:
            st = "⏸ 停用"
        elif j["label"] in status:
            pid, code = status[j["label"]]
            st = "✅ 掛載" if code == "0" or pid != "-" else f"⚠️ exit {code}"
        else:
            st = "❌ 未掛載"
        print(f"{st:<7}{j['sched']:<16}{j['label']}")
        print(f"{'':6}└ {j['prog'][:70]}")
    # jobs loaded in launchctl but plist not in repo
    repo_labels = {j["label"] for j in jobs}
    strays = [l for l in status
              if l.startswith(("com.financeworkflows", "com.arbsentinel"))
              and l not in repo_labels]
    for s in strays:
        print(f"{'⚠️ 掛載但 repo 無 plist':<20}{s}")

    print("\n【2. in-session Claude cron(session-only,session 死即滅,7 天過期)】\n")
    for sched, desc in IN_SESSION_CRONS:
        print(f"  🔄 {sched:<12}{desc}")
    print("  ⚠️ 這區塊來自 manifest,無法從外部驗證 — 實際存活以 watchdog 為準")

    print("\n【3. pmset 排程喚醒】\n")
    for l in pmset_wakes():
        print(f"  {l}")

    print("\n【4. 心跳保護】\n")
    print("  🩺 daily-heartbeat(launchd 15:00)每日巡檢:")
    print("     檢查 launchd 報告(mb/crypto/us-macro)+ 廣場長文是否齊全,缺則 TG 列清單")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
