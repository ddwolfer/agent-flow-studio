# agent-flow-studio Phase 2 — Live Data Wiring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a real, local Eason report producible by building the 5 data MCP servers + a local `gemma4:e4b` subtitle fallback, and closing the known deterministic gaps.

**Architecture:** 5 Python MCP servers (one `studio/mcp/.venv`, FastMCP/stdio) exposing the exact 13 tool ids the inherited skill calls; a TS `mcpConfig.ts` renders a gitignored `mcp.json` (FRED key injected only into the fred server); `runClaude` gains `--mcp-config`/strict/allowed-tools; `buildPrompt` substitutes `${HTML_FILE}/${DATE}/${LOG_FILE}` + bundled CSS; `runPipeline` runs `mechanicalChecks` as advisory and resolves the Chrome path.

**Tech Stack:** Python 3 + `mcp` (FastMCP) + `yt-dlp` + `yfinance` + `requests` + `ollama`; TypeScript + Vitest (existing studio toolchain); local Ollama `gemma4:e4b`.

**Spec:** `docs/superpowers/specs/2026-05-18-agent-flow-studio-live-data-design.md`. **Base:** HEAD `064ec60`, studio vitest 26/26 green.

---

## File Structure

| Path | Responsibility |
|---|---|
| `studio/mcp/requirements.txt` | Python deps for all 5 servers |
| `studio/mcp/.gitignore` | ignore `.venv/`, `mcp.json`, `__pycache__/`, `*.wav` |
| `studio/mcp/mcp.json.tmpl` | registry template with `@PY@`/`@FREDKEY@`/`@DBPATH@`/`@MCPDIR@` tokens |
| `studio/mcp/servers/sqlite_server.py` | `query`/`create_record`/`update_records` + schema auto-init |
| `studio/mcp/servers/fred_server.py` | `fred_get_series` (key from env) |
| `studio/mcp/servers/twse_server.py` | 5 TWSE tools |
| `studio/mcp/servers/yahoo_server.py` | `get_stock_info`/`get_historical_stock_prices` |
| `studio/mcp/servers/ytdlp_server.py` | `ytdlp_search_videos`/`ytdlp_download_transcript` |
| `studio/mcp/lib/gemma_transcribe.py` | audio → chunk → gemma4:e4b → stitched text |
| `studio/mcp/tests/` | pytest unit + recorded real-smoke scripts |
| `studio/lib/runner/mcpConfig.ts` | render `mcp.json`, read FRED key from inherited `.env` |
| `studio/lib/runner/runClaude.ts` | (modify) add mcp-config/strict/allowed-tools args |
| `studio/lib/runner/buildPrompt.ts` | (modify) `${HTML_FILE}/${DATE}/${LOG_FILE}` + `{{report_css}}` |
| `studio/lib/runner/postProcess.ts` | (modify) resolve chrome binary |
| `studio/lib/runner/paths.ts` | (modify) module-relative `STUDIO_ROOT` |
| `studio/lib/runner/runPipeline.ts` | (modify) wire `mechanicalChecks`, pass mcpConfig + logPath/dateIso |
| `studio/prompts/eason/report.css` | bundled CSS from inherited sample |
| `studio/prompts/eason/main.md`, `picks.md` | (modify) placeholder fixes |

**Conventions for every task:** work on `main`; each task = its own `git add <exact paths>` + commit + `git push origin main` (never `-A`, never amend pushed commits, never `--no-verify`; do not stage `studio/package-lock.json`, `studio/mcp/.venv`, or `mcp.json`). Python commands use the venv python `studio/mcp/.venv/bin/python`. After each push the KG-reminder hook fires — record the slice to the knowledge graph.

---

## Task 1: Python MCP scaffold

**Files:**
- Create: `studio/mcp/requirements.txt`, `studio/mcp/.gitignore`, `studio/mcp/mcp.json.tmpl`, `studio/mcp/servers/__init__.py`, `studio/mcp/lib/__init__.py`

- [ ] **Step 1: Create `studio/mcp/requirements.txt`**

```
mcp==1.2.0
yt-dlp==2026.3.17
yfinance==0.2.51
requests==2.32.3
ollama==0.4.4
pytest==8.3.4
```

- [ ] **Step 2: Create `studio/mcp/.gitignore`**

```
.venv/
__pycache__/
*.pyc
mcp.json
*.wav
*.m4a
```

- [ ] **Step 3: Create `studio/mcp/mcp.json.tmpl`**

```json
{
  "mcpServers": {
    "yt-dlp":        { "command": "@PY@", "args": ["@MCPDIR@/servers/ytdlp_server.py"] },
    "twse":          { "command": "@PY@", "args": ["@MCPDIR@/servers/twse_server.py"] },
    "yahoo-finance": { "command": "@PY@", "args": ["@MCPDIR@/servers/yahoo_server.py"] },
    "fred":          { "command": "@PY@", "args": ["@MCPDIR@/servers/fred_server.py"], "env": { "FRED_API_KEY": "@FREDKEY@" } },
    "sqlite":        { "command": "@PY@", "args": ["@MCPDIR@/servers/sqlite_server.py"], "env": { "STUDIO_DB_PATH": "@DBPATH@" } }
  }
}
```

- [ ] **Step 4: Create the two empty package markers**

`studio/mcp/servers/__init__.py` and `studio/mcp/lib/__init__.py` — each an empty file (touch).

- [ ] **Step 5: Create venv and install**

Run:
```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import mcp, yt_dlp, yfinance, requests, ollama; print('deps OK')"
```
Expected: `deps OK`. If a pinned version is unresolvable, relax that single line to the nearest installable version and record the resolved version in the commit message (do not change other pins).

- [ ] **Step 6: Commit**

```bash
git add studio/mcp/requirements.txt studio/mcp/.gitignore studio/mcp/mcp.json.tmpl studio/mcp/servers/__init__.py studio/mcp/lib/__init__.py
git commit -m "chore(mcp): python scaffold + venv deps + mcp.json template"
git push origin main
```

---

## Task 2: sqlite MCP server

**Files:**
- Create: `studio/mcp/servers/sqlite_server.py`
- Test: `studio/mcp/tests/test_sqlite_server.py`

- [ ] **Step 1: Write the failing test**

