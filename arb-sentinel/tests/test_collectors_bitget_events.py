import httpx
from arb_sentinel.collectors import bitget_events


def _resp(html, status=200):
    def fake_get(self, url, **kw):
        return httpx.Response(status, text=html,
                              request=httpx.Request("GET", url))
    return fake_get


_HTML_THREE_ACTIVE = """<html><body>
<div>Bitget PoolX 鎖倉獲得新代幣空投</div>
<div>進行中(3) 即將開始(1) 已結束</div>
</body></html>"""

_HTML_ZERO = """<html><body>
<div>Bitget PoolX 鎖倉獲得新代幣空投</div>
<div>進行中(0) 即將開始(0) 已結束</div>
<div>暫無項目</div>
</body></html>"""

_HTML_FULL_WIDTH_PARENS = """<html><body>
<div>進行中（2） 即將開始（0） 已結束</div>
</body></html>"""

_HTML_NO_COUNTS = """<html><body>
<div>This page has no PoolX counts at all.</div>
</body></html>"""


def test_fetch_event_status_parses_counts(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", _resp(_HTML_THREE_ACTIVE))
    items, errors = bitget_events.fetch_event_status()
    assert errors == []
    assert len(items) == 2     # PoolX + Launchpool both fetched
    poolx = next(i for i in items if i["page"] == "PoolX")
    assert poolx["active"] == 3 and poolx["upcoming"] == 1
    assert poolx["url"].startswith("https://www.bitget.com/")


def test_fetch_event_status_handles_zero_counts(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", _resp(_HTML_ZERO))
    items, errors = bitget_events.fetch_event_status()
    assert errors == []
    poolx = next(i for i in items if i["page"] == "PoolX")
    assert poolx["active"] == 0 and poolx["upcoming"] == 0


def test_fetch_event_status_handles_full_width_parens(monkeypatch):
    # Bitget's SSR sometimes uses full-width brackets （） instead of ASCII ()
    monkeypatch.setattr(httpx.Client, "get", _resp(_HTML_FULL_WIDTH_PARENS))
    items, errors = bitget_events.fetch_event_status()
    poolx = next(i for i in items if i["page"] == "PoolX")
    assert poolx["active"] == 2 and poolx["upcoming"] == 0


def test_fetch_event_status_returns_none_when_pattern_missing(monkeypatch):
    # SSR layout may change. When the regex misses, surface an error rather
    # than guessing a 0 (which would suppress legitimate alerts).
    monkeypatch.setattr(httpx.Client, "get", _resp(_HTML_NO_COUNTS))
    items, errors = bitget_events.fetch_event_status()
    assert items == []
    assert errors and any("pattern" in e.lower() or "parse" in e.lower()
                          for e in errors)


def test_fetch_event_status_never_raises_on_http_error(monkeypatch):
    def boom(self, url, **kw):
        raise httpx.ConnectError("down", request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", boom)
    items, errors = bitget_events.fetch_event_status()
    assert items == []
    assert errors and len(errors) >= 2   # one per page


def test_fetch_event_status_handles_non_200(monkeypatch):
    monkeypatch.setattr(httpx.Client, "get", _resp("blocked", status=403))
    items, errors = bitget_events.fetch_event_status()
    assert items == []
    assert errors and "403" in errors[0]
