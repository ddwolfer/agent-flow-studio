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
