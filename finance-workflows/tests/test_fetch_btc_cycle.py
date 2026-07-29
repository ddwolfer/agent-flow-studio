"""Tests for scripts/fetch_btc_cycle.py — crypto-daily 大週期預載資料。

重點覆蓋三件容易出錯又會直接汙染報告的事:
  1. KDJ 的數學(拿已知序列驗證,不是驗「有回傳」)
  2. 算力單位換算(TH/s → EH/s;曾經誤標成 GH/s,差 1000 倍)
  3. 每個 fetcher 的失敗必須被隔離成 {"error": ...},不可拋出
"""
import sys
import pathlib

import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_btc_cycle as fc                                    # noqa: E402


def _raiser(*_a, **_kw):
    raise httpx.ConnectError("boom")


# ── KDJ ──────────────────────────────────────────────────────────────────────
def test_kdj_flat_series_converges_to_50():
    """全平盤:hi == lo → RSV 定義為 50,K/D 收斂到 50、J = 50。"""
    bars = [{"h": 100.0, "l": 100.0, "c": 100.0}] * 50
    out = fc._kdj(bars)
    assert out["k"] == pytest.approx(50.0, abs=0.01)
    assert out["d"] == pytest.approx(50.0, abs=0.01)
    assert out["j"] == pytest.approx(50.0, abs=0.01)


def test_kdj_top_of_range_is_overbought():
    """收在區間最高 → RSV=100,K/D 往上,J 應進超買區(>80)。"""
    bars = [{"h": 100.0, "l": 90.0, "c": 100.0}] * 60
    out = fc._kdj(bars)
    assert out["j"] > 80, out


def test_kdj_bottom_of_range_is_oversold():
    bars = [{"h": 100.0, "l": 90.0, "c": 90.0}] * 60
    out = fc._kdj(bars)
    assert out["j"] < 20, out


def test_kdj_j_equals_3k_minus_2d():
    bars = [{"h": 100.0 + i, "l": 90.0 + i, "c": 95.0 + i} for i in range(40)]
    out = fc._kdj(bars)
    assert out["j"] == pytest.approx(3 * out["k"] - 2 * out["d"], abs=0.02)


# ── 算力單位 ─────────────────────────────────────────────────────────────────
def test_hashrate_converts_th_s_to_eh_s(monkeypatch):
    """blockchain.info 回 TH/s;796,925,286 TH/s = 796.9 EH/s(不是 0.8)。"""
    pts = [{"t": "2026-06-28", "v": 700_000_000.0}] * 31 + \
          [{"t": "2026-07-28", "v": 796_925_286.0}]
    monkeypatch.setattr(fc, "_chart", lambda *a, **k: pts)
    out = fc.fetch_hashrate()
    assert out["latest_eh_s"] == pytest.approx(796.9, abs=0.1)
    assert out["latest_th_s"] == 796_925_286.0


# ── 難度調整 / 投降訊號 ──────────────────────────────────────────────────────
def test_difficulty_detects_adjustments_and_capitulation(monkeypatch):
    pts = [
        {"t": "2026-01-01", "v": 100.0},
        {"t": "2026-01-02", "v": 100.0},      # 無變化 → 不算一次調整
        {"t": "2026-01-15", "v": 110.0},      # +10%
        {"t": "2026-01-29", "v": 99.0},       # -10%  → 投降訊號
        {"t": "2026-02-12", "v": 97.0},       # -2.02% → 非投降
    ]
    monkeypatch.setattr(fc, "_chart", lambda *a, **k: pts)
    out = fc.fetch_difficulty()
    assert [a["pct"] for a in out["recent_adjustments"]] == [10.0, -10.0, -2.02]
    assert [a["date"] for a in out["capitulation_signals_1y"]] == ["2026-01-29"]


# ── 年化換算 ─────────────────────────────────────────────────────────────────
def test_funding_annualizes_over_3_periods_per_day(monkeypatch):
    """0.01%/8h → 0.01 * 3 * 365 = 10.95%/年。"""
    rate = "0.00010000"
    hist = [{"fundingRate": rate, "fundingTime": 1782720000000}] * 500

    def fake_get(url, **kw):
        req = httpx.Request("GET", url)
        if "premiumIndex" in url:
            return httpx.Response(200, request=req, json={
                "markPrice": "64000.0", "lastFundingRate": rate,
                "nextFundingTime": 1782748800000})
        return httpx.Response(200, request=req, json=hist)

    monkeypatch.setattr(fc.httpx, "get", fake_get)
    out = fc.fetch_coinm_funding()
    assert out["current_annualized_pct"] == pytest.approx(10.95, abs=0.01)
    assert out["window_all"]["annualized_pct"] == pytest.approx(10.95, abs=0.01)
    assert out["window_all"]["negative_share_pct"] == 0.0


def test_funding_counts_negative_share(monkeypatch):
    """負費率 = 做多者收錢,佔比要算對(這是情緒偏冷的證據)。"""
    hist = ([{"fundingRate": "-0.00005000", "fundingTime": 1}] * 250 +
            [{"fundingRate": "0.00005000", "fundingTime": 2}] * 250)

    def fake_get(url, **kw):
        req = httpx.Request("GET", url)
        if "premiumIndex" in url:
            return httpx.Response(200, request=req, json={
                "markPrice": "64000.0", "lastFundingRate": "0.00005000",
                "nextFundingTime": 1782748800000})
        return httpx.Response(200, request=req, json=hist)

    monkeypatch.setattr(fc.httpx, "get", fake_get)
    out = fc.fetch_coinm_funding()
    assert out["window_all"]["negative_share_pct"] == pytest.approx(50.0)


# ── 失敗隔離:任一源掛掉都必須回 error dict,不可拋 ──────────────────────────
@pytest.mark.parametrize("fn", [
    fc.fetch_coinm_funding, fc.fetch_ma200, fc.fetch_difficulty, fc.fetch_hashrate,
])
def test_each_fetcher_isolates_failure(monkeypatch, fn):
    monkeypatch.setattr(fc.httpx, "get", _raiser)
    out = fn()
    assert "error" in out, f"{fn.__name__} 應回 error dict 而非拋出"


def test_kdj_isolates_failure_per_interval(monkeypatch):
    """單一週期抓失敗,其他週期不受影響(各自帶 error)。"""
    monkeypatch.setattr(fc.httpx, "get", _raiser)
    out = fc.fetch_kdj()
    for label in ("4h", "1d", "1w"):
        assert "error" in out[label]


def test_collect_all_never_raises(monkeypatch):
    monkeypatch.setattr(fc.httpx, "get", _raiser)
    data = fc.collect_all()
    assert set(data) >= {"coinm_funding", "kdj", "ma200", "difficulty", "hashrate"}
    assert data["generated_at_utc"].endswith("Z")
