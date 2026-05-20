"""RSS MCP server — one tool: rss_fetch(url, max_items=20)."""
import feedparser, httpx
from mcp.server.fastmcp import FastMCP


class _FetchError(Exception):
    """Raised when the underlying HTTP fetch fails (network/HTTP error)."""


def _fetch_bytes(url: str, timeout: int = 30) -> bytes:
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": "finance-workflows/0.1"})
        if r.status_code >= 400:
            raise _FetchError(f"HTTP {r.status_code}")
        return r.content
    except (httpx.RequestError, _FetchError) as e:
        raise _FetchError(str(e))


def _norm_date(entry) -> str:
    if getattr(entry, "published_parsed", None):
        t = entry.published_parsed
        return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"
    return getattr(entry, "published", "") or ""


mcp = FastMCP("rss")


@mcp.tool()
def rss_fetch(url: str, max_items: int = 20):
    """Fetch and parse an RSS/Atom feed. Returns a list of items or [] on failure.

    Each item: {title, link, published (YYYY-MM-DD if parseable), summary}.
    Never raises — returns [] if the URL is unreachable or not a feed.
    """
    try:
        raw = _fetch_bytes(url)
    except _FetchError:
        return []
    parsed = feedparser.parse(raw)
    out = []
    for e in parsed.entries[: max(int(max_items), 1)]:
        out.append({
            "title": getattr(e, "title", "") or "",
            "link": getattr(e, "link", "") or "",
            "published": _norm_date(e),
            "summary": (getattr(e, "summary", "") or "")[:1000],
        })
    return out


if __name__ == "__main__":
    mcp.run()
