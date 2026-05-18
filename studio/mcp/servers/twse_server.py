"""
TWSE Open API MCP server — 5 tools for Taiwan stock-market data.

Verified endpoints (openapi.twse.com.tw/v1, confirmed 2026-05-18):
  get_daily_market_trading_info  → /exchangeReport/FMTQIK
      keys: Date, TradeVolume, TradeValue, Transaction, TAIEX, Change
  get_market_index_info          → /exchangeReport/MI_INDEX
      keys: 日期, 指數, 收盤指數, 漲跌, 漲跌點數, 漲跌百分比
      (row where 指數=="發行量加權股價指數" = TAIEX; "寶島股價指數" = Formosa/OTC-like)
  get_margin_trading_info        → /exchangeReport/MI_MARGN
      keys: 股票代號, 股票名稱, 融資買進, 融資賣出, 融資今日餘額, 融券今日餘額, etc.
  get_stock_daily_trading(stock_code) → /exchangeReport/STOCK_DAY_ALL
      keys: Date, Code, Name, TradeVolume, TradeValue, OpeningPrice,
            HighestPrice, LowestPrice, ClosingPrice, Change, Transaction
  get_foreign_investment_by_industry → /fund/MI_QFIIS_cat
      keys: IndustryCat, Numbers, ShareNumber, ForeignMainlandAreaShare, Percentage
"""

import requests
from mcp.server.fastmcp import FastMCP

BASE = "https://openapi.twse.com.tw/v1"


def _get(path):
    try:
        r = requests.get(f"{BASE}{path}", timeout=30)
        if r.status_code != 200:
            return {"error": f"twse http {r.status_code} for {path}"}
        return r.json()
    except Exception as e:
        return {"error": f"twse fetch failed: {e}"}


def _row_for(rows, key, value):
    if not isinstance(rows, list):
        return {"error": "unexpected twse payload"}
    for row in rows:
        if str(row.get(key)) == str(value):
            return row
    return {"error": f"stock {value} not found"}


mcp = FastMCP("twse")


@mcp.tool()
def get_daily_market_trading_info():
    """TAIEX level + daily trade value/volume (monthly history, most-recent row = last session).

    Returns list of objects with keys: Date, TradeVolume, TradeValue, Transaction, TAIEX, Change.
    """
    return _get("/exchangeReport/FMTQIK")


@mcp.tool()
def get_market_index_info():
    """All TWSE index levels for the most recent session.

    Returns list of objects with keys: 日期, 指數, 收盤指數, 漲跌, 漲跌點數, 漲跌百分比.
    Rows include 發行量加權股價指數 (TAIEX) and 寶島股價指數 (Formosa index).
    Note: TPEX (OTC) index is not available on this API; closest is 寶島股價指數.
    """
    return _get("/exchangeReport/MI_INDEX")


@mcp.tool()
def get_margin_trading_info():
    """Per-stock margin balance for the most recent session.

    Returns list of objects with keys: 股票代號, 股票名稱, 融資買進, 融資賣出,
    融資今日餘額, 融資限額, 融券買進, 融券賣出, 融券今日餘額, 融券限額, 資券互抵.
    Note: foreign net buy/sell (外資買賣超) is not available on this endpoint;
    this endpoint provides margin lending/shorting balance per stock.
    """
    return _get("/exchangeReport/MI_MARGN")


@mcp.tool()
def get_stock_daily_trading(stock_code: str):
    """Latest daily trading row for one Taiwan stock code (e.g. '2408', '0050').

    Returns a single object with keys: Date, Code, Name, TradeVolume, TradeValue,
    OpeningPrice, HighestPrice, LowestPrice, ClosingPrice, Change, Transaction.
    Returns {"error": "stock <code> not found"} if the code is not in today's data.
    """
    data = _get("/exchangeReport/STOCK_DAY_ALL")
    return _row_for(data, "Code", stock_code)


@mcp.tool()
def get_foreign_investment_by_industry():
    """Foreign + mainland-area shareholding ratio by industry category.

    Returns list of objects with keys: IndustryCat, Numbers (# of stocks),
    ShareNumber (total issued shares), ForeignMainlandAreaShare (foreign-held shares),
    Percentage (foreign ownership %).
    """
    return _get("/fund/MI_QFIIS_cat")


if __name__ == "__main__":
    mcp.run()
