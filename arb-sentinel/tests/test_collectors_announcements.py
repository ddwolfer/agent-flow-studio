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


def test_fetch_okx_paginates_until_empty(monkeypatch):
    # OKX's /api/v5/support/announcements is paginated via the `page` query
    # param. A single launchd window can land >10 promo items; without
    # pagination the older ones get truncated and the state dedup means
    # they NEVER show up later.
    pages = {
        ("latest-events", "1"): [{"annType": "latest-events", "title": "p1-a",
                                   "url": "https://okx/a", "pTime": "1"}],
        ("latest-events", "2"): [{"annType": "latest-events", "title": "p1-b",
                                   "url": "https://okx/b", "pTime": "2"}],
        ("latest-events", "3"): [],
        ("announcements-others", "1"): [],
    }
    def fake_get(self, url, **kw):
        params = kw.get("params", {})
        ann_type = params.get("annType")
        page = str(params.get("page", "1"))
        details = pages.get((ann_type, page), [])
        return httpx.Response(200, json={"code": "0", "data": [{"details": details}]},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_okx()
    titles = [a["annTitle"] for a in anns]
    assert errors == []
    assert "p1-a" in titles and "p1-b" in titles, titles


def test_fetch_binance_paginates_until_short_page(monkeypatch):
    # Two pages of 2 items for catalog 49, then a short page (1 item) means
    # we stop. Stop after the FIRST short page; don't keep walking forever.
    pages_seen = {}
    def fake_get(self, url, **kw):
        params = kw.get("params", {})
        cat = str(params.get("catalogId"))
        page_no = int(params.get("pageNo", 1))
        if cat == "49":
            payload = ([{"id": 1, "code": f"a{page_no}", "title": f"t{page_no}a"},
                        {"id": 2, "code": f"b{page_no}", "title": f"t{page_no}b"}]
                       if page_no <= 2
                       else [{"id": 3, "code": f"c{page_no}", "title": "tail"}])
        else:
            payload = []
        pages_seen[(cat, page_no)] = len(payload)
        return httpx.Response(
            200, json={"code": "000000", "data": {"articles": payload}},
            request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    anns, errors = announcements.fetch_binance(page_size=2)
    assert errors == []
    cat49 = [a for a in anns if a["annType"] == "49"]
    assert len(cat49) == 5     # 2 + 2 + 1, then stop


def test_fetch_all_respects_cfg_exchanges(monkeypatch):
    # cfg.exchanges = ["okx"] means the user has explicitly turned off bitget
    # and binance — fetch_all must not silently call them.
    calls = []
    def fake_bitget(*a, **kw):
        calls.append("bitget"); return ([], [])
    def fake_okx(*a, **kw):
        calls.append("okx"); return ([], [])
    def fake_binance(*a, **kw):
        calls.append("binance"); return ([], [])
    monkeypatch.setattr(announcements, "fetch_bitget", fake_bitget)
    monkeypatch.setattr(announcements, "fetch_okx", fake_okx)
    monkeypatch.setattr(announcements, "fetch_binance", fake_binance)

    import types
    cfg_only_okx = types.SimpleNamespace(exchanges=["okx"])
    announcements.fetch_all(cfg_only_okx)
    assert calls == ["okx"]

    calls.clear()
    cfg_only_binance = types.SimpleNamespace(exchanges=["binance"])
    announcements.fetch_all(cfg_only_binance)
    assert calls == ["binance"]


def test_fetch_all_defaults_to_all_three_when_cfg_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(announcements, "fetch_bitget", lambda *a, **kw: (calls.append("bitget") or [], []))
    monkeypatch.setattr(announcements, "fetch_okx", lambda *a, **kw: (calls.append("okx") or [], []))
    monkeypatch.setattr(announcements, "fetch_binance", lambda *a, **kw: (calls.append("binance") or [], []))
    announcements.fetch_all()
    assert set(calls) == {"bitget", "okx", "binance"}


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


def test_looks_like_promo_uses_ann_type_pure_promo_categories():
    # Binance catalog 93 (Latest Activities) and OKX latest-events are PURE
    # promo categories — every item is promotional regardless of title. The
    # ann_type kwarg used to be ignored, so titles like "Binance Wallet x ABC
    # Project" (no Earn/airdrop keyword) were silently dropped despite being
    # actual promos.
    assert announcements.looks_like_promo("Binance Wallet x ABC Project", ann_type="93")
    assert announcements.looks_like_promo("anything goes here", ann_type="latest-events")
    # Defensive: ann_type for a non-promo category falls through to the
    # keyword check; an unrelated title in catalog 48 (New Listings) stays
    # negative unless a keyword matches.
    assert not announcements.looks_like_promo("OKX to delist FOO perpetual",
                                              ann_type="48")
    assert not announcements.looks_like_promo("Notice of Removal of Spot Pairs",
                                              ann_type="latest_news")


def test_looks_like_promo_matches_simplified_chinese():
    # Bitget zh_CN feed returns Simplified titles; PROMO_KEYWORDS used to be
    # Traditional-only so 44 fetched / 1 flagged. Codepoint-exact `in` matching
    # means 理財 ≠ 理财, so Simplified variants must be present in PROMO_KEYWORDS.
    assert announcements.looks_like_promo("Bitget 理财双币赢推出 USDT 活动")
    assert announcements.looks_like_promo("Bitget USDGO 限时补贴活动")
    assert announcements.looks_like_promo("赚币奖励上线: 质押 BGB 享高息")
    assert announcements.looks_like_promo("回馈用户: 现货返佣活动")
