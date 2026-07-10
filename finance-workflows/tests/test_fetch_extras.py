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
    monkeypatch.setattr(fx, "fetch_twse_three_investors",
                        lambda: {"error": "test-stub"})
    out = tmp_path / "extras.json"
    rc = fx.main(["--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text("utf-8"))
    assert "error" in data["binance_funding"]["BTC"]
    # OI for BTC still surfaces
    assert data["binance_oi"]["BTC"]["open_interest_btc"] == 100.0


# ── TWSE 三大法人買賣金額 ─────────────────────────────────────────────────────
_TWSE_OK_RESPONSE = {
    "stat": "OK",
    "date": "20260709",
    "title": "115年07月09日 三大法人買賣金額統計表",
    "fields": ["單位名稱", "買進金額", "賣出金額", "買賣差額"],
    "data": [
        ["自營商(自行買賣)", "9,494,954,521", "11,531,142,442", "-2,036,187,921"],
        ["自營商(避險)",      "27,743,223,050", "33,378,200,940", "-5,634,977,890"],
        ["投信",              "30,231,840,066", "10,331,239,403", "19,900,600,663"],
        ["外資及陸資(不含外資自營商)", "367,858,937,128", "415,111,753,557", "-47,252,816,429"],
        ["外資自營商",         "0", "0", "0"],
        ["合計",              "435,328,954,765", "470,352,336,342", "-35,023,381,577"],
    ],
}
_TWSE_EMPTY = {"stat": "很抱歉，沒有符合條件的資料!"}


def test_fetch_twse_three_investors_parses_all_categories(monkeypatch):
    import datetime as dt
    monkeypatch.setattr(httpx.Client, "get", _resp(json_body=_TWSE_OK_RESPONSE))
    # Force today so probe date is deterministic (weekday: Thu 2026-07-09;
    # today - 1 = Wed 2026-07-08, which is a weekday → first probe succeeds)
    out = fx.fetch_twse_three_investors(today=dt.date(2026, 7, 9))
    assert out["unit"] == "TWD 億"
    assert out["as_of_date"] == "20260708"                  # today - 1
    assert out["foreign_net_billion_twd"] == round(-47252816429 / 1e8, 2)
    assert out["invtrust_net_billion_twd"] == round(19900600663 / 1e8, 2)
    assert out["prop_dealer_self_net_billion_twd"] == round(-2036187921 / 1e8, 2)
    assert out["prop_dealer_hedge_net_billion_twd"] == round(-5634977890 / 1e8, 2)
    assert out["prop_dealer_combined_net_billion_twd"] == round(
        (-2036187921 + -5634977890) / 1e8, 2
    )
    assert out["total_net_billion_twd"] == round(-35023381577 / 1e8, 2)


def test_fetch_twse_three_investors_probes_back_on_empty(monkeypatch):
    """First probe date returns empty (e.g. TW holiday), second succeeds."""
    import datetime as dt
    calls: list[str] = []
    def stubby_get(self, url, params=None, **kw):
        assert params is not None
        d = params["dayDate"]
        calls.append(d)
        # first call returns empty, second returns OK
        body = _TWSE_EMPTY if len(calls) == 1 else _TWSE_OK_RESPONSE
        return httpx.Response(200, json=body,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", stubby_get)
    # today = Wed 2026-07-08 → probes 07-07 (Tue), 07-06 (Mon), 07-03 (Fri, skip weekend)
    out = fx.fetch_twse_three_investors(today=dt.date(2026, 7, 8))
    assert len(calls) == 2
    assert out["as_of_date"] == calls[1]      # locked to the second (success) probe
    assert "foreign_net_billion_twd" in out


def test_fetch_twse_three_investors_skips_weekends(monkeypatch):
    """today = Mon → probe should skip Sun/Sat and hit Fri first."""
    import datetime as dt
    calls: list[str] = []
    def stubby_get(self, url, params=None, **kw):
        calls.append(params["dayDate"])
        return httpx.Response(200, json=_TWSE_OK_RESPONSE,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", stubby_get)
    # 2026-07-13 is a Monday
    fx.fetch_twse_three_investors(today=dt.date(2026, 7, 13))
    # First probe should be 07-10 (Fri), NOT 07-12 (Sun) or 07-11 (Sat)
    assert calls[0] == "20260710"


def test_fetch_twse_three_investors_reports_error_when_all_probes_fail(monkeypatch):
    import datetime as dt
    monkeypatch.setattr(httpx.Client, "get", _resp(json_body=_TWSE_EMPTY))
    out = fx.fetch_twse_three_investors(today=dt.date(2026, 7, 9))
    assert "error" in out
    assert "stat!=OK" in out["error"]


def test_fetch_twse_three_investors_never_raises_on_http_error(monkeypatch):
    import datetime as dt
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    out = fx.fetch_twse_three_investors(today=dt.date(2026, 7, 9))
    assert "error" in out
