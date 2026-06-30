"""Tests for the rewritten bitget_events collector (XHR-based, post commit 20de6f7)."""
import httpx
from arb_sentinel.collectors import bitget_events


def _mock_post(responses):
    """Build a fake httpx.Client.post that dispatches on URL path. `responses`
    is {path_substring: (status, json_body)}."""
    def fake_post(self, url, **kw):
        for sub, (status, body) in responses.items():
            if sub in url:
                return httpx.Response(status, json=body,
                                      request=httpx.Request("POST", url))
        raise AssertionError(f"unmocked URL: {url}")
    return fake_post


_POOLX_COUNT_3 = (200, {"code": "200", "data": {
    "overNum": "272", "runningNum": "3", "waitStartNum": "0"}})

_POOLX_LIST_3 = (200, {"code": "200", "data": {"items": [
    {"id": "id-JTO", "productCoinName": "JTO", "totalRewards": "46000",
     "endTime": "1783249200000",
     "productDetailLinkUrl": "https://www.bitget.com/events/poolx/id-JTO",
     "productSubList": [{"productSubCoinName": "BGSOL", "apr": "20.88"}]},
    {"id": "id-BLUAI", "productCoinName": "BLUAI", "totalRewards": "14000000",
     "endTime": "1783418400000",
     "productDetailLinkUrl": "https://www.bitget.com/events/poolx/id-BLUAI",
     "productSubList": [{"productSubCoinName": "ETH", "apr": "5.75"}]},
    {"id": "id-O", "productCoinName": "O", "totalRewards": "350000",
     "endTime": "1782993600000",
     "productDetailLinkUrl": "https://www.bitget.com/events/poolx/id-O",
     "productSubList": [{"productSubCoinName": "BTC", "apr": "3.90"}]},
]}})

_LAUNCH_COUNT_0 = (200, {"code": "200", "data": {
    "overNum": "0", "runningNum": "0", "waitStartNum": "0"}})


def test_fetch_event_status_parses_running_and_projects(monkeypatch):
    monkeypatch.setattr(httpx.Client, "post", _mock_post({
        "poolx/product/count": _POOLX_COUNT_3,
        "poolx/product/page/list/new": _POOLX_LIST_3,
        "launchpool/product/count": _LAUNCH_COUNT_0,
    }))
    items, errors = bitget_events.fetch_event_status()
    assert errors == []
    poolx = next(i for i in items if i["page"] == "PoolX")
    assert poolx["running_num"] == 3
    assert poolx["wait_start_num"] == 0
    assert len(poolx["projects"]) == 3
    jto = next(p for p in poolx["projects"] if p["reward_coin"] == "JTO")
    assert jto["stake_coin"] == "BGSOL"
    assert jto["apr_percent"] == "20.88"
    assert jto["id"] == "id-JTO"
    launch = next(i for i in items if i["page"] == "Launchpool")
    assert launch["running_num"] == 0
    assert launch["projects"] == []


def test_fetch_event_status_skips_list_when_no_active(monkeypatch):
    # Optimisation: with runningNum=0 we should NOT call /list — save a RTT.
    list_called = []
    def fake_post(self, url, **kw):
        if "list" in url:
            list_called.append(url)
        if "poolx/product/count" in url:
            return httpx.Response(200, json={"code": "200", "data": {
                "overNum": "0", "runningNum": "0", "waitStartNum": "0"}},
                request=httpx.Request("POST", url))
        if "launchpool/product/count" in url:
            return httpx.Response(200, json=_LAUNCH_COUNT_0[1],
                                  request=httpx.Request("POST", url))
        raise AssertionError(f"unexpected: {url}")
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    bitget_events.fetch_event_status()
    assert list_called == [], f"list was called even though running=0: {list_called}"


def test_fetch_event_status_handles_count_http_error(monkeypatch):
    def fake_post(self, url, **kw):
        return httpx.Response(503, text="bad gateway",
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    items, errors = bitget_events.fetch_event_status()
    assert items == []
    assert len(errors) == 2  # one per page
    assert all("HTTP 503" in e for e in errors)


def test_fetch_event_status_handles_non_200_code(monkeypatch):
    monkeypatch.setattr(httpx.Client, "post", _mock_post({
        "poolx/product/count": (200, {"code": "1001", "msg": "rate limited"}),
        "launchpool/product/count": _LAUNCH_COUNT_0,
    }))
    items, errors = bitget_events.fetch_event_status()
    assert any("1001" in e or "rate limited" in e for e in errors)
    # Launchpool still surfaces normally
    assert any(i["page"] == "Launchpool" for i in items)


def test_fetch_event_status_never_raises_on_transport_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", boom)
    items, errors = bitget_events.fetch_event_status()
    assert items == []
    assert len(errors) == 2


def test_fetch_event_status_surfaces_partial_when_list_fails(monkeypatch):
    # Count succeeds (runningNum=3), but list throws. We still want to know
    # there ARE 3 active pools, even without the names.
    def fake_post(self, url, **kw):
        if "count" in url and "poolx" in url:
            return httpx.Response(200, json=_POOLX_COUNT_3[1],
                                  request=httpx.Request("POST", url))
        if "count" in url and "launchpool" in url:
            return httpx.Response(200, json=_LAUNCH_COUNT_0[1],
                                  request=httpx.Request("POST", url))
        if "list" in url and "poolx" in url:
            raise httpx.ConnectError("list-down", request=httpx.Request("POST", url))
        raise AssertionError(f"unexpected: {url}")
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    items, errors = bitget_events.fetch_event_status()
    poolx = next(i for i in items if i["page"] == "PoolX")
    assert poolx["running_num"] == 3
    assert poolx["projects"] == []
    assert any("list" in e for e in errors)
