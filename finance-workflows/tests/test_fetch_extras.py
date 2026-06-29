"""Tests for scripts/fetch_extras.py — morning-briefing supporting data feeds."""
import json, sys, pathlib
import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import fetch_extras as fx                                       # noqa: E402


def _resp(json_body=None, text_body=None, status=200, headers=None):
    """Build a closure that fakes httpx.Client.get."""
    def fake_get(self, url, **kw):
        if json_body is not None:
            return httpx.Response(status, json=json_body, headers=headers or {},
                                  request=httpx.Request("GET", url))
        return httpx.Response(status, text=text_body or "", headers=headers or {},
                              request=httpx.Request("GET", url))
    return fake_get


# ── Binance fapi funding ──────────────────────────────────────────────────────
def test_fetch_binance_funding_returns_latest_and_24h_avg(monkeypatch):
    # /fapi/v1/fundingRate?symbol=BTCUSDT&limit=3 → 3 funding entries
    body = [
        {"symbol": "BTCUSDT", "fundingTime": 1782720000000, "fundingRate": "0.00005000"},
        {"symbol": "BTCUSDT", "fundingTime": 1782748800000, "fundingRate": "0.00008000"},
        {"symbol": "BTCUSDT", "fundingTime": 1782777600000, "fundingRate": "0.00011000"},
    ]
    monkeypatch.setattr(httpx.Client, "get", _resp(json_body=body))
    out = fx.fetch_binance_funding("BTCUSDT")
    assert out["latest_rate_8h"] == 0.00011
    # 3-sample average of (0.00005, 0.00008, 0.00011) = 0.00008
    assert abs(out["avg_24h_rate_8h"] - 0.00008) < 1e-9
    # Annualised = rate * 3 (per day) * 365
    assert abs(out["latest_annualised"] - 0.00011 * 3 * 365) < 1e-9


def test_fetch_binance_funding_never_raises_on_http_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    out = fx.fetch_binance_funding("BTCUSDT")
    assert out == {"error": "ConnectError: down"} or "error" in out


# ── Binance fapi open interest ────────────────────────────────────────────────
def test_fetch_binance_oi_returns_quantity(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get",
                        _resp(json_body={"symbol": "BTCUSDT",
                                         "openInterest": "101526.453",
                                         "time": 1782749986317}))
    out = fx.fetch_binance_oi("BTCUSDT")
    assert out["open_interest_btc"] == 101526.453


# ── CBOE VIX CSV ──────────────────────────────────────────────────────────────
_CBOE_VIX_CSV = """DATE,OPEN,HIGH,LOW,CLOSE
06/25/2026,14.5,15.2,14.0,14.8
06/26/2026,14.8,15.6,14.5,15.1
06/27/2026,15.1,15.3,14.9,14.95
"""


