"""Yahoo Finance MCP server.

Uses curl_cffi browser-impersonation to bypass Yahoo 429 / crumb-block.
yfinance 0.2.51 passes the session into YfData which calls session.get() for
cookie (https://fc.yahoo.com) and crumb fetching.  Two compatibility layers:

1. Cookie compat: curl_cffi cookies are plain strings in list() but yfinance
   expects objects with .name/.value; _CookieCompat / _ResponseCompat bridge that.

2. UA compat: yfinance hardcodes a Chrome-39 (2014) User-Agent which Yahoo now
   blocks.  _SessionAdapter swaps it for a modern Chrome UA so that cffi
   impersonation and the crumb endpoint agree.
"""
import yfinance as yf
import yfinance.data as _yf_data
from curl_cffi import requests as cffi
from mcp.server.fastmcp import FastMCP

_MODERN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Patch yfinance's class-level UA so every YfData instance uses the modern one
_yf_data.YfData.user_agent_headers = {"User-Agent": _MODERN_UA}


class _CookieCompat:
    """Wraps a (name, value) pair to look like a requests.cookies.Cookie."""
    def __init__(self, name: str, value: str):
        self.name = name
        self.value = value

    def __str__(self):
        return self.value

    def __eq__(self, other):
        return str(self) == str(other)


class _ResponseCompat:
    """Thin wrapper around a curl_cffi Response that replaces .cookies with
    a list-like object whose elements have .name and .value attributes."""

    def __init__(self, resp):
        self._resp = resp
        # Build compat cookie list from the cffi Cookies mapping
        self._compat_cookies = [
            _CookieCompat(k, v)
            for k, v in resp.cookies.items()
        ]

    @property
    def status_code(self):
        return self._resp.status_code

    @property
    def text(self):
        return self._resp.text

    @property
    def cookies(self):
        return self._compat_cookies

    def json(self):
        return self._resp.json()

    @property
    def content(self):
        return self._resp.content

    def raise_for_status(self):
        if self._resp.status_code >= 400:
            from requests.exceptions import HTTPError
            raise HTTPError(
                f"HTTP Error {self._resp.status_code}: ",
                response=self,
            )


class _SessionAdapter:
    """Wraps curl_cffi.Session so that .get() returns _ResponseCompat objects,
    making the cookie interface compatible with what yfinance.data expects.
    Also upgrades the User-Agent header to the modern Chrome string."""

    def __init__(self, session: cffi.Session):
        self._s = session

    def get(self, url, **kwargs):
        # curl_cffi.Session.get doesn't accept 'proxies' — drop it
        kwargs.pop("proxies", None)
        # Upgrade old UA if yfinance passes its stale header dict
        hdrs = kwargs.get("headers") or {}
        ua = hdrs.get("User-Agent", "")
        if not ua or "Chrome/39" in ua:
            kwargs["headers"] = {**hdrs, "User-Agent": _MODERN_UA}
        resp = self._s.get(url, **kwargs)
        return _ResponseCompat(resp)

    # Intentionally no .cache attribute → yfinance._session_is_caching = False


_CFFI_SESSION = cffi.Session(impersonate="chrome")
_SESSION = _SessionAdapter(_CFFI_SESSION)


def _info(raw: dict, ticker: str):
    # yfinance ≥0.2.x may return currentPrice instead of regularMarketPrice
    price = raw.get("regularMarketPrice") or raw.get("currentPrice")
    return {"ticker": ticker,
            "price": price,
            "pe": raw.get("trailingPE"),
            "name": raw.get("shortName")}


def _tk(ticker: str):
    return yf.Ticker(ticker, session=_SESSION)


mcp = FastMCP("yahoo-finance")


@mcp.tool()
def get_stock_info(ticker: str):
    """Current price, P/E, name for a Yahoo ticker (e.g. 2330.TW, MU, ^SOX)."""
    for attempt in (1, 2):
        try:
            return _info(_tk(ticker).info, ticker)
        except Exception as e:
            if attempt == 2:
                return {"ticker": ticker, "error": f"yahoo info failed: {e}"}


@mcp.tool()
def get_historical_stock_prices(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Daily closes (enough bars for 60MA). Returns list of {date, close}."""
    for attempt in (1, 2):
        try:
            h = _tk(ticker).history(period=period, interval=interval)
            return [{"date": str(i.date()), "close": float(c)}
                    for i, c in zip(h.index, h["Close"])]
        except Exception as e:
            if attempt == 2:
                return {"ticker": ticker, "error": f"yahoo history failed: {e}"}


if __name__ == "__main__":
    mcp.run()
