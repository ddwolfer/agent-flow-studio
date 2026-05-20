"""SEC EDGAR MCP server.

Three tools (never raise; return shaped error dicts on failure):

- edgar_resolve_ticker(ticker)  → {ticker, cik, company_name}
- edgar_latest_annual(ticker)   → {ticker, form_type, filing_date, accession,
                                    company_name, primary_doc_url}
                                  (form_type ∈ 10-K | 20-F | 40-F)
- edgar_fetch_text(url, max_chars=60000, offset=0)
                                → {text, full_chars, offset, end, truncated}

Why this exists: company IR pages (investor.nvidia.com, investor.tsmc.com,
investor.apple.com, …) are JS-rendered SPAs that fail headless readability
extraction (see PHASE2-EVIDENCE for the deep-stock-research run that hit empty
IR pages). SEC filings are plain HTML and the primary source of truth for
Business / Risk Factors / MD&A — much more reliable.

SEC EDGAR access rules: identify yourself in the User-Agent (their guidelines).
We do, with a contact-style UA string. SEC also rate-limits to ~10 req/s; this
server makes one request per tool call so we're well under.
"""
import re as _re
import httpx
from mcp.server.fastmcp import FastMCP
from markdownify import markdownify

# Strip <script>...</script>, <style>...</style>, and HTML comments entirely
# BEFORE markdownify — markdownify's `strip=` only removes the tag, not the
# enclosed text content (so JS code / CSS rules would otherwise leak through).
_NUKE_BLOCKS = _re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>", _re.DOTALL | _re.IGNORECASE)
_NUKE_COMMENTS = _re.compile(r"<!--.*?-->", _re.DOTALL)
_NUKE_HEAD = _re.compile(r"<head\b[^>]*>.*?</head\s*>", _re.DOTALL | _re.IGNORECASE)


# SEC EDGAR access rules REQUIRE the UA in the exact format
# "Sample Company Name AdminContact@samplecompany.com" (name + space + email).
# URL-style UA strings get a 403 from sec.gov (empirically confirmed).
# https://www.sec.gov/os/accessing-edgar-data
_UA = "finance-workflows research admin@finance-workflows.local"
_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_ANNUAL_FORMS = {"10-K", "20-F", "40-F"}


class _EdgarError(Exception):
    """Raised internally by _http_get on network/HTTP errors."""


def _http_get(url: str, timeout: int = 30, accept: str | None = None):
    headers = {"User-Agent": _UA, "Accept-Encoding": "gzip, deflate"}
    if accept:
        headers["Accept"] = accept
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers=headers)
    except httpx.RequestError as e:
        raise _EdgarError(f"network: {e}")
    if r.status_code >= 400:
        raise _EdgarError(f"HTTP {r.status_code} on {url}")
    return r


# In-process cache for the SEC ticker map (~10k entries, ~1MB JSON, stable).
_ticker_cache: dict = {"data": None}


def _ticker_map() -> dict:
    """Return {TICKER_UPPER: {"cik": int, "company_name": str}} from SEC."""
    if _ticker_cache["data"] is not None:
        return _ticker_cache["data"]
    try:
        r = _http_get(_TICKER_MAP_URL, accept="application/json")
    except _EdgarError as e:
        raise _EdgarError(f"could not load SEC ticker map: {e}")
    raw = r.json()
    out = {}
    # The payload is {"0": {cik_str, ticker, title}, "1": {...}, …}
    for entry in raw.values():
        t = (entry.get("ticker") or "").upper()
        if t:
            out[t] = {"cik": int(entry["cik_str"]),
                      "company_name": entry.get("title", "")}
    _ticker_cache["data"] = out
    return out


mcp = FastMCP("edgar")


@mcp.tool()
def edgar_resolve_ticker(ticker: str):
    """Map a stock ticker (e.g. 'AAPL', 'TSM') to its SEC CIK + company name.

    Returns {"ticker", "cik", "company_name"} on success.
    On failure: {"ticker", "error"}.
    """
    t = (ticker or "").strip().upper()
    if not t:
        return {"ticker": ticker, "error": "empty ticker"}
    try:
        m = _ticker_map()
    except _EdgarError as e:
        return {"ticker": t, "error": f"could not load SEC ticker map: {e}"}
    if t not in m:
        return {"ticker": t, "error": f"ticker {t} not found in SEC ticker map"}
    info = m[t]
    return {"ticker": t, "cik": info["cik"], "company_name": info["company_name"]}


@mcp.tool()
def edgar_latest_annual(ticker: str):
    """Find the most-recent annual filing (10-K / 20-F / 40-F) for a ticker.

    Returns {"ticker", "form_type", "filing_date", "accession", "company_name",
    "primary_doc_url"} on success. On failure: {"ticker", "error"}.
    """
    resolved = edgar_resolve_ticker(ticker)
    if "error" in resolved:
        return resolved
    cik = resolved["cik"]
    company = resolved["company_name"]
    t = resolved["ticker"]
    sub_url = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
    try:
        r = _http_get(sub_url, accept="application/json")
    except _EdgarError as e:
        return {"ticker": t, "error": f"submissions fetch failed: {e}"}
    try:
        payload = r.json()
        recent = payload["filings"]["recent"]
        forms = recent["form"]
        dates = recent["filingDate"]
        accs = recent["accessionNumber"]
        docs = recent["primaryDocument"]
    except (KeyError, ValueError) as e:
        return {"ticker": t, "error": f"unexpected submissions payload: {e}"}
    # Scan in order — SEC returns most-recent first
    for form, date, acc, doc in zip(forms, dates, accs, docs):
        if form in _ANNUAL_FORMS:
            acc_nodash = acc.replace("-", "")
            url = (f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_nodash}/{doc}")
            return {"ticker": t, "form_type": form, "filing_date": date,
                    "accession": acc, "company_name": company,
                    "primary_doc_url": url}
    return {"ticker": t,
            "error": f"no 10-K / 20-F / 40-F found in recent filings for {t}"}


@mcp.tool()
def edgar_fetch_text(url: str, max_chars: int = 60000, offset: int = 0):
    """Fetch an SEC filing primary document and return its plain text content.

    HTML/CSS/JS are stripped via markdownify (the same library web-fetch uses).
    The returned text is sliced [offset:offset+max_chars]; total length is
    reported via full_chars + a `truncated` flag. To page through a long filing,
    re-call with offset=<previous end>.

    On failure: {"url", "text": "", "error"}.
    """
    try:
        r = _http_get(url)
    except _EdgarError as e:
        return {"url": url, "text": "", "error": str(e)}
    try:
        html = r.text
        html = _NUKE_HEAD.sub("", html)
        html = _NUKE_BLOCKS.sub("", html)
        html = _NUKE_COMMENTS.sub("", html)
        md = markdownify(html, heading_style="ATX")
        # Compact: collapse runs of 3+ newlines to 2
        md = _re.sub(r"\n{3,}", "\n\n", md).strip()
    except Exception as e:
        return {"url": url, "text": "", "error": f"extract failed: {type(e).__name__}: {e}"}
    full = len(md)
    o = max(int(offset), 0)
    n = max(int(max_chars), 1)
    end = min(o + n, full)
    slice_ = md[o:end] if o < full else ""
    return {"url": url, "text": slice_, "full_chars": full,
            "offset": o, "end": end if slice_ else o,
            "truncated": end < full}


if __name__ == "__main__":
    mcp.run()
