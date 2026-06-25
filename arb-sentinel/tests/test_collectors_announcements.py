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


def test_fetch_binance_normalises_and_tags_exchange(monkeypatch):
    # catalog/list/query returns code="000000" (six zeros, not Bitget's five).
    payload = {"code": "000000", "data": {"articles": [
        {"id": 278063, "code": "a6b7d5a8a14a44c1b6a6a34813c6d93f",
         "title": "Binance Earn Yield Arena: Earn Up to 35% APR With This Week",
         "releaseDate": 1781598000000},
        {"id": 278099, "code": "ba04ce1272df4bdf8d2595ccb0e19540",
         "title": "Binance Traders League Season 3: Trade CHR or ETH",
         "releaseDate": 1781598900000},
    ]}}
    def fake_get(self, url, **kw):
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_binance()
    assert errors == []
    a = anns[0]
    assert a["_exchange"] == "binance"
    assert a["annId"] == "a6b7d5a8a14a44c1b6a6a34813c6d93f"
    assert a["annUrl"] == ("https://www.binance.com/en/support/announcement/"
                          "a6b7d5a8a14a44c1b6a6a34813c6d93f")
    assert a["annTitle"].startswith("Binance Earn Yield Arena")
    # Same fake response is returned for every catalog probe — three catalogs
    # configured, so 2 articles × 3 catalogs = 6 entries.
    assert len(anns) == 6


def test_fetch_binance_handles_non_zero_code(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json={"code": "100000", "message": "rate limited"},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_binance()
    assert anns == [] and len(errors) >= 1


def test_fetch_binance_never_raises(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("blocked", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    anns, errors = announcements.fetch_binance()
    assert anns == [] and len(errors) >= 1


def test_fetch_all_includes_binance(monkeypatch):
    # All three exchanges return one item each; fetch_all must surface all
    # three tagged with the right _exchange value.
    bitget_payload = {"code": "00000", "data": [
        {"annId": "bg1", "annTitle": "Bitget 活动", "annDesc": "", "annUrl": "u",
         "annType": "latest_news", "cTime": "1"}]}
    okx_payload = {"code": "0", "data": [{"details": [
        {"annType": "latest-events", "title": "OKX Earn", "url": "https://okx/x",
         "pTime": "1"}]}]}
    binance_payload = {"code": "000000", "data": {"articles": [
        {"id": 1, "code": "abc", "title": "Binance Earn", "releaseDate": 1}]}}

    def fake_get(self, url, **kw):
        if "bitget" in url:
            return httpx.Response(200, json=bitget_payload,
                                  request=httpx.Request("GET", url))
        if "okx.com/api/v5/support/announcements" in url:
            return httpx.Response(200, json=okx_payload,
                                  request=httpx.Request("GET", url))
        if "binance.com/bapi" in url:
            return httpx.Response(200, json=binance_payload,
                                  request=httpx.Request("GET", url))
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_all()
    exchanges = {a["_exchange"] for a in anns}
    assert exchanges == {"bitget", "okx", "binance"}


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