```python
# studio/mcp/tests/test_sqlite_server.py
import os, sqlite3, tempfile, importlib.util, pathlib

def _load(db):
    os.environ["STUDIO_DB_PATH"] = db
    p = pathlib.Path(__file__).parents[1] / "servers" / "sqlite_server.py"
    spec = importlib.util.spec_from_file_location("sqlite_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def test_query_create_update_roundtrip(tmp_path):
    db = str(tmp_path / "f.db")
    m = _load(db)
    m._ensure_schema()  # creates eason_* tables if absent
    m._create_record("eason_picks", {"ticker": "2330", "pick_date": "2026-05-18", "status": "active"})
    rows = m._query("SELECT ticker,status FROM eason_picks WHERE pick_date=?", ["2026-05-18"])
    assert rows == [{"ticker": "2330", "status": "active"}]
    m._update_records("eason_picks", {"status": "closed"}, {"ticker": "2330"})
    rows = m._query("SELECT status FROM eason_picks WHERE ticker=?", ["2330"])
    assert rows == [{"status": "closed"}]

def test_schema_autoinit_creates_three_tables(tmp_path):
    db = str(tmp_path / "g.db")
    m = _load(db); m._ensure_schema()
    con = sqlite3.connect(db)
    names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"eason_training", "eason_daily", "eason_picks"}.issubset(names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_sqlite_server.py -q`
Expected: FAIL — `sqlite_server.py` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/mcp/servers/sqlite_server.py
import os, sqlite3, pathlib
from mcp.server.fastmcp import FastMCP

DB = os.environ.get("STUDIO_DB_PATH", "")
SCHEMA = pathlib.Path(__file__).parents[3] / "financial-report-system" / "db" / "schema.sql"

def _conn():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def _ensure_schema():
    pathlib.Path(DB).parent.mkdir(parents=True, exist_ok=True)
    con = _conn()
    have = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {"eason_training", "eason_daily", "eason_picks"}.issubset(have) and SCHEMA.exists():
        con.executescript(SCHEMA.read_text())
        con.commit()
    con.close()

def _query(sql, params=None):
    con = _conn()
    cur = con.execute(sql, params or [])
    if cur.description:
        out = [dict(r) for r in cur.fetchall()]
    else:
        con.commit(); out = {"rowcount": cur.rowcount}
    con.close()
    return out

def _create_record(table, values: dict):
    cols = ",".join(values.keys())
    ph = ",".join("?" for _ in values)
    con = _conn()
    cur = con.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", list(values.values()))
    con.commit(); rid = cur.lastrowid; con.close()
    return {"inserted_id": rid}

def _update_records(table, values: dict, where: dict):
    setc = ",".join(f"{k}=?" for k in values)
    wherec = " AND ".join(f"{k}=?" for k in where)
    con = _conn()
    cur = con.execute(f"UPDATE {table} SET {setc} WHERE {wherec}",
                      list(values.values()) + list(where.values()))
    con.commit(); n = cur.rowcount; con.close()
    return {"updated": n}

mcp = FastMCP("sqlite")

@mcp.tool()
def query(sql: str, params: list | None = None):
    """Run any SQL. SELECT returns rows (list of dict); else returns {rowcount}."""
    _ensure_schema(); return _query(sql, params)

@mcp.tool()
def create_record(table: str, values: dict):
    """INSERT one record (dict of column->value) into table."""
    _ensure_schema(); return _create_record(table, values)