def test_fetch_cboe_vix_returns_latest_close(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", _resp(text_body=_CBOE_VIX_CSV))
    out = fx.fetch_cboe_vix("VIX")
    assert out["latest_date"] == "06/27/2026"
    assert out["latest_close"] == 14.95
    assert out["prev_close"] == 15.1
    assert abs(out["dod_change"] - (14.95 - 15.1)) < 1e-9


def test_fetch_cboe_vix_handles_malformed_csv(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", _resp(text_body="not a csv"))
    out = fx.fetch_cboe_vix("VIX")
    assert "error" in out


# ── Treasury fiscaldata upcoming auctions ─────────────────────────────────────
def test_fetch_treasury_auctions_returns_top_n(monkeypatch):
    body = {"data": [
        {"auction_date": "2026-07-07", "security_type": "Bill",
         "security_term": "52-Week", "offering_amt": "null"},
        {"auction_date": "2026-07-08", "security_type": "Note",
         "security_term": "9-Year 10-Month", "offering_amt": "null"},
        {"auction_date": "2026-07-09", "security_type": "Bond",
         "security_term": "29-Year 10-Month", "offering_amt": "null"},
    ]}
    monkeypatch.setattr(httpx.Client, "get", _resp(json_body=body))
    out = fx.fetch_treasury_auctions(limit=2)
    assert len(out["auctions"]) == 2
    assert out["auctions"][0]["auction_date"] == "2026-07-07"
    assert out["auctions"][1]["security_term"] == "9-Year 10-Month"


# ── DefiLlama stablecoins ─────────────────────────────────────────────────────
def test_fetch_stablecoin_supply_returns_top_two(monkeypatch):
    body = {"peggedAssets": [
        {"name": "Tether", "symbol": "USDT", "pegType": "peggedUSD",
         "circulating": {"peggedUSD": 110_000_000_000},
         "circulatingPrevDay": {"peggedUSD": 109_500_000_000}},
        {"name": "USD Coin", "symbol": "USDC", "pegType": "peggedUSD",
         "circulating": {"peggedUSD": 60_000_000_000},
         "circulatingPrevDay": {"peggedUSD": 59_800_000_000}},
        {"name": "DAI", "symbol": "DAI", "pegType": "peggedUSD",
         "circulating": {"peggedUSD": 5_000_000_000},
         "circulatingPrevDay": {"peggedUSD": 5_000_000_000}},
    ]}
    monkeypatch.setattr(httpx.Client, "get", _resp(json_body=body))
    out = fx.fetch_stablecoin_supply()
    usdt = next(s for s in out["stablecoins"] if s["symbol"] == "USDT")
    assert usdt["circulating_usd"] == 110_000_000_000
    assert usdt["delta_24h_usd"] == 500_000_000
    # USDT + USDC totals reported separately for the prompt
    assert out["usdt_usdc_combined_delta_24h"] == 500_000_000 + 200_000_000


# ── main() smoke ──────────────────────────────────────────────────────────────
def test_main_writes_combined_json(tmp_path, monkeypatch):
    # Patch each fetcher to return a tiny structured stub.
    monkeypatch.setattr(fx, "fetch_binance_funding",
                        lambda symbol: {"_symbol": symbol, "latest_rate_8h": 0.0001})
    monkeypatch.setattr(fx, "fetch_binance_oi",
                        lambda symbol: {"_symbol": symbol, "open_interest_btc": 100.0})
    monkeypatch.setattr(fx, "fetch_cboe_vix",
                        lambda code: {"_code": code, "latest_close": 14.5})
    monkeypatch.setattr(fx, "fetch_treasury_auctions",
                        lambda limit=10: {"auctions": []})
    monkeypatch.setattr(fx, "fetch_stablecoin_supply",
                        lambda: {"stablecoins": [], "usdt_usdc_combined_delta_24h": 0})
    out = tmp_path / "extras.json"
    rc = fx.main(["--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text("utf-8"))
    # Top-level keys land in a documented shape
    assert set(data.keys()) >= {"generated_at_utc", "binance_funding", "binance_oi",
                                 "cboe_vix", "treasury_auctions", "stablecoins"}
    assert data["binance_funding"]["BTC"]["_symbol"] == "BTCUSDT"
    assert data["cboe_vix"]["VIX"]["_code"] == "VIX"


def test_main_continues_when_individual_source_fails(tmp_path, monkeypatch):
    # One bad source must NOT take down the whole script.
    monkeypatch.setattr(fx, "fetch_binance_funding",
                        lambda symbol: {"error": "ConnectError: down"})
    monkeypatch.setattr(fx, "fetch_binance_oi",
                        lambda symbol: {"open_interest_btc": 100.0})
    monkeypatch.setattr(fx, "fetch_cboe_vix",
                        lambda code: {"latest_close": 14.5})
    monkeypatch.setattr(fx, "fetch_treasury_auctions",
                        lambda limit=10: {"auctions": []})
    monkeypatch.setattr(fx, "fetch_stablecoin_supply",
                        lambda: {"stablecoins": [], "usdt_usdc_combined_delta_24h": 0})
    out = tmp_path / "extras.json"
    rc = fx.main(["--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text("utf-8"))
    assert "error" in data["binance_funding"]["BTC"]
    # OI for BTC still surfaces
    assert data["binance_oi"]["BTC"]["open_interest_btc"] == 100.0
