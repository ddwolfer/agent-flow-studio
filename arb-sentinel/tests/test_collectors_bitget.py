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


def test_applicable_apy_converts_usd_ref_capital_to_coin_units():
    # Bitget tier bands are denominated in the COIN, but ref_capital is USD.
    # For BTC at spot ~70k, 30000 USD = 0.428 BTC — should land in the [0, 0.5)
    # tier (the middle, 5% rate), NOT fall beyond all bands into the last
    # smallest-tier rate.
    apylist = [
        {"rateLevel": "0", "currentApy": "8.0", "minStepVal": "0",    "maxStepVal": "0.5"},
        {"rateLevel": "1", "currentApy": "5.0", "minStepVal": "0.5",  "maxStepVal": "5"},
        {"rateLevel": "2", "currentApy": "1.5", "minStepVal": "5",    "maxStepVal": "0"},
    ]
    # Old behaviour (no spot_usd): 30000 > 5 → falls through to last tier (1.5%)
    legacy = bitget._applicable_apy(apylist, ref_capital=30000)
    assert legacy is not None and legacy[0] == 1.5
    # New behaviour: spot_usd=70000 → 30000/70000 ≈ 0.428 → tier 0 band [0, 0.5) → 8.0%
    fixed = bitget._applicable_apy(apylist, ref_capital=30000, spot_usd=70000)
    assert fixed is not None
    assert fixed[0] == 8.0
    # Stablecoin path (spot_usd=1.0 or None): 30000 → tier 2 [5, ∞) → 1.5%
    stable = bitget._applicable_apy(apylist, ref_capital=30000, spot_usd=1.0)
    assert stable[0] == 1.5


def test_collect_rates_fetches_spot_for_non_stables(monkeypatch):
    # The collector must look up a coin-to-USD spot for non-stables (e.g. BTC)
    # via Bitget's keyless spot ticker, so band matching lands on the right
    # tier. Stables (USDT/USDC) skip the spot fetch and treat ref_capital as
    # coin units.
    products = {"code": "00000", "data": [
        {"coin": "BTC", "periodType": "flexible", "apyType": "ladder", "apyList": [
            {"rateLevel": "0", "currentApy": "8.0", "minStepVal": "0",   "maxStepVal": "0.5"},
            {"rateLevel": "1", "currentApy": "5.0", "minStepVal": "0.5", "maxStepVal": "5"},
            {"rateLevel": "2", "currentApy": "1.5", "minStepVal": "5",   "maxStepVal": "0"}]},
    ]}
    ticker = {"code": "00000", "data": [{"symbol": "BTCUSDT", "lastPr": "70000"}]}
    fetched_symbols = []
    def fake_get(self, url, **kw):
        if "spot/market/tickers" in url:
            fetched_symbols.append(kw.get("params", {}).get("symbol"))
            return httpx.Response(200, json=ticker, request=httpx.Request("GET", url))
        # signed savings/product
        return httpx.Response(200, json=products, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    opps, errors = bitget.collect_rates(_cfg(assets=["BTC"], ref_capital=30000))
    assert errors == []
    assert opps[0].asset == "BTC"
    # 30000 USD / 70000 USD/BTC = 0.428 BTC → tier 0 band [0, 0.5) → 8.0%
    assert abs(opps[0].apr - 0.08) < 1e-9
    assert "BTCUSDT" in fetched_symbols
