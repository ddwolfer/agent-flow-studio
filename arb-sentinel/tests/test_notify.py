import httpx
from arb_sentinel.models import Opportunity, ACT_NOW
from arb_sentinel import notify

def test_format_escapes_html(cfg):
    o = Opportunity(exchange="okx", category="flexible_earn", asset="A&B",
                    apr=0.052, apr_source="api")
    msg = notify.format_opportunity(o, 0.052, {"est_net": 60.0, "holding_days": 14}, "NO_DEADLINE", ACT_NOW, cfg)
    assert "A&amp;B" in msg          # & escaped
    assert "5.2%" in msg

def test_send_posts_to_topic(monkeypatch, cfg):
    captured = {}
    def fake_post(self, url, data=None, **kw):
        captured["url"] = url; captured["data"] = data
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    ok = notify.send_message("hi", cfg)
    assert ok is True
    assert captured["data"]["message_thread_id"] == "1390"
    assert captured["data"]["parse_mode"] == "HTML"

def test_format_opportunity_handles_none_apr(cfg):
    o = Opportunity(exchange="okx", category="stable_depeg", asset="USDC-USDT",
                    apr=None, apr_source="api", subsidy_note="last=1.0005")
    msg = notify.format_opportunity(o, None, {}, "NO_DEADLINE", "WATCH", cfg)
    assert "—" in msg            # apr rendered as dash, no crash

def test_send_returns_false_on_non_200(monkeypatch, cfg):
    def fake_post(self, url, data=None, **kw):
        return httpx.Response(500, text="err", request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert notify.send_message("hi", cfg) is False


def test_send_fails_closed_when_topic_arb_missing(monkeypatch, cfg):
    # Empty TELEGRAM_TOPIC_ARB used to silently fall through and send the alert
    # to the group's General chat instead of topic 1390 — violates the
    # "every arb alert lives in topic 1390" routing rule. Must fail-closed.
    posted = {"called": False}
    def fake_post(self, url, data=None, **kw):
        posted["called"] = True
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg.telegram_topic_arb = ""
    assert notify.send_message("hi", cfg) is False
    assert posted["called"] is False, "must not POST to Telegram when topic_arb empty"


def test_send_uses_topic_override_when_supplied(monkeypatch, cfg):
    # carry-guardian sends to TELEGRAM_TOPIC_CARRY (different from _ARB).
    # send_message accepts a `topic` kwarg to override cfg.telegram_topic_arb.
    captured = {}
    def fake_post(self, url, data=None, **kw):
        captured["data"] = data
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    ok = notify.send_message("hi", cfg, topic="1521")
    assert ok is True
    assert captured["data"]["message_thread_id"] == "1521"   # overridden
    # NOT the default topic_arb "1390"
    assert captured["data"]["message_thread_id"] != cfg.telegram_topic_arb


def test_send_fails_closed_when_topic_override_empty(monkeypatch, cfg):
    # Explicit override with empty string must still fail closed — never
    # silently send to General chat.
    posted = {"called": False}
    def fake_post(self, url, data=None, **kw):
        posted["called"] = True
        return httpx.Response(200, json={"ok": True},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert notify.send_message("hi", cfg, topic="") is False
    assert posted["called"] is False


def test_send_sleeps_on_failure_to_throttle_429_burst(monkeypatch, cfg):
    # On non-200 (especially 429), the previous shape skipped the sleep and
    # returned False immediately — back-to-back failures hit Telegram with
    # no spacing at all. Sleep belongs in `finally`, so failure paths also
    # observe the per-second rate limit.
    slept = []
    monkeypatch.setattr(notify.time, "sleep", lambda s: slept.append(s))
    def fake_post(self, url, **kw):
        return httpx.Response(429, text="Too Many Requests",
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx.Client, "post", fake_post)
    assert notify.send_message("hi", cfg) is False
    assert slept and slept[0] > 0, "expected throttle sleep on failure path"
