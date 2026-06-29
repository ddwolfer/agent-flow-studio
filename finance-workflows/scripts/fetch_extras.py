"""Pre-fetch supporting data for the morning-briefing workflow.

Runs BEFORE `run-workflow.py morning-briefing` and writes a JSON file the
prompt then loads with the Read tool. Each fetcher is independent and never
raises out — a failing source is recorded as `{"error": "<msg>"}` so the
prompt can render "資料不可用" instead of dropping the entire briefing.

Data sources (all keyless, all JSON or CSV):
  1. Binance fapi — BTCUSDT + ETHUSDT perpetual funding rate (latest +
     trailing 24h avg) and open interest. Source of crypto leverage signal.
  2. CBOE — VIX, VIX9D, VIX3M daily CSV. Used to compute the VIX9D/VIX
     and VX1:VX2 backwardation regime flag.
  3. Treasury fiscaldata — upcoming auctions. Used to populate "today's
     calendar" with the next 10 days of auction schedule.
  4. DefiLlama stablecoins — USDT + USDC circulating + 24h Δ. Source of
     crypto on-ramp liquidity (proxy for institutional bid).

Output shape (top-level keys):
  generated_at_utc: ISO timestamp
  binance_funding: {"BTC": {...}, "ETH": {...}}
  binance_oi:      {"BTC": {...}, "ETH": {...}}
  cboe_vix:        {"VIX": {...}, "VIX9D": {...}, "VIX3M": {...}}
  treasury_auctions: {"auctions": [...]}
  stablecoins:     {"stablecoins": [...], "usdt_usdc_combined_delta_24h": <num>}

Usage:
  python fetch_extras.py --output /path/to/extras.json
"""
import argparse, datetime, io, json, pathlib, sys
import csv
import httpx

_FAPI = "https://fapi.binance.com"
_CBOE = ("https://cdn.cboe.com/api/global/us_indices/daily_prices/"
         "{code}_History.csv")
_TREAS = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
          "v1/accounting/od/upcoming_auctions")
_STABLECOINS = "https://stablecoins.llama.fi/stablecoins"

_DEFAULT_TIMEOUT = 12.0


# ── 1. Binance fapi funding ───────────────────────────────────────────────────
def fetch_binance_funding(symbol: str, timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Latest perp funding rate + 24h trailing average. 3 samples = 24h on
    Binance's 8h cadence. Returns {"error": ...} on any failure."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{_FAPI}/fapi/v1/fundingRate",
                      params={"symbol": symbol, "limit": 3})
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:120]}"}
        rows = r.json()
        if not isinstance(rows, list) or not rows:
            return {"error": "empty response"}
        latest = float(rows[-1]["fundingRate"])
        avg = sum(float(r["fundingRate"]) for r in rows) / len(rows)
        return {
            "_symbol": symbol,
            "latest_rate_8h": latest,
            "avg_24h_rate_8h": avg,
            "latest_annualised": latest * 3 * 365,   # 3 cycles/day × 365
            "samples": len(rows),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 2. Binance fapi open interest ─────────────────────────────────────────────
def fetch_binance_oi(symbol: str, timeout: float = _DEFAULT_TIMEOUT) -> dict:
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(f"{_FAPI}/fapi/v1/openInterest",
                      params={"symbol": symbol})
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:120]}"}
        j = r.json()
        return {
            "_symbol": symbol,
            "open_interest_btc": float(j.get("openInterest") or 0),
            "as_of_ms": j.get("time"),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 3. CBOE VIX/VIX9D/VIX3M ──────────────────────────────────────────────────
def fetch_cboe_vix(code: str, timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Latest close + DoD change from the CBOE daily CSV. `code` ∈
    {VIX, VIX9D, VIX3M}. ~200 KB CSV download — fine on a daily cron."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(_CBOE.format(code=code))
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        rows = list(csv.DictReader(io.StringIO(r.text)))
        if len(rows) < 2 or "CLOSE" not in (rows[-1].keys()):
            return {"error": "malformed CSV"}
        last, prev = rows[-1], rows[-2]
        return {
            "_code": code,
            "latest_date": last["DATE"],
            "latest_close": float(last["CLOSE"]),
            "prev_close": float(prev["CLOSE"]),
            "dod_change": float(last["CLOSE"]) - float(prev["CLOSE"]),
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 4. Treasury fiscaldata upcoming auctions ──────────────────────────────────
def fetch_treasury_auctions(limit: int = 10,
                            timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """Upcoming UST auctions sorted ascending by date. Each entry has
    auction_date / security_type / security_term / offering_amt (when set).

    The endpoint is named `upcoming_auctions` but in practice contains the
    HISTORICAL schedule — without a date filter you get auctions from 2024.
    Apply `filter=auction_date:gte:<today>` to get genuinely future ones."""
    try:
        today = datetime.date.today().isoformat()
        with httpx.Client(timeout=timeout) as c:
            r = c.get(_TREAS, params={
                "sort": "auction_date",
                "filter": f"auction_date:gte:{today}",
                "page[size]": limit,
            })
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}: {r.text[:120]}"}
        data = (r.json() or {}).get("data") or []
        out = []
        for row in data[:limit]:
            out.append({
                "auction_date": row.get("auction_date"),
                "security_type": row.get("security_type"),
                "security_term": row.get("security_term"),
                "offering_amt": row.get("offering_amt"),
            })
        return {"auctions": out}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 5. DefiLlama stablecoins ─────────────────────────────────────────────────
def fetch_stablecoin_supply(timeout: float = _DEFAULT_TIMEOUT) -> dict:
    """USDT + USDC circulating supply and 24h delta. Smaller stables omitted
    to keep the prompt focused on the institutional on-ramp signal."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(_STABLECOINS)
        if r.status_code != 200:
            return {"error": f"HTTP {r.status_code}"}
        assets = (r.json() or {}).get("peggedAssets") or []
        out = []
        combined = 0.0
        for a in assets:
            sym = a.get("symbol")
            if sym not in ("USDT", "USDC"):
                continue
            cur = (a.get("circulating") or {}).get("peggedUSD") or 0
            prev = (a.get("circulatingPrevDay") or {}).get("peggedUSD") or 0
            delta = float(cur) - float(prev)
            out.append({
                "symbol": sym,
                "name": a.get("name"),
                "circulating_usd": float(cur),
                "circulating_prev_24h_usd": float(prev),
                "delta_24h_usd": delta,
            })
            combined += delta
        return {
            "stablecoins": out,
            "usdt_usdc_combined_delta_24h": combined,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── orchestration ────────────────────────────────────────────────────────────
def collect_all() -> dict:
    """Run every fetcher independently. Each failure is isolated in its own
    `error` key so the prompt can degrade gracefully."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "binance_funding": {
            "BTC": fetch_binance_funding("BTCUSDT"),
            "ETH": fetch_binance_funding("ETHUSDT"),
        },
        "binance_oi": {
            "BTC": fetch_binance_oi("BTCUSDT"),
            "ETH": fetch_binance_oi("ETHUSDT"),
        },
        "cboe_vix": {
            "VIX": fetch_cboe_vix("VIX"),
            "VIX9D": fetch_cboe_vix("VIX9D"),
            "VIX3M": fetch_cboe_vix("VIX3M"),
        },
        "treasury_auctions": fetch_treasury_auctions(limit=10),
        "stablecoins": fetch_stablecoin_supply(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="path to write JSON")
    args = ap.parse_args(argv)
    data = collect_all()
    out = pathlib.Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(f"[fetch_extras] wrote {out} ({len(json.dumps(data))} bytes)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
