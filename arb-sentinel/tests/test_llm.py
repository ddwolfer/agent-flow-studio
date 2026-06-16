import httpx
from arb_sentinel import llm


def test_extract_json_balanced():
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('noise {"a": {"b": 2}} trailing') == {"a": {"b": 2}}
    assert llm._extract_json("no json here") is None


def _groq_reply(content):
    def fake_post(self, url, **kw):
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]},
                             request=httpx.Request("POST", url))
    return fake_post


def test_extract_promo_normalises_percent_to_decimal(monkeypatch):
    reply = '{"is_promotion": true, "activity_name": "X", "start_date": "2026-06-01",' \
            '"end_date": "2026-06-30", "apr_percent": 12, "min_hold_days": 14,' \
            '"entry_asset": "USDT", "subsidy_note": "s", "directional_risk": false}'
    monkeypatch.setattr(httpx.Client, "post", _groq_reply(reply))
    out = llm.extract_promo("t", "b", api_key="k")
    assert out["is_promotion"] is True
    assert abs(out["apr"] - 0.12) < 1e-9          # 12 percent -> 0.12 decimal
    assert out["entry_asset"] == "USDT"


def test_extract_promo_null_apr(monkeypatch):
    monkeypatch.setattr(httpx.Client, "post",
                        _groq_reply('{"is_promotion": false, "apr_percent": null}'))
    out = llm.extract_promo("t", "b", api_key="k")
    assert out["is_promotion"] is False and out["apr"] is None


def test_extract_promo_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert llm.extract_promo("t", "b", api_key="") is None


def test_extract_promo_never_raises_on_http_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", boom)
    assert llm.extract_promo("t", "b", api_key="k") is None
