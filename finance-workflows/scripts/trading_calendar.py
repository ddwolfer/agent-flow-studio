"""交易日曆 — 市場是否開市、市場時區的「今天」、盤別推斷。

為什麼需要:在此之前系統只有「週一到週五」這個近似,於是
  - 美股假日(勞動節、感恩節…)照樣去抓 QQQ,拿到的是前一交易日的舊資料
    卻當成當日,§8 的敘述會建立在錯誤的「今天」上;
  - daily_heartbeat 在美股休市日會誤報 us-macro 缺報告;
  - 「現在美股開盤了嗎」只能靠人肉判斷。
2026-09-07 就是活例子:美股休市、台股開市 —— 週一到五的近似兩邊都會錯。

設計取自 daily_stock_analysis/src/core/trading_calendar.py 的兩個要點:
  1. **按市場時區取「今天」**,不要用伺服器本地日期(UTC 伺服器會差一天)
  2. **fail-open**:exchange-calendars 沒裝或查詢失敗時回 None(未知),
     呼叫端一律當成「照跑」。日曆是精準化工具,不該變成新的故障點。

加密貨幣沒有休市概念,一律視為開市。

用法:
    from trading_calendar import is_market_open, market_today, market_phase
    if is_market_open("us") is False:      # 注意:None(未知)不等於 False
        skip_qqq()
"""
from __future__ import annotations

import datetime as _dt
import logging
from enum import Enum
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

try:
    import exchange_calendars as _xcals
    _XCALS_AVAILABLE = True
except ImportError:                                          # pragma: no cover
    _XCALS_AVAILABLE = False
    logger.warning("exchange-calendars 未安裝,交易日檢查停用(fail-open)")

# 我們實際用到的市場。crypto 沒有日曆(24/7)。
MARKET_EXCHANGE = {"us": "XNYS", "tw": "XTAI"}
MARKET_TIMEZONE = {
    "us": "America/New_York",
    "tw": "Asia/Taipei",
    "crypto": "UTC",
}
CRYPTO_MARKETS = {"crypto"}

# 我們追蹤的標的 → 市場。QQQ 是美股 ETF;BTC/ETH 是 24/7。
SYMBOL_MARKET = {
    "QQQ": "us",
    "BTC-USD": "crypto", "ETH-USD": "crypto",
    "BTCUSDT": "crypto", "ETHUSDT": "crypto",
}


class MarketPhase(str, Enum):
    PREMARKET = "premarket"
    INTRADAY = "intraday"
    POSTMARKET = "postmarket"
    CLOSED = "closed"          # 非交易日
    ALWAYS_OPEN = "always_open"   # crypto
    UNKNOWN = "unknown"        # 日曆不可用 → fail-open


def market_for_symbol(symbol: str) -> str | None:
    """標的 → 市場代碼。未知標的回 None(呼叫端 fail-open)。"""
    return SYMBOL_MARKET.get(str(symbol).strip().upper())


def market_today(market: str) -> _dt.date:
    """該市場所在時區的「今天」。

    伺服器時區不等於市場時區:台北凌晨 01:00 時,紐約還在前一天下午。
    用本地日期去查美股日曆會系統性地差一天。
    """
    tz = MARKET_TIMEZONE.get(market, "UTC")
    return _dt.datetime.now(ZoneInfo(tz)).date()


def is_market_open(market: str, check_date: _dt.date | None = None) -> bool | None:
    """該市場當日是否開市。

    回傳 True/False,或 **None 表示「不知道」**(日曆不可用、市場未知)。
    呼叫端必須把 None 當成「照跑」——
        if is_market_open("us") is False: skip()
    寫成 `if not is_market_open(...)` 會把未知也擋掉,那就違背 fail-open。
    """
    if market in CRYPTO_MARKETS:
        return True
    code = MARKET_EXCHANGE.get(market)
    if not code or not _XCALS_AVAILABLE:
        return None
    day = check_date or market_today(market)
    try:
        return bool(_xcals.get_calendar(code).is_session(day))
    except Exception as e:                                   # pragma: no cover
        logger.warning("交易日查詢失敗(fail-open):%s", e)
        return None


def market_phase(market: str, now: _dt.datetime | None = None) -> MarketPhase:
    """盤前 / 盤中 / 盤後 / 休市。

    只看 regular session(不含美股 pre/after-hours),因為我們的資料源
    (yfinance 日線、compute_zones)本來就以正規盤為準。
    """
    if market in CRYPTO_MARKETS:
        return MarketPhase.ALWAYS_OPEN
    code = MARKET_EXCHANGE.get(market)
    if not code or not _XCALS_AVAILABLE:
        return MarketPhase.UNKNOWN

    tz = ZoneInfo(MARKET_TIMEZONE.get(market, "UTC"))
    now = now.astimezone(tz) if now else _dt.datetime.now(tz)
    day = now.date()
    if is_market_open(market, day) is not True:
        return MarketPhase.CLOSED
    try:
        cal = _xcals.get_calendar(code)
        open_utc = cal.session_open(day)
        close_utc = cal.session_close(day)
    except Exception as e:                                   # pragma: no cover
        logger.warning("盤別推斷失敗(fail-open):%s", e)
        return MarketPhase.UNKNOWN

    open_local = open_utc.tz_convert(tz).to_pydatetime()
    close_local = close_utc.tz_convert(tz).to_pydatetime()
    if now < open_local:
        return MarketPhase.PREMARKET
    if now >= close_local:
        return MarketPhase.POSTMARKET
    return MarketPhase.INTRADAY


def should_fetch(symbol: str, check_date: _dt.date | None = None) -> bool:
    """今天值不值得為這個標的抓資料。

    只有在「明確知道休市」時才回 False。未知一律 True —— 少抓一次的代價
    (報告缺一段)遠大於多抓一次(拿到與昨天相同的日線)。
    """
    market = market_for_symbol(symbol)
    if market is None:
        return True
    return is_market_open(market, check_date) is not False


def describe(market: str) -> str:
    """人類可讀的一行摘要,給日誌和報告用。"""
    open_state = is_market_open(market)
    phase = market_phase(market)
    if open_state is None:
        return f"{market}: 交易日未知(日曆不可用,照跑)"
    if market in CRYPTO_MARKETS:
        return f"{market}: 24/7 開市"
    return f"{market}: {'開市' if open_state else '休市'} · {phase.value}"
