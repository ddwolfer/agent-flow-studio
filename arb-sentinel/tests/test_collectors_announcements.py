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


def test_fetch_okx_normalises_and_tags_exchange(monkeypatch):
    payload = {"code": "0", "data": [{"details": [
        {"annType": "latest-events", "title": "OKX Earn event", "url": "https://okx/help/x",
         "pTime": "1781588100000"}]}]}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_okx()
    assert errors == []
    a = anns[0]
    assert a["_exchange"] == "okx" and a["annId"] == "https://okx/help/x"
    assert a["annTitle"] == "OKX Earn event" and a["annUrl"] == "https://okx/help/x"


def test_looks_like_promo():
    assert announcements.looks_like_promo("OKX Flash Earn is Now Live")
    assert announcements.looks_like_promo("OKX Launches CeDeFi Boost event")
    assert announcements.looks_like_promo("Bitget USDGO 限時補貼活動")
    assert not announcements.looks_like_promo("Scheduled Maintenance: Email System")
    assert not announcements.looks_like_promo("OKX to delist FOO perpetual")


def test_looks_like_promo_matches_simplified_chinese():
    # Bitget zh_CN feed returns Simplified titles; PROMO_KEYWORDS used to be
    # Traditional-only so 44 fetched / 1 flagged. Codepoint-exact `in` matching
    # means 理財 ≠ 理财, so Simplified variants must be present in PROMO_KEYWORDS.
    assert announcements.looks_like_promo("Bitget 理财双币赢推出 USDT 活动")
    assert announcements.looks_like_promo("Bitget USDGO 限时补贴活动")
    assert announcements.looks_like_promo("赚币奖励上线: 质押 BGB 享高息")
    assert announcements.looks_like_promo("回馈用户: 现货返佣活动")
