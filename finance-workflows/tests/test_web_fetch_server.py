import importlib.util, pathlib

def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "web_fetch_server.py"
    spec = importlib.util.spec_from_file_location("web_fetch_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

_HTML = """<!doctype html><html><head><title>Hello Title</title>
<meta name="author" content="Jane Doe">
</head><body>
<header>nav stuff</header>
<article><h1>Hello Title</h1>
<p>First paragraph of the real article body. Has enough words to be picked up.</p>
<p>Second paragraph with more content for the readability extractor to like.</p>
</article>
<footer>cookie banner</footer>
</body></html>"""

class _R:
    def __init__(self, text, status=200, ct="text/html"):
        self.text = text; self.status_code = status
        self.headers = {"content-type": ct}; self.content = text.encode()

def test_web_fetch_returns_status_and_text(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R(_HTML))
    r = m.web_fetch("https://example.com/article")
    assert r["status"] == 200
    assert "Hello Title" in r["text"]
    assert r["content_type"].startswith("text/html")

def test_web_fetch_non_200_still_returns_shape(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R("nope", status=404, ct="text/plain"))
    r = m.web_fetch("https://example.com/missing")
    assert r["status"] == 404
    assert r["text"] == "nope"

def test_web_extract_article_strips_chrome(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "_http_get", lambda url, timeout=30: _R(_HTML))
    r = m.web_extract_article("https://example.com/article")
    assert r["title"] == "Hello Title"
    md = r["text_markdown"]
    assert "First paragraph of the real article body" in md
    assert "nav stuff" not in md
    assert "cookie banner" not in md

def test_web_fetch_network_error_returns_status_0(monkeypatch):
    m = _load()
    def boom(url, timeout=30):
        raise m._WebError("connection refused")
    monkeypatch.setattr(m, "_http_get", boom)
    r = m.web_fetch("https://no-such-host.invalid")
    assert r["status"] == 0
    assert "connection refused" in r["text"]
