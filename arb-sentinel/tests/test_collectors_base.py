import httpx
from arb_sentinel.collectors import base


def test_get_json_returns_payload_on_2xx(monkeypatch):
    def fake_get(self, url, **kw):
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    data, err = base.get_json("https://x")
    assert err is None and data == {"ok": True}


def test_get_json_does_not_retry_4xx_non_429(monkeypatch):
    # 404 / 400 are deterministic; retrying just wastes the timeout budget.
    calls = {"n": 0}
    def fake_get(self, url, **kw):
        calls["n"] += 1
        return httpx.Response(404, text="not found",
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(base, "_BACKOFF_SECONDS", (0, 0, 0))  # never sleep
    data, err = base.get_json("https://x")
    assert data is None and err is not None and "404" in err
    assert calls["n"] == 1


def test_get_json_retries_5xx_and_succeeds(monkeypatch):
    # 503 should retry; second attempt succeeds → caller sees data, no error.
    calls = {"n": 0}
    def fake_get(self, url, **kw):
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, text="bad gateway",
                                  request=httpx.Request("GET", url))
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(base, "_BACKOFF_SECONDS", (0, 0, 0))
    data, err = base.get_json("https://x")
    assert err is None and data == {"ok": True}
    assert calls["n"] == 2


def test_get_json_retries_429_and_succeeds(monkeypatch):
    calls = {"n": 0}
    def fake_get(self, url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, text="slow down",
                                  request=httpx.Request("GET", url))
        return httpx.Response(200, json={"ok": 1},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(base, "_BACKOFF_SECONDS", (0, 0, 0))
    data, err = base.get_json("https://x")
    assert err is None and data == {"ok": 1}
    assert calls["n"] == 2


def test_get_json_retries_transport_error_and_succeeds(monkeypatch):
    # ConnectError / ReadTimeout etc. are transient and should retry.
    calls = {"n": 0}
    def fake_get(self, url, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("flaky",
                                     request=httpx.Request("GET", url))
        return httpx.Response(200, json={"ok": 1},
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(base, "_BACKOFF_SECONDS", (0, 0, 0))
    data, err = base.get_json("https://x")
    assert err is None and data == {"ok": 1}
    assert calls["n"] == 2


def test_get_json_gives_up_after_max_attempts(monkeypatch):
    calls = {"n": 0}
    def fake_get(self, url, **kw):
        calls["n"] += 1
        return httpx.Response(503, text="down",
                              request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    monkeypatch.setattr(base, "_BACKOFF_SECONDS", (0, 0, 0))
    data, err = base.get_json("https://x")
    assert data is None and "503" in err
    assert calls["n"] == 3   # 1 initial + 2 retries
