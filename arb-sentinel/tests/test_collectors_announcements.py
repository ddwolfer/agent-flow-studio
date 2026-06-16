import httpx
from arb_sentinel.collectors import announcements


def test_fetch_bitget_parses(monkeypatch):
    payload = {"code": "00000", "data": [
        {"annId": "1", "annTitle": "促銷", "annDesc": "d", "annUrl": "u",
         "annType": "latest_news", "cTime": "1"}]}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_bitget()
    assert errors == []
    assert any(a["annId"] == "1" for a in anns)


def test_fetch_bitget_never_raises(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    anns, errors = announcements.fetch_bitget()
    assert anns == [] and len(errors) >= 1
