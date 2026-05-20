"""web-fetch MCP server — two tools: web_fetch(url) and web_extract_article(url)."""
import httpx
from mcp.server.fastmcp import FastMCP

from readability import Document
from markdownify import markdownify


class _WebError(Exception):
    """Raised by _http_get when the underlying HTTP fetch fails (network error)."""


def _http_get(url: str, timeout: int = 30):
    try:
        return httpx.get(url, timeout=timeout, follow_redirects=True,
                         headers={"User-Agent": "finance-workflows/0.1"})
    except httpx.RequestError as e:
        raise _WebError(str(e))


mcp = FastMCP("web-fetch")


@mcp.tool()
def web_fetch(url: str):
    """Raw HTTP GET. Returns {status, content_type, text}. Never raises;
    on network error returns {status:0, content_type:'', text:<error>}.
    """
    try:
        r = _http_get(url)
    except _WebError as e:
        return {"status": 0, "content_type": "", "text": str(e)}
    return {"status": r.status_code,
            "content_type": r.headers.get("content-type", ""),
            "text": r.text}


@mcp.tool()
def web_extract_article(url: str):
    """Extract a readable article from a URL using readability + markdownify.
    Returns {title, byline, published, text_markdown}. Never raises;
    on failure returns the dict with empty fields.
    """
    try:
        r = _http_get(url)
    except _WebError:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    if r.status_code >= 400:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    try:
        doc = Document(r.text)
        title = (doc.short_title() or "").strip()
        body_html = doc.summary(html_partial=True)
        md = markdownify(body_html, heading_style="ATX").strip()
    except Exception:
        return {"title": "", "byline": "", "published": "", "text_markdown": ""}
    return {"title": title, "byline": "", "published": "", "text_markdown": md}


if __name__ == "__main__":
    mcp.run()
