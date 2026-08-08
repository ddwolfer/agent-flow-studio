"""Tests for scripts/trading_calendar.py。

兩個最容易寫錯、也最貴的地方各有一整段:
  1. **None ≠ False** —— 「不知道」必須被當成「照跑」。把未知誤當休市,
     等於日曆故障就讓整個報告靜默少一段,那比沒有日曆更糟。
  2. **市場時區** —— 用伺服器本地日期查美股日曆會系統性差一天
     (台北凌晨查,紐約還在前一天)。
"""
import datetime as dt
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import trading_calendar as tc                                # noqa: E402


# ── 加密 24/7 ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("day", ["2026-08-08", "2026-09-07", "2026-12-25"])
def test_crypto_always_open(day):
    assert tc.is_market_open("crypto", dt.date.fromisoformat(day)) is True


def test_crypto_phase_is_always_open():
    assert tc.market_phase("crypto") == tc.MarketPhase.ALWAYS_OPEN


# ── 真實假日:週一到五的近似會判錯的那些 ────────────────────────────────────
def test_us_labor_day_closed_but_tw_open():
    """2026-09-07 週一:美股勞動節休市,台股正常 —— 兩邊近似都會錯。"""
    day = dt.date(2026, 9, 7)
    assert tc.is_market_open("us", day) is False
    assert tc.is_market_open("tw", day) is True


def test_us_thanksgiving_closed_but_tw_open():
    """2026-11-26 週四:感恩節。"""
    day = dt.date(2026, 11, 26)
    assert tc.is_market_open("us", day) is False
    assert tc.is_market_open("tw", day) is True


def test_weekend_closed_both_markets():
    day = dt.date(2026, 8, 8)          # 週六
    assert tc.is_market_open("us", day) is False
    assert tc.is_market_open("tw", day) is False


def test_normal_weekday_open_both():
    day = dt.date(2026, 8, 7)          # 週五
    assert tc.is_market_open("us", day) is True
    assert tc.is_market_open("tw", day) is True


# ── fail-open:日曆不可用時一律回 None(未知),不可回 False ────────────────
def test_unknown_market_returns_none(monkeypatch):
    assert tc.is_market_open("mars") is None


def test_missing_library_returns_none(monkeypatch):
    monkeypatch.setattr(tc, "_XCALS_AVAILABLE", False)
    assert tc.is_market_open("us", dt.date(2026, 9, 7)) is None


def test_missing_library_phase_is_unknown(monkeypatch):
    monkeypatch.setattr(tc, "_XCALS_AVAILABLE", False)
    assert tc.market_phase("us") == tc.MarketPhase.UNKNOWN


def test_calendar_exception_fails_open(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("calendar backend exploded")
    monkeypatch.setattr(tc._xcals, "get_calendar", boom)
    assert tc.is_market_open("us", dt.date(2026, 9, 7)) is None


# ── should_fetch:唯一會回 False 的情況是「明確知道休市」 ──────────────────
def test_should_fetch_false_only_on_known_closure():
    assert tc.should_fetch("QQQ", dt.date(2026, 9, 7)) is False
    assert tc.should_fetch("QQQ", dt.date(2026, 8, 7)) is True


def test_should_fetch_true_for_crypto_on_us_holiday():
    assert tc.should_fetch("BTC-USD", dt.date(2026, 9, 7)) is True


def test_should_fetch_true_for_unknown_symbol():
    """沒登記的標的不該被擋 —— 未知一律照抓。"""
    assert tc.should_fetch("SOMETHING-NEW", dt.date(2026, 9, 7)) is True


def test_should_fetch_true_when_calendar_unavailable(monkeypatch):
    """日曆掛掉時,連 QQQ 都要照抓 —— 這就是 fail-open 的重點。"""
    monkeypatch.setattr(tc, "_XCALS_AVAILABLE", False)
    assert tc.should_fetch("QQQ", dt.date(2026, 9, 7)) is True


def test_symbol_lookup_is_case_insensitive():
    assert tc.market_for_symbol("qqq") == "us"
    assert tc.market_for_symbol("btc-usd") == "crypto"


# ── 市場時區 ────────────────────────────────────────────────────────────────
def test_market_today_uses_market_timezone():
    """台北與紐約的「今天」最多差一天,不該相等於同一個伺服器日期。"""
    us, tw = tc.market_today("us"), tc.market_today("tw")
    assert abs((tw - us).days) <= 1


def test_timezones_are_distinct():
    assert tc.MARKET_TIMEZONE["us"] != tc.MARKET_TIMEZONE["tw"]


# ── 盤別 ────────────────────────────────────────────────────────────────────
def test_phase_closed_on_holiday():
    holiday = dt.datetime(2026, 9, 7, 12, 0, tzinfo=dt.timezone.utc)
    assert tc.market_phase("us", holiday) == tc.MarketPhase.CLOSED


def test_phase_premarket_before_open():
    """2026-08-07 07:00 ET(開盤 09:30 前)。"""
    from zoneinfo import ZoneInfo
    t = dt.datetime(2026, 8, 7, 7, 0, tzinfo=ZoneInfo("America/New_York"))
    assert tc.market_phase("us", t) == tc.MarketPhase.PREMARKET


def test_phase_intraday_during_session():
    from zoneinfo import ZoneInfo
    t = dt.datetime(2026, 8, 7, 11, 0, tzinfo=ZoneInfo("America/New_York"))
    assert tc.market_phase("us", t) == tc.MarketPhase.INTRADAY


def test_phase_postmarket_after_close():
    from zoneinfo import ZoneInfo
    t = dt.datetime(2026, 8, 7, 18, 0, tzinfo=ZoneInfo("America/New_York"))
    assert tc.market_phase("us", t) == tc.MarketPhase.POSTMARKET


# ── describe:日誌用,不可拋 ─────────────────────────────────────────────────
@pytest.mark.parametrize("market", ["us", "tw", "crypto", "mars"])
def test_describe_never_raises(market):
    assert isinstance(tc.describe(market), str)
