import yfinance as yf
from mcp.server.fastmcp import FastMCP

def _info(raw: dict, ticker: str):
    return {"ticker": ticker,
            "price": raw.get("regularMarketPrice"),
            "pe": raw.get("trailingPE"),
            "name": raw.get("shortName")}

mcp = FastMCP("yahoo-finance")

@mcp.tool()
def get_stock_info(ticker: str):
    """Current price, P/E, name for a Yahoo ticker (e.g. 2330.TW, MU, ^SOX)."""
    try:
        return _info(yf.Ticker(ticker).info, ticker)
    except Exception as e:
        return {"ticker": ticker, "error": f"yahoo info failed: {e}"}

@mcp.tool()
def get_historical_stock_prices(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Daily closes (enough bars for 60MA). Returns list of {date, close}."""
    try:
        h = yf.Ticker(ticker).history(period=period, interval=interval)
        return [{"date": str(i.date()), "close": float(c)}
                for i, c in zip(h.index, h["Close"])]
    except Exception as e:
        return {"ticker": ticker, "error": f"yahoo history failed: {e}"}

if __name__ == "__main__":
    mcp.run()
