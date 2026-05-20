"""Hermetic tests for the rewritten yahoo_server (yfinance>=1.3.0, no shim).

Network-mocked: we monkeypatch yf.Ticker so the tests don't hit Yahoo. Tests
verify the never-raises contract and the shape of returned dicts / lists."""
import importlib.util, pathlib, types


def _load():
    p = pathlib.Path(__file__).parents[1] / "mcp" / "servers" / "yahoo_server.py"
    spec = importlib.util.spec_from_file_location("yahoo_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


class _FakeHistory:
    def __init__(self, rows):
        self._rows = rows
        self.empty = len(rows) == 0
    def __len__(self): return len(self._rows)
    def iterrows(self):
        return iter(self._rows)


class _DT:
    def __init__(self, s): self._s = s
    def date(self): return self
    def __str__(self): return self._s


class _FakeTicker:
    info_to_return = None
    history_to_return = None
    raise_with = None
    def __init__(self, ticker): self._t = ticker
    @property
    def info(self):
        if _FakeTicker.raise_with is not None:
            raise _FakeTicker.raise_with
        return _FakeTicker.info_to_return
    def history(self, period="6mo", interval="1d"):
        if _FakeTicker.raise_with is not None:
            raise _FakeTicker.raise_with
        return _FakeTicker.history_to_return


def _install(m, info=None, history=None, exc=None):
    _FakeTicker.info_to_return = info
    _FakeTicker.history_to_return = history
    _FakeTicker.raise_with = exc
    m.yf = types.SimpleNamespace(Ticker=_FakeTicker)


# ── get_stock_info ────────────────────────────────────────────────────────────

def test_get_stock_info_returns_raw_dict():
    m = _load()
    _install(m, info={"shortName": "NVDA", "marketCap": 3.2e12,
                      "trailingPE": 75.2, "sector": "Technology"})
    out = m.get_stock_info("NVDA")
    assert out["shortName"] == "NVDA"
    assert out["marketCap"] == 3.2e12
    assert out["sector"] == "Technology"


def test_get_stock_info_empty_treated_as_failure():
    m = _load()
    _install(m, info={})
    out = m.get_stock_info("ZZZZ")
    assert out["ticker"] == "ZZZZ"
    assert "empty info dict" in out["error"]


def test_get_stock_info_exception_caught():
    m = _load()
    _install(m, exc=RuntimeError("Yahoo throttled"))
    out = m.get_stock_info("NVDA")
    assert out["ticker"] == "NVDA"
    assert "RuntimeError" in out["error"]
    assert "Yahoo throttled" in out["error"]


# ── get_historical_stock_prices ───────────────────────────────────────────────

def _row(o, h, l, c, v):
    return {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v}


def test_history_returns_bars():
    m = _load()
    rows = [
        (_DT("2026-05-19"), _row(100.0, 105.0, 99.5, 104.0, 1_000_000)),
        (_DT("2026-05-20"), _row(104.0, 108.0, 103.0, 107.5, 1_200_000)),
    ]
    _install(m, history=_FakeHistory(rows))
    out = m.get_historical_stock_prices("NVDA", period="5d")
    assert isinstance(out, list) and len(out) == 2
    assert out[0] == {"date": "2026-05-19", "open": 100.0, "high": 105.0,
                       "low": 99.5, "close": 104.0, "volume": 1_000_000}
    assert out[1]["close"] == 107.5


def test_history_empty_returns_error_dict():
    m = _load()
    _install(m, history=_FakeHistory([]))
    out = m.get_historical_stock_prices("ZZZZ")
    assert isinstance(out, dict)
    assert "empty history" in out["error"]


def test_history_exception_caught():
    m = _load()
    _install(m, exc=ConnectionError("dns fail"))
    out = m.get_historical_stock_prices("NVDA")
    assert isinstance(out, dict)
    assert "dns fail" in out["error"]
    assert "ConnectionError" in out["error"]
