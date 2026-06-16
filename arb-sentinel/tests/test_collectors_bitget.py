import types
import httpx
from arb_sentinel.collectors import bitget


def _cfg(**kw):
    base = dict(assets=["USDT", "USDC"], bitget_api_key="k",
                bitget_api_secret="s", bitget_api_passphrase="p")
    base.update(kw)
    return types.SimpleNamespace(**base)


_RESP = {"code": "00000", "msg": "success", "data": [
    {"productId": "1", "coin": "USDT", "periodType": "flexible", "apyType": "ladder",
     "apyList": [{"rateLevel": "0", "currentApy": "6.50"},
                 {"rateLevel": "1", "currentApy": "4.00"}]},
    {"productId": "2", "coin": "USDC", "periodType": "flexible", "apyType": "single",
     "apyList": [{"rateLevel": "0", "currentApy": "5.00"}]},
]}


def test_percent_to_decimal_conversion(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=_RESP, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = bitget.collect_rates(_cfg())
    assert errors == []
    usdt = next(o for o in opps if o.asset == "USDT")
    assert abs(usdt.apr - 0.065) < 1e-9          # "6.50" percent -> 0.065 decimal
    assert "L0:6.50%" in usdt.tier_info


def test_bitget_error_code_is_handled(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json={"code": "40037", "msg": "apikey invalid"},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = bitget.collect_rates(_cfg())
    assert opps == [] and len(errors) == 1 and "40037" in errors[0]


def test_missing_keys_skips_without_network():
    opps, errors = bitget.collect_rates(_cfg(bitget_api_key=""))
    assert opps == [] and len(errors) == 1 and "skipped" in errors[0]


def test_tier_selected_by_ref_capital_and_promo_flag(monkeypatch):
    # 30000 falls in the L1 band, so the honest rate is 1.31% — NOT the 6.97% headline
    # that only covers the first 300. The headline must be flagged promotional.
    resp = {"code": "00000", "data": [
        {"coin": "USDT", "periodType": "flexible", "apyType": "ladder", "apyList": [
            {"rateLevel": "0", "currentApy": "6.97", "minStepVal": "0", "maxStepVal": "300"},
            {"rateLevel": "1", "currentApy": "1.31", "minStepVal": "300", "maxStepVal": "120000000"}]},
    ]}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=resp, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = bitget.collect_rates(_cfg(assets=["USDT"], ref_capital=30000))
    assert errors == []
    u = opps[0]
    assert abs(u.apr - 0.0131) < 1e-9
    assert u.apr_is_promotional is True
    assert "6.97%" in (u.subsidy_note or "")
