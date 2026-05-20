"""Hermetic tests for edgar_server (HTTP mocked, no live SEC calls)."""
import importlib.util, json, pathlib, types


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "edgar_server.py"
    spec = importlib.util.spec_from_file_location("edgar_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class _R:
    def __init__(self, text=None, payload=None, status=200):
        self._text = text
        self._payload = payload
        self.status_code = status
        self.headers = {}
    @property
    def text(self):
        if self._text is not None: return self._text
        return json.dumps(self._payload)
    def json(self):
        return self._payload if self._payload is not None else json.loads(self._text)


_TICKERS_PAYLOAD = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 1318605, "ticker": "TSLA", "title": "Tesla, Inc."},
    "2": {"cik_str": 1326801, "ticker": "META", "title": "Meta Platforms, Inc."},
}


def _reset_cache(m):
    m._ticker_cache["data"] = None


def _install_http(m, *, get_response=None, get_side_effect=None):
    if get_side_effect:
        m._http_get = lambda url, timeout=30, accept=None: get_side_effect(url)
    else:
        m._http_get = lambda url, timeout=30, accept=None: get_response


# ── edgar_resolve_ticker ──────────────────────────────────────────────────────

def test_resolve_ticker_hit():
    m = _load(); _reset_cache(m)
    _install_http(m, get_response=_R(payload=_TICKERS_PAYLOAD))
    r = m.edgar_resolve_ticker("AAPL")
    assert r == {"ticker": "AAPL", "cik": 320193, "company_name": "Apple Inc."}


def test_resolve_ticker_case_insensitive_and_strip():
    m = _load(); _reset_cache(m)
    _install_http(m, get_response=_R(payload=_TICKERS_PAYLOAD))
    r = m.edgar_resolve_ticker("  aapl  ")
    assert r["cik"] == 320193


def test_resolve_ticker_miss():
    m = _load(); _reset_cache(m)
    _install_http(m, get_response=_R(payload=_TICKERS_PAYLOAD))
    r = m.edgar_resolve_ticker("ZZZZ")
    assert r["ticker"] == "ZZZZ"
    assert "not found" in r["error"]


def test_resolve_ticker_empty():
    m = _load(); _reset_cache(m)
    r = m.edgar_resolve_ticker("")
    assert "empty ticker" in r["error"]


def test_resolve_ticker_network_error():
    m = _load(); _reset_cache(m)
    def boom(url): raise m._EdgarError("HTTP 503 on tickers")
    _install_http(m, get_side_effect=boom)
    r = m.edgar_resolve_ticker("AAPL")
    assert r["ticker"] == "AAPL"
    assert "could not load SEC ticker map" in r["error"]


# ── edgar_latest_annual ───────────────────────────────────────────────────────

def _submissions_payload(forms_dates_accessions_docs):
    forms, dates, accs, docs = zip(*forms_dates_accessions_docs) if forms_dates_accessions_docs else ([], [], [], [])
    return {"cik": "320193", "name": "Apple Inc.",
            "filings": {"recent": {"form": list(forms), "filingDate": list(dates),
                                    "accessionNumber": list(accs),
                                    "primaryDocument": list(docs)}}}


def test_latest_annual_picks_newest_10k():
    m = _load(); _reset_cache(m)
    def route(url):
        if "company_tickers.json" in url: return _R(payload=_TICKERS_PAYLOAD)
        if "submissions" in url:
            return _R(payload=_submissions_payload([
                ("10-Q", "2025-08-01", "0000320193-25-000099", "aapl-q3.htm"),
                ("10-K", "2024-11-01", "0000320193-24-000123", "aapl-10k-fy24.htm"),
                ("10-K", "2023-11-03", "0000320193-23-000106", "aapl-10k-fy23.htm"),
            ]))
        raise AssertionError(f"unexpected url {url}")
    _install_http(m, get_side_effect=route)
    r = m.edgar_latest_annual("AAPL")
    assert r["form_type"] == "10-K"
    assert r["filing_date"] == "2024-11-01"
    assert r["accession"] == "0000320193-24-000123"
    # Verify URL construction: dashes stripped from accession in directory
    assert r["primary_doc_url"] == \
        "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-10k-fy24.htm"
    assert r["company_name"] == "Apple Inc."


