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


# ── 多源降級(2026-08-08 新增)────────────────────────────────────────────
# 靜默換源是最糟的失敗形式:讀者會以為看到的是主來源的數字。所以這裡的
# 重點不只是「有沒有換成功」,而是「換了有沒有被記錄下來」。
import compute_zones as _cz                                    # noqa: E402


def _fake_bars(n=5):
    return [_cz.Bar(date=f"2026-08-{i+1:02d}", open=1.0, high=2.0, low=0.5,
                    close=1.5, volume=10.0) for i in range(n)]


def test_primary_source_wins_and_is_not_marked_degraded(monkeypatch):
    monkeypatch.setattr(_cz, "_SOURCE_CHAIN",
                        [("yfinance", lambda t, p: _fake_bars()),
                         ("binance", lambda t, p: [])])
    bars = _cz.fetch_bars("BTC-USD")
    assert len(bars) == 5
    assert _cz.LAST_FETCH_TRACE["source"] == "yfinance"
    assert _cz.LAST_FETCH_TRACE["degraded"] is False


def test_falls_back_to_second_source_and_records_the_failure(monkeypatch):
    def boom(t, p):
        raise RuntimeError("yfinance down")
    monkeypatch.setattr(_cz, "_SOURCE_CHAIN",
                        [("yfinance", boom),
                         ("binance", lambda t, p: _fake_bars(3))])
    bars = _cz.fetch_bars("BTC-USD")
    assert len(bars) == 3
    trace = _cz.LAST_FETCH_TRACE
    assert trace["source"] == "binance"
    assert trace["degraded"] is True
    # 失敗的那一級必須留在紀錄裡,不能只留下成功的那個
    assert trace["attempts"][0]["source"] == "yfinance"
    assert trace["attempts"][0]["ok"] is False
    assert "yfinance down" in trace["attempts"][0]["error"]


def test_empty_result_counts_as_failure_not_success(monkeypatch):
    """回空 list 不是「成功但沒資料」,是這一級失敗,要繼續降級。"""
    monkeypatch.setattr(_cz, "_SOURCE_CHAIN",
                        [("yfinance", lambda t, p: []),
                         ("binance", lambda t, p: _fake_bars(2))])
    assert len(_cz.fetch_bars("BTC-USD")) == 2
    assert _cz.LAST_FETCH_TRACE["source"] == "binance"
    assert _cz.LAST_FETCH_TRACE["attempts"][0]["error"] == "no_bars"


def test_all_sources_failing_returns_empty_with_full_trace(monkeypatch):
    monkeypatch.setattr(_cz, "_SOURCE_CHAIN",
                        [("yfinance", lambda t, p: []),
                         ("binance", lambda t, p: [])])
    assert _cz.fetch_bars("QQQ") == []
    trace = _cz.LAST_FETCH_TRACE
    assert trace["source"] is None and trace["degraded"] is True
    assert len(trace["attempts"]) == 2


def test_binance_returns_empty_for_unmapped_ticker():
    """美股標的走不到 Binance —— 必須乾淨地回空,而不是丟例外或亂抓。"""
    assert _cz._bars_from_binance("QQQ", "12mo") == []
    assert _cz._bars_from_binance("NVDA", "12mo") == []


def test_binance_symbol_map_covers_our_crypto():
    for t in ("BTC-USD", "ETH-USD"):
        assert t in _cz._CRYPTO_BINANCE_SYMBOL


# ── 多透鏡 + 風險不對稱(2026-08-08 新增)──────────────────────────────────
# 多透鏡的用意不是多幾個指標,而是讓**透鏡之間的分歧變成可呈現的訊號**。
# 訊號在 Python 算,不交給 LLM 判斷 —— 同一份資料每次要得到同一個結論。

def _bars_trending(n=250, start=100.0, step=1.0):
    return [_cz.Bar(date=f"2026-01-{i % 28 + 1:02d}", open=start + i * step,
                    high=start + i * step + 1, low=start + i * step - 1,
                    close=start + i * step, volume=1000.0) for i in range(n)]


