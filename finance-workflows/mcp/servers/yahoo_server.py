"""Yahoo Finance MCP server (yfinance >= 1.3.0).

yfinance 1.3.0 handles curl_cffi internally — no session shim required.
(The previous studio-era compatibility layer was written for yfinance 0.2.51
and started failing once yfinance 1.x landed: yfinance now expects to manage
its own curl_cffi session and rejects custom session adapters with
"Yahoo API requires curl_cffi session not <custom adapter>".)

Tools (never raise; return shaped error dict on failure):
- get_stock_info(ticker) → the raw yfinance Ticker.info dict (rich fields:
  longBusinessSummary, sector, industry, marketCap, currentPrice / regularMarketPrice,
  trailingPE / forwardPE / pegRatio / priceToBook, profitMargins / operatingMargins /
  returnOnEquity, revenueGrowth / earningsGrowth, debtToEquity / freeCashflow /
  totalCash / totalDebt, dividendYield, fiftyTwoWeekHigh / Low …). Adds {ticker, error}
  on failure.
- get_historical_stock_prices(ticker, period, interval) → list of
  {date, open, high, low, close, volume}.
"""
import yfinance as yf
from mcp.server.fastmcp import FastMCP


mcp = FastMCP("yahoo-finance")


@mcp.tool()
def get_stock_info(ticker: str):
    """Return the full Yahoo Finance info dict for a ticker (e.g. 'NVDA',
    '2330.TW', '^SOX'). On failure returns {"ticker": <t>, "error": <msg>}.
    """
    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        return {"ticker": ticker, "error": f"{type(e).__name__}: {e}"}
    if not info:
        return {"ticker": ticker, "error": "empty info dict (likely invalid ticker or upstream block)"}
    return info


@mcp.tool()
def get_historical_stock_prices(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Return historical OHLCV bars as a list of
    {date, open, high, low, close, volume}. On failure returns
    {"ticker": <t>, "error": <msg>}.

    `period`: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max.
    `interval`: 1m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo.
    """
    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception as e:
        return {"ticker": ticker, "error": f"{type(e).__name__}: {e}"}
    if h is None or getattr(h, "empty", True):
        return {"ticker": ticker, "error": "empty history (invalid ticker / range / interval)"}
    out = []
    for idx, row in h.iterrows():
        out.append({
            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]),
        })
    return out


if __name__ == "__main__":
    mcp.run()