def test_latest_annual_accepts_20f_for_foreign():
    """TSM and similar foreign-private-issuers file 20-F, not 10-K."""
    m = _load(); _reset_cache(m)
    def route(url):
        if "company_tickers.json" in url:
            return _R(payload={"0": {"cik_str": 1046179, "ticker": "TSM", "title": "Taiwan Semiconductor Manufacturing Co Ltd"}})
        if "submissions" in url:
            return _R(payload=_submissions_payload([
                ("6-K", "2025-09-01", "0001046179-25-000050", "tsm-6k.htm"),
                ("20-F", "2025-04-15", "0001046179-25-000010", "tsm-20f-fy24.htm"),
            ]))
        raise AssertionError(f"unexpected url {url}")
    _install_http(m, get_side_effect=route)
    r = m.edgar_latest_annual("TSM")
    assert r["form_type"] == "20-F"
    assert "tsm-20f-fy24.htm" in r["primary_doc_url"]


def test_latest_annual_no_annual_filed():
    m = _load(); _reset_cache(m)
    def route(url):
        if "company_tickers.json" in url: return _R(payload=_TICKERS_PAYLOAD)
        if "submissions" in url:
            return _R(payload=_submissions_payload([
                ("10-Q", "2025-08-01", "x", "x.htm"),
                ("8-K", "2025-07-01", "y", "y.htm"),
            ]))
    _install_http(m, get_side_effect=route)
    r = m.edgar_latest_annual("AAPL")
    assert "no 10-K / 20-F / 40-F" in r["error"]


def test_latest_annual_propagates_resolve_failure():
    m = _load(); _reset_cache(m)
    _install_http(m, get_response=_R(payload=_TICKERS_PAYLOAD))
    r = m.edgar_latest_annual("ZZZZ")
    assert "not found" in r["error"]


# ── edgar_fetch_text ──────────────────────────────────────────────────────────

_FAKE_FILING_HTML = """<html><head><title>10-K Test</title>
<style>body { color: red; }</style>
<script>alert('x');</script>
</head><body>
<h1>Item 1. Business</h1>
<p>The Company designs, manufactures, and markets smartphones.</p>
<h2>Item 1A. Risk Factors</h2>
<p>The Company is exposed to significant supply chain concentration risk.</p>
<p>Another paragraph of risk factor commentary follows.</p>
</body></html>"""


def test_fetch_text_basic_extraction():
    m = _load()
    _install_http(m, get_response=_R(text=_FAKE_FILING_HTML))
    r = m.edgar_fetch_text("https://www.sec.gov/Archives/edgar/data/x/y/z.htm", max_chars=50000)
    assert "error" not in r
    assert "Item 1. Business" in r["text"]
    assert "smartphones" in r["text"]
    assert "Risk Factors" in r["text"]
    assert "alert" not in r["text"]  # script stripped
    assert "color: red" not in r["text"]  # style stripped
    assert r["truncated"] is False
    assert r["offset"] == 0
    assert r["end"] == r["full_chars"]


def test_fetch_text_truncation_and_paging():
    m = _load()
    big_html = "<html><body>" + ("<p>Paragraph paragraph paragraph paragraph.</p>" * 200) + "</body></html>"
    _install_http(m, get_response=_R(text=big_html))
    page1 = m.edgar_fetch_text("https://x", max_chars=500, offset=0)
    assert page1["truncated"] is True
    assert page1["end"] > 0
    assert len(page1["text"]) <= 500
    page2 = m.edgar_fetch_text("https://x", max_chars=500, offset=page1["end"])
    assert page2["full_chars"] == page1["full_chars"]
    assert page2["offset"] == page1["end"]


def test_fetch_text_offset_past_end_returns_empty():
    m = _load()
    _install_http(m, get_response=_R(text=_FAKE_FILING_HTML))
    r = m.edgar_fetch_text("https://x", max_chars=50000, offset=999999)
    assert r["text"] == ""
    assert r["truncated"] is False


def test_fetch_text_http_error_returns_shape():
    m = _load()
    def boom(url, timeout=30, accept=None):
        raise m._EdgarError("HTTP 404 on x")
    m._http_get = boom
    r = m.edgar_fetch_text("https://x")
    assert r["text"] == ""
    assert "404" in r["error"]
