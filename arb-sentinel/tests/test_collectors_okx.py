import json, pathlib
import httpx
from arb_sentinel.collectors import okx

FIX = pathlib.Path(__file__).parent / "fixtures"

def _mock_client(monkeypatch, payload):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)

def test_collect_rates_maps_to_opportunities(monkeypatch, cfg):
    _mock_client(monkeypatch, json.loads((FIX / "okx_lending_summary.json").read_text()))
    opps, errors = okx.collect_rates(cfg)
    assert errors == []
    usdc = next(o for o in opps if o.asset == "USDC")
    assert usdc.exchange == "okx" and usdc.category == "flexible_earn"
    assert usdc.apr == 0.025 and usdc.apr_source == "api"

def test_collect_never_raises_on_http_error(monkeypatch, cfg):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    opps, errors = okx.collect_rates(cfg)
    assert opps == [] and len(errors) == 1   # logged, not raised