def test_risk_lens_never_outputs_bullish():
    """移植自 disagreement.py 的 _effective_signal —— 風險只能警告不能看好。"""
    assert _cz._effective_lens_signal("risk", "bullish") == "neutral"
    assert _cz._effective_lens_signal("risk", "bearish") == "bearish"
    assert _cz._effective_lens_signal("risk", "neutral") == "neutral"


def test_non_risk_lens_keeps_bullish():
    assert _cz._effective_lens_signal("structure", "bullish") == "bullish"
    assert _cz._effective_lens_signal("moving_average", "bullish") == "bullish"


def test_risk_lens_in_real_signals_is_never_bullish():
    """即使離失效位很遠,風險透鏡也只能是 neutral。"""
    out = {"trend": {"direction": "up"}, "range": {"position": "discount"},
           "price": 200.0, "buy_zone": {"invalidation_price": 100.0}}
    sigs = _cz.lens_signals(out, {"ma_stack": "bullish", "volume_ratio": 1.0})
    risk = next(l for l in sigs["lenses"] if l["lens"] == "risk")
    assert risk["signal"] == "neutral"


def test_risk_lens_turns_bearish_when_close_to_invalidation():
    out = {"trend": {"direction": "up"}, "range": {"position": "discount"},
           "price": 101.0, "buy_zone": {"invalidation_price": 100.0}}
    sigs = _cz.lens_signals(out, {})
    risk = next(l for l in sigs["lenses"] if l["lens"] == "risk")
    assert risk["signal"] == "bearish"


def test_volume_lens_never_gives_direction():
    """量能只確認參與度,不單獨給方向 —— 否則會變成第二個結構訊號。"""
    for ratio in (0.1, 1.0, 5.0):
        sigs = _cz.lens_signals({"trend": {"direction": "up"}},
                                {"volume_ratio": ratio})
        vol = next(l for l in sigs["lenses"] if l["lens"] == "volume")
        assert vol["signal"] == "neutral", ratio


def test_conflicting_lenses_require_disclosure():
    """結構看多但均線看空 → 必須揭露分歧,這是多透鏡存在的理由。"""
    out = {"trend": {"direction": "up"}, "range": {"position": "premium"}}
    sigs = _cz.lens_signals(out, {"ma_stack": "bearish"})
    assert sigs["conflict_type"] == "conflicting"
    assert sigs["disclosure_required"] is True


def test_aligned_lenses_do_not_require_disclosure():
    out = {"trend": {"direction": "up"}, "range": {"position": "discount"}}
    sigs = _cz.lens_signals(out, {"ma_stack": "bullish"})
    assert sigs["conflict_type"] == "aligned"
    assert sigs["disclosure_required"] is False


def test_single_lens_is_insufficient_not_aligned():
    """只有一個訊號不叫「一致」,叫樣本不足 —— 不可據此講得肯定。"""
    sigs = _cz.lens_signals({"trend": {"direction": "up"}}, {})
    assert sigs["conflict_type"] == "insufficient"


def test_ma_stack_detects_bullish_order():
    m = _cz.lens_metrics(_bars_trending())
    assert m["ma_stack"] == "bullish"          # 單調上升 → MA20>MA50>MA200


def test_ma_stack_detects_bearish_order():
    m = _cz.lens_metrics(_bars_trending(step=-0.3))
    assert m["ma_stack"] == "bearish"


def test_lens_metrics_handles_short_history():
    """不足 200 根時 ma200 為 None,不可以拿 None 去比大小。"""
    m = _cz.lens_metrics(_bars_trending(n=30))
    assert m["ma20"] is not None and m["ma200"] is None
    assert m["ma_stack"] is None


def test_lens_metrics_empty_bars():
    assert _cz.lens_metrics([]) == {}
