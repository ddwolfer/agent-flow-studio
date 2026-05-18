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