@mcp.tool()
def update_records(table: str, values: dict, where: dict):
    """UPDATE rows in table; set `values` where all `where` equalities match."""
    _ensure_schema(); return _update_records(table, values, where)

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_sqlite_server.py -q`
Expected: PASS (2 tests). If schema.sql column names differ from the test's (`ticker`,`pick_date`,`status`), adjust ONLY the test's column names to match the real `financial-report-system/db/schema.sql` `eason_picks` definition (read it first); do not alter schema.sql.

- [ ] **Step 5: Commit**

```bash
git add studio/mcp/servers/sqlite_server.py studio/mcp/tests/test_sqlite_server.py
git commit -m "feat(mcp): sqlite server (query/create_record/update_records + schema autoinit)"
git push origin main
```

---

## Task 3: fred MCP server

**Files:**
- Create: `studio/mcp/servers/fred_server.py`
- Test: `studio/mcp/tests/test_fred_server.py`

- [ ] **Step 1: Write the failing test (offline unit on the parse helper)**

```python
# studio/mcp/tests/test_fred_server.py
import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "fred_server.py"
    spec = importlib.util.spec_from_file_location("fred_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_pick_latest_and_prev():
    m = _load()
    obs = {"observations": [
        {"date": "2026-03-01", "value": "4.1"},
        {"date": "2026-04-01", "value": "4.3"},
        {"date": "2026-05-01", "value": "."},   # FRED missing-value marker
    ]}
    assert m._latest(obs) == {"date": "2026-04-01", "value": 4.3,
                              "prev_date": "2026-03-01", "prev_value": 4.1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_fred_server.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/mcp/servers/fred_server.py
import os, requests
from mcp.server.fastmcp import FastMCP

API = "https://api.stlouisfed.org/fred/series/observations"

def _latest(payload: dict):
    valid = [o for o in payload.get("observations", []) if o.get("value") not in (".", None, "")]
    if not valid:
        return {"error": "no valid observations"}
    last = valid[-1]
    prev = valid[-2] if len(valid) > 1 else {}
    return {"date": last["date"], "value": float(last["value"]),
            "prev_date": prev.get("date"),
            "prev_value": float(prev["value"]) if prev else None}

mcp = FastMCP("fred")

@mcp.tool()
def fred_get_series(series_id: str):
    """Latest + previous value for a FRED series (e.g. FEDFUNDS, CPIAUCSL, T10Y2Y)."""
    key = os.environ.get("FRED_API_KEY", "")
    if not key:
        return {"error": "FRED_API_KEY not set"}
    r = requests.get(API, params={"series_id": series_id, "api_key": key,
                                  "file_type": "json", "sort_order": "asc"}, timeout=30)
    if r.status_code != 200:
        return {"error": f"fred http {r.status_code}"}
    return {"series_id": series_id, **_latest(r.json())}

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run unit test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_fred_server.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Real smoke (records evidence — uses the inherited key)**

Run:
```bash
FRED_API_KEY=$(grep '^FRED_API_KEY=' /Users/pochenkuo/AI/new_financial-report-system/financial-report-system/scripts/.env | cut -d= -f2-) \
/Users/pochenkuo/AI/new_financial-report-system/studio/mcp/.venv/bin/python -c \
"import os,sys; sys.path.insert(0,'/Users/pochenkuo/AI/new_financial-report-system/studio/mcp/servers'); import fred_server as f; print(f.fred_get_series('T10Y2Y'))"
```
Expected: a dict with numeric `value` + `prev_value` for `T10Y2Y` (no `error`). Paste the exact output into the commit message. Do NOT print the key.

- [ ] **Step 6: Commit**

```bash
git add studio/mcp/servers/fred_server.py studio/mcp/tests/test_fred_server.py
git commit -m "feat(mcp): fred server (fred_get_series) + real T10Y2Y smoke"
git push origin main
```

---

## Task 4: twse MCP server

**Files:**
- Create: `studio/mcp/servers/twse_server.py`
- Test: `studio/mcp/tests/test_twse_server.py`

- [ ] **Step 1: Pin the real endpoints (discovery — required, not a placeholder)**

The TWSE Open API base is `https://openapi.twse.com.tw/v1`. Its exact endpoint paths/JSON keys must be confirmed against the live API, not memorised. Run:
```bash
curl -s https://openapi.twse.com.tw/v1/exchangeReport/MI_INDEX | head -c 600; echo
curl -s https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK | head -c 600; echo
curl -s https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN | head -c 600; echo
curl -s https://openapi.twse.com.tw/v1/fund/T86 | head -c 600; echo
curl -s "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL" | head -c 600; echo
```
Record in the commit message, for each of the 5 tools, the chosen endpoint path and the exact JSON keys used. If an endpoint 404s, find the correct one in the swagger at `https://openapi.twse.com.tw/` and record it. The 5 tools and what each must return (fields the inherited prompt consumes — see spec §1):
- `get_daily_market_trading_info` → TAIEX index level, daily trade volume, foreign net short
- `get_market_index_info` → OTC/TPEX index level
- `get_margin_trading_info` → foreign net buy/sell, margin balance
- `get_stock_daily_trading(stock_code)` → that stock's latest close/volume
- `get_foreign_investment_by_industry` → foreign net buy/sell by industry

- [ ] **Step 2: Write the failing test (offline — on the pure shape mapper)**

```python
# studio/mcp/tests/test_twse_server.py
import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "twse_server.py"
    spec = importlib.util.spec_from_file_location("twse_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_pick_row_for_stock():
    m = _load()
    rows = [{"Code": "2317", "ClosingPrice": "100.0", "TradeVolume": "1000"},
            {"Code": "2408", "ClosingPrice": "55.5",  "TradeVolume": "2000"}]
    assert m._row_for(rows, "Code", "2408") == {"Code": "2408", "ClosingPrice": "55.5", "TradeVolume": "2000"}
    assert m._row_for(rows, "Code", "9999") == {"error": "stock 9999 not found"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_twse_server.py -q`
Expected: FAIL — module missing.

- [ ] **Step 4: Write implementation (fill endpoint paths/keys from Step 1)**

```python
# studio/mcp/servers/twse_server.py
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
    for row in rows:
        if str(row.get(key)) == str(value):
            return row
    return {"error": f"stock {value} not found"}

mcp = FastMCP("twse")

# NOTE: endpoint paths below are the Step-1-verified values; the engineer
# replaces each "<PATH from Step 1>" with the confirmed path before running
# the smoke, and records the mapping in the commit message.
@mcp.tool()
def get_daily_market_trading_info():
    """TAIEX level + daily volume + foreign net short."""
    return _get("<PATH from Step 1: market index/volume>")

@mcp.tool()
def get_market_index_info():
    """OTC / TPEX index level."""
    return _get("<PATH from Step 1: OTC index>")

@mcp.tool()
def get_margin_trading_info():
    """Foreign net buy/sell + margin balance."""
    return _get("<PATH from Step 1: margin>")

@mcp.tool()
def get_stock_daily_trading(stock_code: str):
    """Latest daily trading row for one Taiwan stock code."""
    data = _get("<PATH from Step 1: per-stock daily>")
    if isinstance(data, dict) and data.get("error"):
        return data
    return _row_for(data, "<code key from Step 1>", stock_code)

@mcp.tool()
def get_foreign_investment_by_industry():
    """Foreign net buy/sell by industry."""
    return _get("<PATH from Step 1: foreign by industry>")

if __name__ == "__main__":
    mcp.run()
```

> The four `<PATH from Step 1: ...>` and `<code key from Step 1>` strings are NOT placeholders left for "later" — they are filled in THIS step from the Step-1 discovery output before proceeding. The plan cannot hardcode them because TWSE's live paths must be verified, not assumed. Filling them is part of Step 4.

- [ ] **Step 5: Run unit test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_twse_server.py -q`
Expected: PASS (1 test — the pure `_row_for` mapper, independent of network).

- [ ] **Step 6: Real smoke (records evidence)**

Run:
```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp
.venv/bin/python -c "import sys; sys.path.insert(0,'servers'); import twse_server as t; \
print('mkt', str(t.get_daily_market_trading_info())[:200]); \
print('2408', t.get_stock_daily_trading('2408'))"
```
Expected: non-error data for the market call and for stock `2408`. Paste output (truncated) into the commit message. If TWSE returns empty outside trading hours, note that and confirm the shape is still correct (keys present).

- [ ] **Step 7: Commit**

```bash
git add studio/mcp/servers/twse_server.py studio/mcp/tests/test_twse_server.py
git commit -m "feat(mcp): twse server (5 tools) + verified endpoints + real smoke"
git push origin main
```

---

## Task 5: yahoo-finance MCP server

**Files:**
- Create: `studio/mcp/servers/yahoo_server.py`
- Test: `studio/mcp/tests/test_yahoo_server.py`

- [ ] **Step 1: Write the failing test (offline — on the field selector)**

```python
# studio/mcp/tests/test_yahoo_server.py
import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "yahoo_server.py"
    spec = importlib.util.spec_from_file_location("yahoo_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_select_info_fields():
    m = _load()
    raw = {"regularMarketPrice": 950.0, "trailingPE": 25.4, "shortName": "TSMC", "junk": 1}
    assert m._info(raw, "2330.TW") == {"ticker": "2330.TW", "price": 950.0,
                                       "pe": 25.4, "name": "TSMC"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_yahoo_server.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/mcp/servers/yahoo_server.py
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
```

- [ ] **Step 4: Run unit test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_yahoo_server.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Real smoke (records evidence)**

Run:
```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp
.venv/bin/python -c "import sys; sys.path.insert(0,'servers'); import yahoo_server as y; \
print(y.get_stock_info('2330.TW')); print(len(y.get_historical_stock_prices('^TWII')), 'bars')"
```
Expected: `2330.TW` price + pe non-null; `^TWII` returns ≥60 bars. Paste output into the commit message. If a single ticker errors transiently, retry once; if it still errors, record that and confirm the `{error}` shape is returned (prompt tolerates partial data per spec §7).

- [ ] **Step 6: Commit**

```bash
git add studio/mcp/servers/yahoo_server.py studio/mcp/tests/test_yahoo_server.py
git commit -m "feat(mcp): yahoo-finance server (info/history) + real smoke"
git push origin main
```

---

## Task 6: yt-dlp MCP server (captions only)

**Files:**
- Create: `studio/mcp/servers/ytdlp_server.py`
- Test: `studio/mcp/tests/test_ytdlp_server.py`

- [ ] **Step 1: Write the failing test (offline — on the search-result mapper)**

```python
# studio/mcp/tests/test_ytdlp_server.py
import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "servers" / "ytdlp_server.py"
    spec = importlib.util.spec_from_file_location("ytdlp_server", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_map_search_entries():
    m = _load()
    raw = {"entries": [{"id": "abc", "title": "T1", "upload_date": "20260518",
                        "webpage_url": "https://youtu.be/abc"}]}
    assert m._map_search(raw, 1) == [{"video_id": "abc", "title": "T1",
        "upload_date": "2026-05-18", "url": "https://youtu.be/abc"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_ytdlp_server.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation (captions only; gemma fallback added in Task 7)**

```python
# studio/mcp/servers/ytdlp_server.py
import yt_dlp
from mcp.server.fastmcp import FastMCP

def _map_search(info: dict, max_results: int):
    out = []
    for e in (info.get("entries") or [])[:max_results]:
        d = e.get("upload_date") or ""
        iso = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
        out.append({"video_id": e.get("id"), "title": e.get("title"),
                    "upload_date": iso,
                    "url": e.get("webpage_url") or f"https://youtu.be/{e.get('id')}"})
    return out

def _fetch_captions(video_url: str, langs: list[str]) -> str | None:
    opts = {"skip_download": True, "writesubtitles": True,
            "writeautomaticsub": True, "subtitleslangs": langs, "quiet": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(video_url, download=False)
    subs = {**(info.get("subtitles") or {}), **(info.get("automatic_captions") or {})}
    for lang in langs:
        if lang in subs and subs[lang]:
            import requests
            url = subs[lang][-1].get("url")
            if url:
                t = requests.get(url, timeout=30).text
                if t.strip():
                    return t
    return None

mcp = FastMCP("yt-dlp")

@mcp.tool()
def ytdlp_search_videos(query: str, maxResults: int = 1, uploadDateFilter: str = "today"):
    """Search YouTube; returns [{video_id,title,upload_date,url}]."""
    spec = f"ytsearch{max(maxResults,1)*3}:{query}"
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(spec, download=False)
    return _map_search(info, maxResults)

@mcp.tool()
def ytdlp_download_transcript(video_url: str, language: str = "zh-Hant"):
    """Transcript text. Tries captions zh-TW/zh-Hant/zh/en. (gemma fallback: Task 7.)"""
    txt = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
    if txt:
        return {"source": "captions", "text": txt}
    return {"source": "none", "text": "", "note": "no captions; fallback pending"}

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 4: Run unit test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_ytdlp_server.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Real smoke (records evidence)**

Run:
```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp
.venv/bin/python -c "import sys; sys.path.insert(0,'servers'); import ytdlp_server as v; \
r=v.ytdlp_search_videos('張貽程 外資超錢線',1,'week'); print(r); \
print(v.ytdlp_download_transcript(r[0]['url'])['source'] if r else 'no result')"
```
Expected: a video result; transcript `source` is `captions` or `none`. Paste output into the commit message.

- [ ] **Step 6: Commit**

```bash
git add studio/mcp/servers/ytdlp_server.py studio/mcp/tests/test_ytdlp_server.py
git commit -m "feat(mcp): yt-dlp server (search + caption transcript) + real smoke"
git push origin main
```

---

## Task 7: gemma4:e4b subtitle fallback

**Files:**
- Create: `studio/mcp/lib/gemma_transcribe.py`
- Modify: `studio/mcp/servers/ytdlp_server.py` (wire fallback into `ytdlp_download_transcript`)
- Test: `studio/mcp/tests/test_gemma_transcribe.py`

- [ ] **Step 1: Write the failing test (offline — chunk math is pure)**

```python
# studio/mcp/tests/test_gemma_transcribe.py
import importlib.util, pathlib
def _load():
    p = pathlib.Path(__file__).parents[1] / "lib" / "gemma_transcribe.py"
    spec = importlib.util.spec_from_file_location("gemma_transcribe", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_chunk_ranges():
    m = _load()
    # 1000s audio, 300s chunks -> 4 ranges, last is remainder
    assert m._chunk_ranges(1000, 300) == [(0,300),(300,600),(600,900),(900,1000)]
    assert m._chunk_ranges(250, 300) == [(0,250)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_gemma_transcribe.py -q`
Expected: FAIL — module missing.

- [ ] **Step 3: Write minimal implementation**

```python
# studio/mcp/lib/gemma_transcribe.py
import os, subprocess, tempfile, pathlib, ollama

MODEL = os.environ.get("STUDIO_TRANSCRIBE_MODEL", "gemma4:e4b")
CHUNK = int(os.environ.get("STUDIO_TRANSCRIBE_CHUNK_SEC", "300"))
PROMPT = "Transcribe this Mandarin audio verbatim. Output plain text only, no commentary."

def _chunk_ranges(total_sec: int, chunk: int):
    out, s = [], 0
    while s < total_sec:
        out.append((s, min(s + chunk, total_sec))); s += chunk
    return out or [(0, total_sec)]

def _audio_duration(path: str) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    return int(float(r.stdout.strip() or "0"))

def transcribe(video_url: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        a = str(pathlib.Path(d) / "a.m4a")
        subprocess.run(["yt-dlp", "-f", "bestaudio", "-o", a, "--quiet", video_url], check=True)
        wav = str(pathlib.Path(d) / "a.wav")
        subprocess.run(["ffmpeg", "-y", "-i", a, "-ac", "1", "-ar", "16000", wav],
                       capture_output=True, check=True)
        dur = _audio_duration(wav)
        parts = []
        for (s, e) in _chunk_ranges(dur, CHUNK):
            c = str(pathlib.Path(d) / f"c_{s}.wav")
            subprocess.run(["ffmpeg", "-y", "-i", wav, "-ss", str(s), "-to", str(e), c],
                           capture_output=True, check=True)
            resp = ollama.chat(model=MODEL, messages=[
                {"role": "user", "content": PROMPT, "images": [], "audio": [c]}])
            parts.append(resp["message"]["content"].strip())
        return "\n".join(p for p in parts if p)
```

> Note: the exact Ollama audio-input field (`audio=[...]` vs an attachment arg) depends on the installed `ollama` python client + `gemma4:e4b` modality support. Step 5 (verify-before-rely) is where this is proven against the real model; if the field name differs, fix the single `ollama.chat(...)` call to the form that actually returns text for this model and record the working call in the commit message. The pure `_chunk_ranges` logic (unit-tested here) is the part this task guarantees; the live binding is proven in Step 5.

- [ ] **Step 4: Run unit test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_gemma_transcribe.py -q`
Expected: PASS (1 test).

- [ ] **Step 5: Verify-before-rely real smoke (gate — must pass before wiring)**

Find a short (<3 min) Mandarin YouTube clip that has NO captions (verify with Task 6's `ytdlp_download_transcript` returning `source: none`). Then:
```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp
.venv/bin/python -c "import sys; sys.path.insert(0,'lib'); import gemma_transcribe as g; \
print(g.transcribe('<caption-less mandarin short clip URL>')[:500])"
```
Expected: non-empty, recognisably-Mandarin transcript text. Paste the first ~500 chars into the commit message as evidence. **If output is empty/garbage:** stop, mark this task DONE_WITH_CONCERNS, and report to the controller — the documented contingency (faster-whisper) is a separate decision, not done here.

- [ ] **Step 6: Wire fallback into the server**

In `studio/mcp/servers/ytdlp_server.py`, change the end of `ytdlp_download_transcript` from the `return {"source": "none", ...}` line to:

```python
    try:
        from importlib import import_module
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "lib"))
        g = import_module("gemma_transcribe")
        text = g.transcribe(video_url)
        if text.strip():
            return {"source": "gemma4:e4b", "text": text}
    except Exception as e:
        return {"source": "none", "text": "", "error": f"fallback failed: {e}"}
    return {"source": "none", "text": ""}
```

- [ ] **Step 7: Re-run yt-dlp unit test (no regression)**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio/mcp && .venv/bin/python -m pytest tests/test_ytdlp_server.py tests/test_gemma_transcribe.py -q`
Expected: PASS (2 tests; the search-mapper test and chunk test still green).

- [ ] **Step 8: Commit**

```bash
git add studio/mcp/lib/gemma_transcribe.py studio/mcp/servers/ytdlp_server.py studio/mcp/tests/test_gemma_transcribe.py
git commit -m "feat(mcp): local gemma4:e4b subtitle fallback + verify-before-rely smoke"
git push origin main
```

---

## Task 8: mcpConfig.ts + runClaude wiring

**Files:**
- Create: `studio/lib/runner/mcpConfig.ts`
- Modify: `studio/lib/runner/runClaude.ts`
- Test: `studio/lib/runner/mcpConfig.test.ts`, `studio/lib/runner/runClaude.test.ts` (extend)

- [ ] **Step 1: Verify the real claude flag names (discovery — required)**

Run: `claude --help 2>&1 | grep -iE "mcp-config|strict-mcp|allowed-?tools" ` and record the exact flags. The plan assumes `--mcp-config <path>`, `--strict-mcp-config`, `--allowedTools <comma-list>` (the inherited `eason-daily.sh:27` used `--allowedTools`). Use whatever the installed `claude` (v2.1.143) actually prints; record the confirmed flags in the commit message and use them in Step 4.

- [ ] **Step 2: Write the failing test**

```ts
// studio/lib/runner/mcpConfig.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, writeFile, readFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderMcpConfig } from "./mcpConfig";

let root: string;
beforeEach(async () => { root = await mkdtemp(join(tmpdir(), "mc-")); });

describe("renderMcpConfig", () => {
  it("substitutes tokens and injects FRED key from the inherited .env", async () => {
    const mcpDir = join(root, "studio", "mcp");
    await mkdir(mcpDir, { recursive: true });
    await writeFile(join(mcpDir, "mcp.json.tmpl"),
      JSON.stringify({ mcpServers: { fred: { command: "@PY@",
        args: ["@MCPDIR@/servers/fred_server.py"], env: { FRED_API_KEY: "@FREDKEY@" } },
        sqlite: { command: "@PY@", args: ["@MCPDIR@/servers/sqlite_server.py"],
          env: { STUDIO_DB_PATH: "@DBPATH@" } } } }));
    const envFile = join(root, ".env");
    await writeFile(envFile, "DISCORD_WEBHOOK=secret\nFRED_API_KEY=ABC123\n");
    const out = join(mcpDir, "mcp.json");
    await renderMcpConfig({ mcpDir, envFile, dbPath: "/db/financial.db",
      pythonBin: "/v/python", outPath: out });
    const cfg = JSON.parse(await readFile(out, "utf8"));
    expect(cfg.mcpServers.fred.env.FRED_API_KEY).toBe("ABC123");
    expect(cfg.mcpServers.fred.command).toBe("/v/python");
    expect(cfg.mcpServers.fred.args[0]).toBe(mcpDir + "/servers/fred_server.py");
    expect(cfg.mcpServers.sqlite.env.STUDIO_DB_PATH).toBe("/db/financial.db");
    expect(JSON.stringify(cfg)).not.toContain("secret"); // only FRED key read
  });

  it("throws if FRED_API_KEY missing from env file", async () => {
    const mcpDir = join(root, "m"); await mkdir(mcpDir, { recursive: true });
    await writeFile(join(mcpDir, "mcp.json.tmpl"), "{}");
    const envFile = join(root, ".env"); await writeFile(envFile, "X=1\n");
    await expect(renderMcpConfig({ mcpDir, envFile, dbPath: "d",
      pythonBin: "p", outPath: join(mcpDir, "mcp.json") })).rejects.toThrow(/FRED_API_KEY/);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/mcpConfig.test.ts`
Expected: FAIL — cannot resolve `./mcpConfig`.

- [ ] **Step 4: Write minimal implementation**

```ts
// studio/lib/runner/mcpConfig.ts
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { ConfigError } from "./errors";

function readEnvValue(envText: string, key: string): string | null {
  for (const line of envText.split("\n")) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && m[1] === key) return m[2]!.trim();
  }
  return null;
}

export interface RenderMcpArgs {
  mcpDir: string; envFile: string; dbPath: string;
  pythonBin: string; outPath: string;
}

export async function renderMcpConfig(a: RenderMcpArgs): Promise<string> {
  const tmpl = await readFile(join(a.mcpDir, "mcp.json.tmpl"), "utf8");
  let envText = "";
  try { envText = await readFile(a.envFile, "utf8"); }
  catch { throw new ConfigError(`inherited .env not readable: ${a.envFile}`); }
  const fred = readEnvValue(envText, "FRED_API_KEY");
  if (!fred) throw new ConfigError("FRED_API_KEY not found in inherited .env");
  const rendered = tmpl
    .replaceAll("@PY@", a.pythonBin)
    .replaceAll("@MCPDIR@", a.mcpDir)
    .replaceAll("@DBPATH@", a.dbPath)
    .replaceAll("@FREDKEY@", fred);
  await writeFile(a.outPath, rendered);
  return a.outPath;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/mcpConfig.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 6: Extend runClaude to accept mcp args**

In `studio/lib/runner/runClaude.ts`, add to `RunClaudeArgs` two optional fields and append args. Add after `spawner: Spawner;`:
```ts
  mcpConfigPath?: string;
  allowedTools?: string[];
```
Then change the non-fake `args` construction to:
```ts
  const args = bin.endsWith("fake-claude.sh")
    ? []
    : [
        "-p", a.prompt, "--model", a.model, "--max-turns", String(a.maxTurns),
        ...(a.mcpConfigPath ? ["--mcp-config", a.mcpConfigPath, "--strict-mcp-config"] : []),
        ...(a.allowedTools && a.allowedTools.length
          ? ["--allowedTools", a.allowedTools.join(",")] : []),
      ];
```
(Use the exact flag names confirmed in Step 1 if they differ from `--mcp-config`/`--strict-mcp-config`/`--allowedTools`.)

- [ ] **Step 7: Add a runClaude test for the new args**

Append to `studio/lib/runner/runClaude.test.ts`:
```ts
it("passes mcp-config + allowedTools to a real (non-fake) bin", async () => {
  const seen: string[] = [];
  const spy = async (_f: string, args: string[]) => { seen.push(...args); return { code: 0 }; };
  await runClaude({ prompt: "p", model: "m", maxTurns: 5, cwd: ".", htmlOut: "/tmp/o.html",
    claudeBin: "claude", spawner: spy as any,
    mcpConfigPath: "/x/mcp.json", allowedTools: ["mcp__fred__fred_get_series", "Write"] });
  expect(seen).toContain("--mcp-config");
  expect(seen).toContain("/x/mcp.json");
  expect(seen).toContain("--strict-mcp-config");
  expect(seen.join(",")).toContain("mcp__fred__fred_get_series,Write");
});
```

- [ ] **Step 8: Run the full studio suite**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npm test && npx tsc --noEmit`
Expected: all green (28 tests: prior 26 + mcpConfig 2 + runClaude new 1 = 29; confirm exact count and that tsc=0).

- [ ] **Step 9: Commit**

```bash
git add studio/lib/runner/mcpConfig.ts studio/lib/runner/mcpConfig.test.ts studio/lib/runner/runClaude.ts studio/lib/runner/runClaude.test.ts
git commit -m "feat(studio): mcpConfig render + runClaude --mcp-config/--allowedTools"
git push origin main
```

---

## Task 9: buildPrompt placeholders + bundled report CSS

**Files:**
- Create: `studio/prompts/eason/report.css`
- Modify: `studio/prompts/eason/main.md`, `studio/prompts/eason/picks.md`, `studio/lib/runner/buildPrompt.ts`
- Test: `studio/lib/runner/buildPrompt.test.ts` (extend)

- [ ] **Step 1: Bundle the CSS**

Read `/Users/pochenkuo/AI/new_financial-report-system/financial-report-system/samples/eason-sample.html`, extract the contents of its `<style>...</style>` block verbatim, and write it to `studio/prompts/eason/report.css`. If there is no `<style>` block (CSS is inline on elements), instead write a short comment file: `/* inline styles in sample; main.md instructs Claude to mirror the sample's dark-navy/red/emoji-block card style */` and the prompt edit in Step 3 will describe the style instead of injecting CSS. Record which case applied in the commit message.

- [ ] **Step 2: Write the failing test**

```ts
// append to studio/lib/runner/buildPrompt.test.ts
it("substitutes shell-style report vars and report css", () => {
  const out = buildPrompt({
    promptTemplate: "save to ${HTML_FILE} on ${DATE}; log ${LOG_FILE}; css:{{report_css}}",
    references: [], channel,
    calendarText: "Today is 2026-05-18 (Monday).",
    htmlPath: "/runs/r1/report.html", logPath: "/runs/r1/claude.log",
    dateIso: "2026-05-18", reportCss: "BODY{color:red}",
  });
  expect(out).toContain("save to /runs/r1/report.html on 2026-05-18");
  expect(out).toContain("log /runs/r1/claude.log");
  expect(out).toContain("css:BODY{color:red}");
  expect(out).not.toContain("${"); expect(out).not.toContain("{{report_css}}");
});
```
(`channel` is the existing test fixture object already defined at the top of this file.)

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/buildPrompt.test.ts`
Expected: FAIL — `buildPrompt` has no `htmlPath`/`logPath`/`dateIso`/`reportCss` params.

- [ ] **Step 4: Update buildPrompt**

Replace `studio/lib/runner/buildPrompt.ts` contents with:
```ts
import type { Channel } from "../config/schema";

export interface BuildPromptArgs {
  promptTemplate: string;
  references: readonly string[];
  channel: Channel;
  calendarText: string;
  htmlPath?: string;
  logPath?: string;
  dateIso?: string;
  reportCss?: string;
}

export function buildPrompt(a: BuildPromptArgs): string {
  let body = a.promptTemplate
    .replaceAll("{{channel.handle}}", a.channel.handle)
    .replaceAll("{{channel.name}}", a.channel.name)
    .replaceAll("{{channel.search_query}}", a.channel.search_query)
    .replaceAll("{{calendar}}", a.calendarText)
    .replaceAll("{{report_css}}", a.reportCss ?? "")
    .replaceAll("${HTML_FILE}", a.htmlPath ?? "")
    .replaceAll("${DATE}", a.dateIso ?? "")
    .replaceAll("${LOG_FILE}", a.logPath ?? "");
  if (a.references.length > 0)
    body += "\n\n---\n# Reference material (authoritative)\n\n" +
      a.references.join("\n\n---\n\n");
  return body;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/buildPrompt.test.ts`
Expected: PASS (prior buildPrompt tests + the new one).

- [ ] **Step 6: Fix the prompt files**

In `studio/prompts/eason/main.md`: replace the WSL CSS reference line (the one containing `/mnt/c/FINANCIAL/reports/...html` used as CSS reference) with: `使用以下 CSS 樣式：\n{{report_css}}` (Traditional Chinese kept consistent with the file). Leave every other analytical line untouched. The existing `${HTML_FILE}`/`${DATE}` literals stay (now substituted by buildPrompt). In `studio/prompts/eason/picks.md`: leave `${HTML_FILE}`/`${LOG_FILE}`/`${DATE}` literals as-is (now substituted). Record the exact line changed in the commit message.

- [ ] **Step 7: Commit**

```bash
git add studio/prompts/eason/report.css studio/prompts/eason/main.md studio/prompts/eason/picks.md studio/lib/runner/buildPrompt.ts studio/lib/runner/buildPrompt.test.ts
git commit -m "feat(studio): buildPrompt report-path/css substitution + bundled CSS"
git push origin main
```

---

## Task 10: runPipeline wiring + chrome path + STUDIO_ROOT

**Files:**
- Modify: `studio/lib/runner/paths.ts`, `studio/lib/runner/postProcess.ts`, `studio/lib/runner/runPipeline.ts`
- Test: extend `studio/lib/runner/runPipeline.test.ts`, `studio/lib/runner/postProcess.test.ts`

- [ ] **Step 1: Fix STUDIO_ROOT (module-relative)**

Replace `studio/lib/runner/paths.ts` contents with:
```ts
import { join } from "node:path";
import { fileURLToPath } from "node:url";
export const STUDIO_ROOT = fileURLToPath(new URL("../../", import.meta.url)); // studio/
export const RUNS_ROOT = join(STUDIO_ROOT, "runs");
```

- [ ] **Step 2: Chrome path resolution test (postProcess)**

Append to `studio/lib/runner/postProcess.test.ts`:
```ts
it("uses a resolvable chrome binary for the pdf step", async () => {
  const seen: string[] = [];
  const spy: Spawner = async (file) => { seen.push(file); return { code: 0 }; };
  await postProcess({ htmlPath: "/tmp/r.html",
    post: { pdf: true, notify: false, picks: { model: "h", prompt: "p" } } as any,
    runPicks: false, picksPrompt: "x",
    financeRoot: "/repo/financial-report-system", spawner: spy });
  expect(seen.some((f) => /chrome/i.test(f))).toBe(true);
});
```
(Already-passing behaviourally; this pins that a chrome-ish binary string is chosen.)

- [ ] **Step 3: Implement chrome resolution in postProcess**

In `studio/lib/runner/postProcess.ts`, before the `if (a.post.pdf)` block add:
```ts
  const { existsSync } = await import("node:fs");
  const CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
  ].find((p) => existsSync(p)) ?? "google-chrome";
```
and change the pdf spawn's first arg from `"google-chrome"` to `CHROME`.

- [ ] **Step 4: Run postProcess tests**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/postProcess.test.ts`
Expected: PASS (prior 3 + new 1).

- [ ] **Step 5: Wire mechanicalChecks + new buildPrompt args into runPipeline (test first)**

Append to `studio/lib/runner/runPipeline.test.ts`:
```ts
it("records advisory qualityOk=false for the fake report but still succeeds", async () => {
  const r = await runPipeline("eason", {
    studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
    spawner: async (file, args, opts) =>
      file.endsWith("fake-claude.sh") ? spawnProc(file, args, opts) : { code: 0 },
  });
  expect(r.status).toBe("succeeded");
  expect(r.qualityOk).toBe(false);              // fixture HTML lacks required sections
  expect(Array.isArray(r.qualityFailures)).toBe(true);
});
```

- [ ] **Step 6: Run test to verify it fails**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/runPipeline.test.ts`
Expected: FAIL — `qualityOk`/`qualityFailures` not on the record yet.

- [ ] **Step 7: Implement the wiring**

In `studio/lib/runner/runRecord.ts` `RunRecord` interface add: `qualityOk?: boolean; qualityFailures?: string[];` (after `notifySent?`).
In `studio/lib/runner/runPipeline.ts`:
- import: `import { calendarFacts } from "./calendar";` already present; add `import { mechanicalChecks } from "../quality/check";` and `import { readFile } from "node:fs/promises";`.
- pass new buildPrompt args: change the `buildPrompt({...})` call to also pass
  `htmlPath: htmlOut, logPath: join(o.runsRoot, runId, "claude.log"), dateIso: cal.iso,`
  (the `cal` variable already exists from `calendarFacts`).
- after the successful `postProcess(...)` and before the final `updateRun(... status:"succeeded" ...)`, insert:
```ts
    let qualityOk: boolean | undefined;
    let qualityFailures: string[] | undefined;
    try {
      const html = await readFile(cr.htmlPath, "utf8");
      const q = mechanicalChecks(html, { iso: cal.iso, weekday: cal.weekday });
      qualityOk = q.ok; qualityFailures = q.failures;
    } catch { qualityOk = false; qualityFailures = ["report HTML unreadable"]; }
```
  and add `qualityOk, qualityFailures,` to the succeeded `updateRun` patch object. `mechanicalChecks` never throws; it does NOT influence `status`.

- [ ] **Step 8: Run full suite + tsc**

Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npm test && npx tsc --noEmit`
Expected: all green; tsc=0. (The existing end-to-end test still asserts `status==="succeeded"`; the new one asserts the advisory fields.)

- [ ] **Step 9: Commit**

```bash
git add studio/lib/runner/paths.ts studio/lib/runner/postProcess.ts studio/lib/runner/postProcess.test.ts studio/lib/runner/runRecord.ts studio/lib/runner/runPipeline.ts studio/lib/runner/runPipeline.test.ts
git commit -m "feat(studio): wire mechanicalChecks (advisory) + chrome path + STUDIO_ROOT"
git push origin main
```

---

## Task 11: Real end-to-end Eason run

**Files:** none created; this is the integration + evidence task.

- [ ] **Step 1: Render the real mcp.json**

Run (TS one-off via vitest-style node is unavailable; use a tiny inline node script through the studio tsconfig is overkill — instead drive it through a temporary test). Create `studio/lib/runner/_e2e.render.test.ts`:
```ts
import { it } from "vitest";
import { renderMcpConfig } from "./mcpConfig";
import { STUDIO_ROOT } from "./paths";
import { join } from "node:path";
it("render real mcp.json", async () => {
  await renderMcpConfig({
    mcpDir: join(STUDIO_ROOT, "mcp"),
    envFile: join(STUDIO_ROOT, "../financial-report-system/scripts/.env"),
    dbPath: join(STUDIO_ROOT, "../financial-report-system/data/financial.db"),
    pythonBin: join(STUDIO_ROOT, "mcp/.venv/bin/python"),
    outPath: join(STUDIO_ROOT, "mcp/mcp.json"),
  });
});
```
Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/_e2e.render.test.ts`
Expected: PASS; `studio/mcp/mcp.json` now exists (gitignored). Then delete `_e2e.render.test.ts` (it was a one-off harness; do not commit it).

- [ ] **Step 2: Trigger a real run**

Add a temporary node-driven trigger via a one-off test `studio/lib/runner/_e2e.run.test.ts`:
```ts
import { it, expect } from "vitest";
import { runPipeline } from "./runPipeline";
import { spawnProc } from "./spawnProc";
import { STUDIO_ROOT, RUNS_ROOT } from "./paths";
import { join } from "node:path";
it("real eason run", async () => {
  const r = await runPipeline("eason", {
    studioRoot: STUDIO_ROOT, runsRoot: RUNS_ROOT,
    claudeBin: "claude", spawner: spawnProc,
    mcpConfigPath: join(STUDIO_ROOT, "mcp/mcp.json"),
    allowedTools: [
      "mcp__yt-dlp__ytdlp_search_videos","mcp__yt-dlp__ytdlp_download_transcript",
      "mcp__twse__get_daily_market_trading_info","mcp__twse__get_market_index_info",
      "mcp__twse__get_margin_trading_info","mcp__twse__get_stock_daily_trading",
      "mcp__twse__get_foreign_investment_by_industry",
      "mcp__yahoo-finance__get_stock_info","mcp__yahoo-finance__get_historical_stock_prices",
      "mcp__fred__fred_get_series",
      "mcp__sqlite__query","mcp__sqlite__create_record","mcp__sqlite__update_records",
      "Write","Read",
    ],
  } as any);
  console.log(JSON.stringify(r, null, 2));
  expect(["succeeded","failed"]).toContain(r.status);
}, 1800000); // 30 min budget
```
(`runPipeline` must accept `mcpConfigPath`/`allowedTools` and forward them to `runClaude` — extend `RunPipelineOpts` + the `runClaude({...})` call with these two passthrough fields as part of THIS step; they default undefined so the fake-CLI tests are unaffected. Show the two-line interface addition in the commit.)
Run: `cd /Users/pochenkuo/AI/new_financial-report-system/studio && npx vitest run lib/runner/_e2e.run.test.ts`
Expected: completes with a `RunRecord`. Capture the JSON.

- [ ] **Step 3: Self-verify the produced report**

- Confirm `studio/runs/<runId>/report.html` exists and is non-trivial (`wc -c`).
- Read it; run the structural checks: required sections present, `mechanicalChecks` `qualityOk`/`qualityFailures` from the run record, calendar weekday correct for the run date, no news items dated >7 days before or after the run date.
- Diff structure against `financial-report-system/samples/eason-sample.html` (sections + signal blocks + a picks table present).
- Confirm `eason_training`/`eason_daily`/`eason_picks` rows were written: `studio/mcp/.venv/bin/python -c "import sqlite3;c=sqlite3.connect('/Users/pochenkuo/AI/new_financial-report-system/financial-report-system/data/financial.db');print([(t,c.execute(f'select count(*) from {t}').fetchone()[0]) for t in ['eason_training','eason_daily','eason_picks']])"`.
- Delete `_e2e.run.test.ts` (one-off harness; not committed).

- [ ] **Step 4: Commit the evidence**

```bash
git add docs/superpowers/plans/2026-05-18-agent-flow-studio-live-data.md
git commit -m "docs: Phase 2 complete — real local Eason report produced (evidence in body)

<paste: runId, run.json status/qualityOk/qualityFailures, report byte size,
section-presence check, sqlite row counts, transcript source (captions|gemma4:e4b)>"
git push origin main
```
(If no plan-file change is pending, commit a short `docs/superpowers/plans/PHASE2-EVIDENCE.md` with the same evidence instead — the point is a durable record of the real run.)

- [ ] **Step 5: Escalate ONLY the subjective call**

Present the rendered `report.html` to the user for the one judgment that is theirs per `feedback_self_verification_first`: *is this Eason analysis genuinely insightful and in his style?* Provide: the report, the mechanical-check result, the transcript source, and any data gaps (e.g. a Yahoo ticker that errored). Do not ask the user to verify anything mechanical — that was all self-checked above.

---

## Self-Review

**1. Spec coverage:**
- §1 build all 5 servers → Tasks 2–6. §1 tool contract (13 ids) → enforced in Task 8 allowedTools + Task 11. ✓
- §2 architecture (Python venv, mcp.json render, runClaude flags, secret handling) → Tasks 1, 8. FRED-only secret read + not logged → Task 8 `mcpConfig.ts` test asserts `not.toContain("secret")`. ✓
- §3 deterministic gaps: `${HTML_FILE}/${DATE}/${LOG_FILE}` + CSS → Task 9; mechanicalChecks advisory → Task 10; chrome path → Task 10; STUDIO_ROOT → Task 10; sqlite schema autoinit → Task 2. ✓
- §4 gemma fallback (captions→audio→chunk→gemma4:e4b, verify-before-rely) → Tasks 6 + 7. ✓
- §5 verification (per-server real smokes, contract test, e2e, escalate only subjective) → smoke steps in Tasks 3–7, Task 8 contract test, Task 11. ✓
- §6 YAGNI (no messaging/canvas/whisper-built) → no such tasks; whisper only named as contingency. ✓
- §7 risks (Yahoo `{error}`, gemma gate, TWSE per-endpoint, tool-name fidelity) → Task 5 error shape, Task 7 Step 5 gate, Task 4 discovery, Task 8/11 explicit `mcp__server__tool` ids. ✓
- §8 11-step sequence → Tasks 1–11 map 1:1. ✓

**2. Placeholder scan:** The `<PATH from Step 1>` / `<code key from Step 1>` tokens in Task 4 and the caption-less URL in Task 7 Step 5 are explicitly *resolved within the same task by a stated discovery command*, not deferred — this is required because the values are external/live and must be verified, not memorised; the plan states the exact discovery command and lock criteria. All TS/Python code blocks are complete. No "TBD/handle errors/similar to Task N".

**3. Type consistency:** `renderMcpConfig(RenderMcpArgs)` used identically in Tasks 8 & 11. `RunClaudeArgs` new fields `mcpConfigPath?/allowedTools?` defined Task 8, forwarded via `RunPipelineOpts` Task 11. `RunRecord.qualityOk?/qualityFailures?` defined Task 10, asserted Task 10/11. `BuildPromptArgs` new optional fields defined Task 9, supplied by runPipeline Task 10. Python: `_query/_create_record/_update_records`, `_latest`, `_row_for`, `_info`, `_map_search`, `_chunk_ranges/transcribe` names consistent between each server and its test. No drift.

---

## Execution Handoff
Plan complete and saved to `docs/superpowers/plans/2026-05-18-agent-flow-studio-live-data.md`.
