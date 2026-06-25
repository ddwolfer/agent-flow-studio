import types
import httpx
from arb_sentinel.collectors import binance


def _cfg(**kw):
    base = dict(assets=["USDC", "USDT"], binance_api_key="k", binance_api_secret="s")
    base.update(kw)
    return types.SimpleNamespace(**base)


_RESP = {"total": 2, "rows": [
    {"asset": "USDC", "latestAnnualPercentageRate": "0.01227912",
     "tierAnnualPercentageRate": {"0-300USDC": "0.05"}, "canPurchase": True},
    {"asset": "USDT", "latestAnnualPercentageRate": "0.01178866",
     "tierAnnualPercentageRate": {}, "canPurchase": True},
]}


def test_collect_rates_parses_decimal_apr(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=_RESP, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = binance.collect_rates(_cfg())
    assert errors == []
    usdc = next(o for o in opps if o.asset == "USDC")
    assert usdc.exchange == "binance" and usdc.apr_source == "api"
    assert abs(usdc.apr - 0.01227912) < 1e-9


def test_missing_keys_skips_without_network():
    opps, errors = binance.collect_rates(_cfg(binance_api_key="", binance_api_secret=""))
    assert opps == [] and len(errors) == 1 and "skipped" in errors[0]


def test_never_raises_on_http_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    opps, errors = binance.collect_rates(_cfg())
    assert opps == [] and len(errors) >= 1


def test_collect_borrow_annualises_hourly_rate(monkeypatch):
    rows = [{"asset": "USDT", "nextHourlyInterestRate": "0.00000385"},
            {"asset": "BTC", "nextHourlyInterestRate": "0.00000045"}]
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=rows, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    rates, errors = binance.collect_borrow(_cfg())
    assert errors == []
    assert abs(rates["USDT"] - 0.00000385 * 24 * 365) < 1e-12   # hourly -> annual


def test_collect_borrow_missing_keys_skips():
    rates, errors = binance.collect_borrow(_cfg(binance_api_key="", binance_api_secret=""))
    assert rates == {} and len(errors) == 1


def test_collect_borrow_handles_dict_shaped_error_response(monkeypatch):
    # Binance sometimes returns HTTP 200 + dict-shaped error envelope
    # ({"code": -1234, "msg": "..."}) instead of the documented list of rows.
    # Iterating over a dict yields str keys, so `row.get("asset")` would
    # AttributeError out of collect_borrow and violate never-raise.
    err_body = {"code": -1003, "msg": "Too many requests"}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=err_body, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    rates, errors = binance.collect_borrow(_cfg())
    assert rates == {}
    assert any("Too many requests" in e or "shape" in e or "code" in e.lower()
               for e in errors)


def test_collect_rates_handles_dict_shaped_error_response(monkeypatch):
    # Same defense for collect_rates: signed FLEX endpoint may return
    # {"code":-2015,"msg":"Invalid API-key"} as the JSON body even on HTTP 200.
    err_body = {"code": -2015, "msg": "Invalid API-key"}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=err_body, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = binance.collect_rates(_cfg())
    assert opps == []
    assert any("Invalid API-key" in e or "code" in e.lower() for e in errors)
