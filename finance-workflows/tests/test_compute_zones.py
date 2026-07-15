"""Tests for scripts/compute_zones.py — focused on the NaN-bar guard.

The full algorithm is validated by real-data 9-ticker runs; this file locks
in the specific regression that broke a pre-market run: yfinance emits an
unsettled bar with NaN OHLC for the current session, which collapsed
`price` to 0.0 and poisoned the zone math.
"""
import sys, pathlib
import math
import pandas as pd
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import compute_zones as cz                                       # noqa: E402


class _FakeTicker:
    def __init__(self, df):
        self._df = df

    def history(self, **kw):
        return self._df


def _mk_df(rows):
    """rows: list of (date_str, o, h, l, c, v)."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {
            "Open": [r[1] for r in rows],
            "High": [r[2] for r in rows],
            "Low": [r[3] for r in rows],
            "Close": [r[4] for r in rows],
            "Volume": [r[5] for r in rows],
        },
        index=idx,
    )


def test_fetch_bars_skips_trailing_nan_bar(monkeypatch):
    """The unsettled pre-market bar (NaN OHLC) must be dropped so the last
    real bar's close becomes `price`, not 0.0."""
    df = _mk_df([
        ("2026-07-13", 400.0, 405.0, 398.0, 404.0, 1000),
        ("2026-07-14", 404.0, 406.0, 394.0, 394.76, 2000),
        ("2026-07-15", float("nan"), float("nan"), float("nan"), float("nan"), 3000),
    ])
    monkeypatch.setattr(cz.yf, "Ticker", lambda t: _FakeTicker(df))
    bars = cz.fetch_bars("TSLA")
    assert len(bars) == 2                      # NaN bar dropped
    assert bars[-1].date == "2026-07-14"
    assert bars[-1].close == 394.76            # real close, not 0.0
    assert all(math.isfinite(b.close) for b in bars)


def test_fetch_bars_skips_interior_nan_bar(monkeypatch):
    """A NaN bar anywhere (e.g. a data-vendor hiccup) is skipped, not just
    the trailing one."""
    df = _mk_df([
        ("2026-07-10", 400.0, 405.0, 398.0, 404.0, 1000),
        ("2026-07-13", float("nan"), float("nan"), float("nan"), float("nan"), 0),
        ("2026-07-14", 404.0, 406.0, 394.0, 394.76, 2000),
    ])
    monkeypatch.setattr(cz.yf, "Ticker", lambda t: _FakeTicker(df))
    bars = cz.fetch_bars("TSLA")
    assert len(bars) == 2
    assert [b.date for b in bars] == ["2026-07-10", "2026-07-14"]


def test_fetch_bars_empty_df_returns_empty(monkeypatch):
    monkeypatch.setattr(cz.yf, "Ticker", lambda t: _FakeTicker(pd.DataFrame()))
    assert cz.fetch_bars("TSLA") == []


def test_build_output_price_never_zero_with_nan_tail(monkeypatch):
    """End-to-end: a 60+ bar series with a trailing NaN bar still yields a
    positive price (the NaN bar never reaches build_output)."""
    rows = []
    base = 100.0
    for i in range(65):
        # simple ascending series, deterministic
        px = base + i
        rows.append((f"2026-0{4 + i // 30}-{(i % 28) + 1:02d}",
                     px, px + 1, px - 1, px + 0.5, 1000))
    rows.append(("2026-07-15", float("nan"), float("nan"),
                 float("nan"), float("nan"), 3000))
    df = _mk_df(rows)
    monkeypatch.setattr(cz.yf, "Ticker", lambda t: _FakeTicker(df))
    bars = cz.fetch_bars("TEST")
    out = cz.build_output("TEST", bars)
    assert out["price"] > 0
    assert out["mode"] == "full"
    assert "buy_zone_above_price_anomaly" not in out.get("warnings", [])
