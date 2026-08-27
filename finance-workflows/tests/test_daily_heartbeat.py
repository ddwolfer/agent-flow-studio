"""Tests for scripts/daily_heartbeat.py — the 15:00 launchd 巡檢.

The bug these exist to prevent (2026-08-02): the heartbeat used to carry its
own hardcoded copy of each workflow's schedule. morning-briefing's plist is
Mon-Fri but the table said "daily", so the monitor false-alarmed every
weekend — and on 2026-07-26 that triggered a pointless backfill of a report
that was never due. A monitor that lies trains you to ignore it.

Most of the surface here is the launchd→Python weekday conversion, which is
off-by-one AND wrapped (launchd: 0 or 7 = Sunday, 1 = Monday; Python:
0 = Monday, 6 = Sunday), so it gets exhaustive coverage.
"""
import pathlib
import plistlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import daily_heartbeat as hb                                    # noqa: E402


def _write_plist(d: pathlib.Path, name: str, cal):
    """Write com.financeworkflows.<name>.plist with the given StartCalendarInterval."""
    body = {"Label": f"com.financeworkflows.{name}"}
    if cal is not None:
        body["StartCalendarInterval"] = cal
    p = d / f"com.financeworkflows.{name}.plist"
    with open(p, "wb") as f:
        plistlib.dump(body, f)
    return p


# ── launchd → Python weekday conversion ──────────────────────────────────────
@pytest.mark.parametrize("launchd_dow,py_weekday", [
    (1, 0),   # Monday
    (2, 1),
    (3, 2),
    (4, 3),
    (5, 4),
    (6, 5),   # Saturday
    (0, 6),   # Sunday — launchd spells it 0 …
    (7, 6),   # … and also 7. Both must land on Python's 6.
])
def test_weekday_conversion(tmp_path, launchd_dow, py_weekday):
    _write_plist(tmp_path, "wf", [{"Weekday": launchd_dow, "Hour": 7}])
    assert hb.plist_weekdays("wf", tmp_path) == {py_weekday}


def test_monday_to_friday_plist(tmp_path):
    """The real morning-briefing shape: five Weekday entries, 1-5."""
    _write_plist(tmp_path, "wf",
                 [{"Weekday": d, "Hour": 7, "Minute": 0} for d in range(1, 6)])
    assert hb.plist_weekdays("wf", tmp_path) == {0, 1, 2, 3, 4}


# ── "every day" cases must return None, not an empty set ─────────────────────
def test_no_weekday_key_means_every_day(tmp_path):
    """crypto-daily's shape: a bare Hour/Minute dict — due every day."""
    _write_plist(tmp_path, "wf", {"Hour": 7, "Minute": 30})
    assert hb.plist_weekdays("wf", tmp_path) is None


def test_mixed_entries_degrade_to_every_day(tmp_path):
    """If ANY entry is unrestricted, the job can fire any day."""
    _write_plist(tmp_path, "wf", [{"Weekday": 1, "Hour": 7}, {"Hour": 20}])
    assert hb.plist_weekdays("wf", tmp_path) is None


def test_start_interval_only_means_every_day(tmp_path):
    _write_plist(tmp_path, "wf", None)
    assert hb.plist_weekdays("wf", tmp_path) is None


# ── unknown schedule must fail SAFE (check every day), never skip silently ───
def test_missing_plist_returns_none(tmp_path):
    assert hb.plist_weekdays("does-not-exist", tmp_path) is None


def test_corrupt_plist_returns_none(tmp_path):
    (tmp_path / "com.financeworkflows.wf.plist").write_text("not a plist")
    assert hb.plist_weekdays("wf", tmp_path) is None


# ── the actual repo plists — the regression that started this ───────────────
def test_real_morning_briefing_is_weekdays_only():
    """The 2026-08-02 false alarm: this must NOT be 'every day'."""
    assert hb.plist_weekdays("morning-briefing") == {0, 1, 2, 3, 4}


def test_real_crypto_daily_is_every_day():
    assert hb.plist_weekdays("crypto-daily") is None


def test_real_us_macro_is_weekdays_only():
    assert hb.plist_weekdays("us-macro") == {0, 1, 2, 3, 4}


# ── gap detection honours the parsed schedule ────────────────────────────────
def test_weekend_does_not_flag_weekday_only_workflow(monkeypatch, tmp_path):
    """Sunday (weekday=6): a Mon-Fri workflow with no report is NOT a gap."""
    monkeypatch.setattr(hb, "WATCHED_WORKFLOWS", ["wf"])
    monkeypatch.setattr(hb, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(hb, "plist_weekdays", lambda n, d=None: {0, 1, 2, 3, 4})
    assert hb.check_launchd_reports("2026-08-02", 6) == []


def test_weekday_flags_missing_report(monkeypatch, tmp_path):
    monkeypatch.setattr(hb, "WATCHED_WORKFLOWS", ["wf"])
    monkeypatch.setattr(hb, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(hb, "plist_weekdays", lambda n, d=None: {0, 1, 2, 3, 4})
    gaps = hb.check_launchd_reports("2026-07-29", 2)     # Wednesday
    assert len(gaps) == 1 and "wf" in gaps[0]


def test_present_report_is_not_a_gap(monkeypatch, tmp_path):
    reports = tmp_path / "reports" / "wf"
    reports.mkdir(parents=True)
    (reports / "2026-07-29.html").write_text("<html></html>")
    monkeypatch.setattr(hb, "WATCHED_WORKFLOWS", ["wf"])
    monkeypatch.setattr(hb, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(hb, "plist_weekdays", lambda n, d=None: None)
    assert hb.check_launchd_reports("2026-07-29", 2) == []

# 廣場發文巡檢的兩個測試已於 2026-08-19 隨 check_square() 一併移除
# (Write-to-Earn 實驗結束,「今日無長文」不再是缺口)。


# ── backfill command uses driver script when one exists ─────────────────────
# Motivation: 2026-08-27 — user ran the plain runner to backfill crypto-daily
# after a 32h Chrome hang, and the report came out with 大週期 空的 because
# it skipped fetch_btc_cycle.py. The heartbeat's suggested command must not
# lead the user (or future-me) into this trap.

def test_backfill_uses_driver_script_when_available():
    assert hb._backfill_cmd("crypto-daily") == "bash scripts/crypto_daily.sh"
    assert hb._backfill_cmd("morning-briefing") == "bash scripts/morning_briefing.sh"


def test_backfill_falls_back_to_runner_for_workflows_without_driver():
    # us-macro has no driver script — pre-fetch isn't needed for that workflow.
    assert hb._backfill_cmd("us-macro") == "mcp/.venv/bin/python run-workflow.py us-macro"


def test_gap_message_embeds_driver_command(monkeypatch, tmp_path):
    reports = tmp_path / "reports"
    (reports / "crypto-daily").mkdir(parents=True)
    monkeypatch.setattr(hb, "REPORTS", reports)
    monkeypatch.setattr(hb, "WATCHED_WORKFLOWS", ["crypto-daily"])
    monkeypatch.setattr(hb, "plist_weekdays", lambda n, d=None: None)
    gaps = hb.check_launchd_reports("2026-08-27", 2)
    assert len(gaps) == 1
    assert "bash scripts/crypto_daily.sh" in gaps[0]
    assert "run-workflow.py crypto-daily" not in gaps[0]  # ensure old form gone
