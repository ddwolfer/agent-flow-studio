"""Tests for the Telegram post-run notification. No real HTTP — httpx.Client
is monkeypatched. Verifies: skip when creds absent, posts text + PDF when set,
sends message_thread_id when topic env present, never raises on errors."""
import importlib.util, json, pathlib


def _load():
    p = pathlib.Path(__file__).parents[1] / "scripts" / "notify_telegram.py"
    spec = importlib.util.spec_from_file_location("notify_telegram", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class _FakeResp:
    def __init__(self, status=200, text=""):
        self.status_code = status
        self.text = text


class _FakeClient:
    """Records every POST so tests can assert what would have been sent."""
    posts = []

    def __init__(self, *a, **k): pass
    def __enter__(self): _FakeClient.posts = []; return self
    def __exit__(self, *a): return False
    def post(self, url, data=None, files=None, **k):
        _FakeClient.posts.append({"url": url, "data": dict(data or {}),
                                   "files": bool(files)})
        return _FakeResp(200, "ok")


def _write_history(tmp_path, date, obj):
    p = tmp_path / "_history.jsonl"
    p.write_text(json.dumps({**obj, "date": date}) + "\n", "utf-8")
    return p


def test_skips_when_no_creds(monkeypatch, tmp_path):
    m = _load()
    monkeypatch.setattr(m.httpx, "Client", _FakeClient)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    m.notify("x", "2026-05-24", tmp_path / "r.html", None, "TELEGRAM_TOPIC_X")
    assert _FakeClient.posts == []  # never called


def test_sends_message_and_pdf_with_topic(monkeypatch, tmp_path):
    m = _load()
    monkeypatch.setattr(m.httpx, "Client", _FakeClient)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
    monkeypatch.setenv("TELEGRAM_TOPIC_X", "42")
    html = tmp_path / "r.html"; html.write_text("<p>x</p>", "utf-8")
    (tmp_path / "r.pdf").write_bytes(b"%PDF-1.4 fake")
    hist = _write_history(tmp_path, "2026-05-24", {
        "overall_stance": "Neutral cautious",
        "confidence": 4,
        "top_signals": ["BTC at STH cost basis", {"signal": "ETH weak"}],
        "top_risks": ["Fed rate path"]})
    m.notify("crypto-daily", "2026-05-24", html, hist, "TELEGRAM_TOPIC_X")
    # 2 calls: sendMessage + sendDocument
    assert len(_FakeClient.posts) == 2
    msg, doc = _FakeClient.posts
    assert "sendMessage" in msg["url"]
    assert msg["data"]["chat_id"] == "-1001"
    assert msg["data"]["message_thread_id"] == "42"   # topic threaded
    assert "Neutral cautious" in msg["data"]["text"]
    assert "BTC at STH cost basis" in msg["data"]["text"]
    assert "ETH weak" in msg["data"]["text"]          # dict signal flattened
    assert "Fed rate path" in msg["data"]["text"]
    assert "sendDocument" in doc["url"] and doc["files"]
    assert doc["data"]["message_thread_id"] == "42"


def test_no_topic_env_sends_without_thread_id(monkeypatch, tmp_path):
    m = _load()
    monkeypatch.setattr(m.httpx, "Client", _FakeClient)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
    monkeypatch.delenv("TELEGRAM_TOPIC_Y", raising=False)  # not set
    html = tmp_path / "r.html"; html.write_text("<p>x</p>", "utf-8")
    m.notify("us-macro", "2026-05-24", html, None, "TELEGRAM_TOPIC_Y")
    assert len(_FakeClient.posts) == 1  # message only (no PDF)
    assert "message_thread_id" not in _FakeClient.posts[0]["data"]


def test_swallows_httpx_exceptions(monkeypatch, tmp_path):
    """Telegram failures must never raise — report is already written."""
    m = _load()
    class Boom:
        def __init__(self, *a, **k): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **k): raise RuntimeError("network down")
    monkeypatch.setattr(m.httpx, "Client", Boom)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "BOT")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001")
    html = tmp_path / "r.html"; html.write_text("<p>x</p>", "utf-8")
    # Must not raise
    m.notify("crypto-daily", "2026-05-24", html, None, None)
