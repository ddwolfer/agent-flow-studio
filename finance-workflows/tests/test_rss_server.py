import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "rss_server.py"
    spec = importlib.util.spec_from_file_location("rss_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_FAKE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Demo</title>
  <item>
    <title>First post</title>
    <link>https://example.com/1</link>
    <pubDate>Mon, 21 May 2026 09:00:00 +0000</pubDate>
    <description>One liner.</description>
  </item>
  <item>
    <title>Second post</title>
    <link>https://example.com/2</link>
    <pubDate>Mon, 21 May 2026 08:00:00 +0000</pubDate>
    <description>Another.</description>
  </item>
</channel></rss>"""

def test_rss_fetch_parses_items(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_fetch_bytes", lambda url, timeout=30: _FAKE_RSS.encode("utf-8"))
    out = m.rss_fetch("https://example.com/feed", max_items=10)
    assert len(out) == 2
    assert out[0]["title"] == "First post"
    assert out[0]["link"] == "https://example.com/1"
    assert "2026-05-21" in out[0]["published"]
    assert out[0]["summary"].startswith("One liner")

def test_rss_fetch_caps_max_items(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_fetch_bytes", lambda url, timeout=30: _FAKE_RSS.encode("utf-8"))
    out = m.rss_fetch("https://example.com/feed", max_items=1)
    assert len(out) == 1

def test_rss_fetch_returns_empty_on_404(monkeypatch):
    m = _load()
    def raise_404(url, timeout=30):
        raise m._FetchError("404 not found")
    monkeypatch.setattr(m, "_fetch_bytes", raise_404)
    out = m.rss_fetch("https://example.com/missing")
    assert out == []
