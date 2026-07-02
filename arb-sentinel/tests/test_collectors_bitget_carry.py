"""Tests for the carry-guardian collector extensions in bitget.py.

Live-verified shapes captured 2026-07-02 via scripts/carry-smoke.py — see
docs/superpowers/specs/carry-smoke-notes.md for unit traps."""
import types
import httpx
from arb_sentinel.collectors import bitget


def _cfg(**kw):
    base = dict(bitget_api_key="k", bitget_api_secret="s",
                bitget_api_passphrase="p",
                carry_loan_order_id="1454384882276573190",
                carry_loan_coin="USDC",
                carry_earn_asset="USDGO",
                carry_pair="USDGOUSDC")
    base.update(kw)
    return types.SimpleNamespace(**base)


# ── loan_ongoing_orders ──────────────────────────────────────────────────────
_LOAN_RESP = {"code": "00000", "msg": "success", "data": [{
    "orderId": "1454384882276573190",
    "loanCoin": "USDC",
    "loanAmount": "21580.3944434",
    "interestAmount": "0.64870669",
    "hourInterestRate": "0.000313",     # PERCENT-per-hour string
    "pledgeCoin": "BTC",
    "pledgeAmount": "0.56571125",
    "pledgeRate": "61.71",              # PERCENT string
    "supRate": "85",
    "forceRate": "91",
    "borrowTime": "1782478297775",
    "expireTime": "0",
}]}


def test_loan_ongoing_orders_normalises_percent_units(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=_LOAN_RESP,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    orders, errors = bitget.loan_ongoing_orders(_cfg())
    assert errors == []
    o = orders[0]
    assert o["order_id"] == "1454384882276573190"
    assert o["loan_coin"] == "USDC" and o["pledge_coin"] == "BTC"
    # The critical /100 normalisation
    assert abs(o["ltv"] - 0.6171) < 1e-9
    assert abs(o["margin_call_ltv"] - 0.85) < 1e-9
    assert abs(o["liquidation_ltv"] - 0.91) < 1e-9
    # Hour rate → decimal per hour
    assert abs(o["hour_rate"] - 0.00000313) < 1e-15
    # Annualised: hour_rate × 24 × 365
    assert abs(o["annual_rate"] - 0.00000313 * 24 * 365) < 1e-12
    # Raw decimal fields kept for accounting
    assert abs(o["loan_amount"] - 21580.3944434) < 1e-6
    assert abs(o["pledge_amount"] - 0.56571125) < 1e-9
    assert abs(o["interest_amount"] - 0.64870669) < 1e-9


def test_loan_ongoing_orders_matches_target_order_id(monkeypatch):
    # When multiple orders come back, pick the one matching config.
    resp = {"code": "00000", "data": [
        {**_LOAN_RESP["data"][0], "orderId": "999999", "loanCoin": "USDT"},
        _LOAN_RESP["data"][0],
    ]}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=resp,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    orders, errors = bitget.loan_ongoing_orders(_cfg())
    assert errors == []
    assert len(orders) == 1                      # only the matching one surfaces
    assert orders[0]["order_id"] == "1454384882276573190"


def test_loan_ongoing_orders_returns_empty_when_no_active(monkeypatch):
    # Position closed / liquidated — "訂單消失" signal per spec §5.1 tail.
    def fake_get(self, url, **kw):
        return httpx.Response(200, json={"code": "00000", "data": []},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    orders, errors = bitget.loan_ongoing_orders(_cfg())
    assert orders == [] and errors == []


def test_loan_ongoing_orders_never_raises_on_http_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    orders, errors = bitget.loan_ongoing_orders(_cfg())
    assert orders == [] and len(errors) >= 1


# ── loan_hour_interest (public) ──────────────────────────────────────────────
def test_loan_hour_interest_returns_annualised(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json={
            "code": "00000",
            "data": {"coin": "USDC", "hourInterestRate": "0.000450"}
        }, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    out, errors = bitget.loan_hour_interest("USDC")
    assert errors == []
    assert abs(out["hour_rate"] - 0.0000045) < 1e-15
    assert abs(out["annual_rate"] - 0.0000045 * 24 * 365) < 1e-12


# ── savings_assets ───────────────────────────────────────────────────────────
# Live-verified 2026-07-02 shape: data.resultList list; per-product dict
# has holdAmount / lastProfit / totalProfit / apy tiers.
_SAVINGS_RESP = {"code": "00000", "data": {"resultList": [
    {"productCoin": "BTC", "holdAmount": "0.42798196",
     "lastProfit": "0", "totalProfit": "0",
     "apy": [{"rateLevel": "1", "minApy": "0", "maxApy": "100",
              "currentApy": "2.50"}]},
    {"productCoin": "USDGO", "holdAmount": "24604.61217546",
     "lastProfit": "0.84262368", "totalProfit": "15.70237854",
     "apy": [{"rateLevel": "1", "minApy": "0", "maxApy": "100000", "currentApy": "10.00"},
             {"rateLevel": "2", "minApy": "100000", "maxApy": "1000000", "currentApy": "6.50"},
             {"rateLevel": "3", "minApy": "1000000", "maxApy": "50000000", "currentApy": "4.00"}]},
]}}


def test_savings_assets_finds_usdgo_full_shape(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=_SAVINGS_RESP,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    result, errors = bitget.savings_assets("USDGO", _cfg())
    assert errors == []
    assert result["asset"] == "USDGO"
    assert abs(result["balance"] - 24604.61217546) < 1e-6
    # lastProfit resolves §5.2 payout audit — no balance-delta needed
    assert abs(result["last_profit"] - 0.84262368) < 1e-9
    assert abs(result["total_profit"] - 15.70237854) < 1e-9
    # apy tiers surfaced for digest / expected-payout calculation
    assert len(result["apy_tiers"]) == 3
    tier1 = result["apy_tiers"][0]
    assert tier1["apy_percent"] == 10.00
    assert tier1["min"] == 0 and tier1["max"] == 100000


def test_savings_assets_returns_none_when_asset_missing(monkeypatch):
    resp = {"code": "00000", "data": {"resultList": []}}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=resp,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    result, errors = bitget.savings_assets("USDGO", _cfg())
    assert result is None and errors == []


# ── spot_orderbook (public) ──────────────────────────────────────────────────
def test_spot_orderbook_parses_bids_and_cumulative_depth(monkeypatch):
    resp = {"code": "00000", "data": {
        "bids": [["1.0002", "500"], ["1.0001", "1000"],
                 ["1.0000", "2000"], ["0.9999", "3000"]],
        "asks": [["1.0004", "100"]],
    }}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=resp,
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    book, errors = bitget.spot_orderbook("USDGOUSDC", limit=15)
    assert errors == []
    assert abs(book["bid1_price"] - 1.0002) < 1e-9
    assert abs(book["bid1_qty"] - 500) < 1e-9
    # Cumulative sum of qtys across bids
    assert abs(book["cum_bid_qty"] - 6500.0) < 1e-9
    assert book["bid_levels"] == 4


def test_spot_orderbook_never_raises_on_transport_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    book, errors = bitget.spot_orderbook("USDGOUSDC", limit=15)
    assert book is None and errors
