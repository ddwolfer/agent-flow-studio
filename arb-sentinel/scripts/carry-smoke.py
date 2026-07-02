"""Smoke test for carry-guardian's 4 Bitget endpoints.

Purpose (per spec §4 尾巴):
1. Determine whether the account is on v2 classic (/api/v2/earn/loan/*) or v3
   UTA (/api/v3/loan/*). We check by trying v2 first and looking for order
   1454384882276573190 in the ongoing-orders response.
2. Dump the RAW JSON of each endpoint so we can pin exact field names +
   units (spec's "不要猜 pledgeRate 是 63.45 還是 0.6345" concern).
3. Confirm which `type` in savings/records holds interest payouts.

Read-only key required (existing BITGET_API_KEY/SECRET/PASSPHRASE in .env).
NEVER writes anywhere. Prints to stdout; append notes to
docs/superpowers/specs/carry-smoke-notes.md by hand after review.

Usage:
    mcp/.venv/bin/python scripts/carry-smoke.py  # from finance-workflows
    # or from arb-sentinel root:
    .venv/bin/python scripts/carry-smoke.py
"""
import json
import os
import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT))

# Load .env like the runner does (self-contained; no dep on runner import).
env_path = _ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k.startswith("export "):
            k = k[len("export "):].strip()
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
            v = v[1:-1]
        os.environ.setdefault(k, v)

from arb_sentinel.collectors.bitget import _signed_get  # noqa: E402
import httpx  # noqa: E402

KEY = os.environ.get("BITGET_API_KEY", "")
SEC = os.environ.get("BITGET_API_SECRET", "")
PASS = os.environ.get("BITGET_API_PASSPHRASE", "")

# Position facts from spec §1 for anchoring what to look for.
EXPECTED_ORDER_ID = "1454384882276573190"
EXPECTED_LOAN_COIN = "USDC"
EXPECTED_PLEDGE_COIN = "BTC"
EXPECTED_EARN_ASSET = "USDGO"


def _print_header(label: str, url: str) -> None:
    line = "=" * 80
    print(f"\n{line}\n{label}\n  → {url}\n{line}")


def _dump(label: str, obj) -> None:
    print(f"\n[{label}]")
    print(json.dumps(obj, ensure_ascii=False, indent=2)[:5000])


def probe_loan_ongoing_orders():
    """/api/v2/earn/loan/ongoing-orders — signed, returns list of active loans.
    We look for order EXPECTED_ORDER_ID. If absent, try v3 UTA path."""
    path = "/api/v2/earn/loan/ongoing-orders"
    _print_header("1. loan_ongoing_orders (v2 classic)", path)
    data, err = _signed_get(path, "", KEY, SEC, PASS)
    if err:
        print(f"  ✗ v2 failed: {err}")
        # Try v3 UTA
        path3 = "/api/v3/loan/ongoing-orders"
        _print_header("1b. loan_ongoing_orders (v3 UTA fallback)", path3)
        data, err = _signed_get(path3, "", KEY, SEC, PASS)
        if err:
            print(f"  ✗ v3 also failed: {err}")
            return None, None
        _dump("v3 raw", data)
        return "v3", data
    _dump("v2 raw", data)
    # Look for the expected order id in whatever list it returned
    dd = data.get("data")
    candidates = []
    if isinstance(dd, list):
        candidates.append(dd)
    elif isinstance(dd, dict):
        for k in ("resultList", "orderList", "list"):
            v = dd.get(k)
            if isinstance(v, list):
                candidates.append(v)
    for shape in candidates:
        hits = [o for o in shape if isinstance(o, dict)
                and str(o.get("orderId") or o.get("id") or "") == EXPECTED_ORDER_ID]
        if hits:
                print(f"\n  ✓ Found expected order {EXPECTED_ORDER_ID}")
                print("  Field survey (first hit):")
                for k, v in hits[0].items():
                    print(f"    {k!r}: {v!r}  ({type(v).__name__})")
                return "v2", data
    print(f"\n  ⚠ Order {EXPECTED_ORDER_ID} NOT found in v2 response")
    print("  (could be that the account uses v3 UTA — spec says probe next)")
    return "v2?", data


def probe_loan_hour_interest():
    """/api/v2/earn/loan/public/hour-interest — PUBLIC (no auth). Query coin."""
    url = "https://api.bitget.com/api/v2/earn/loan/public/hour-interest"
    _print_header("2. loan_hour_interest (public)", url)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, params={"coin": EXPECTED_LOAN_COIN})
        print(f"  HTTP {r.status_code}")
        obj = r.json()
        _dump("raw", obj)
        # Field survey
        d = obj.get("data")
        if isinstance(d, dict):
            print("\n  Field survey:")
            for k, v in d.items():
                print(f"    {k!r}: {v!r}  ({type(v).__name__})")
        elif isinstance(d, list) and d:
            print("\n  First entry field survey:")
            for k, v in (d[0] if isinstance(d[0], dict) else {}).items():
                print(f"    {k!r}: {v!r}  ({type(v).__name__})")
    except Exception as e:
        print(f"  ✗ failed: {type(e).__name__}: {e}")


def probe_savings_assets():
    """/api/v2/earn/savings/assets — signed. Where's USDGO balance?"""
    path = "/api/v2/earn/savings/assets"
    _print_header("3a. savings_assets", path)
    data, err = _signed_get(path, "", KEY, SEC, PASS)
    if err:
        print(f"  ✗ failed: {err}")
        return
    _dump("raw", data)
    # Find USDGO entry
    for shape in (data.get("data"), (data.get("data") or {}).get("resultList")):
        if isinstance(shape, list):
            for item in shape:
                if isinstance(item, dict) and str(item.get("productCoin") or
                                                    item.get("coin") or "") == EXPECTED_EARN_ASSET:
                    print(f"\n  ✓ Found USDGO entry:")
                    for k, v in item.items():
                        print(f"    {k!r}: {v!r}  ({type(v).__name__})")


def probe_savings_records():
    """/api/v2/earn/savings/records — signed. Which `type` holds daily interest?"""
    for record_type in ("interest", "profit", "settleInterest", "sub_income"):
        path = "/api/v2/earn/savings/records"
        _print_header(f"3b. savings_records (type={record_type})", path)
        query = f"type={record_type}&coin={EXPECTED_EARN_ASSET}&limit=3"
        data, err = _signed_get(path, query, KEY, SEC, PASS)
        if err:
            print(f"  ✗ failed: {err}")
            continue
        _dump(f"type={record_type} raw", data)
        # If we got 3 non-empty rows, that's the winner
        for shape in (data.get("data"), (data.get("data") or {}).get("resultList")):
            if isinstance(shape, list) and shape:
                print(f"\n  ✓ type={record_type} returned {len(shape)} rows — CANDIDATE")


def probe_spot_orderbook():
    """/api/v2/spot/market/orderbook — PUBLIC. USDGO/USDC bid depth."""
    url = "https://api.bitget.com/api/v2/spot/market/orderbook"
    _print_header("4. spot_orderbook (public)", url)
    try:
        with httpx.Client(timeout=15.0) as c:
            r = c.get(url, params={"symbol": f"{EXPECTED_EARN_ASSET}USDC", "limit": 15})
        print(f"  HTTP {r.status_code}")
        obj = r.json()
        _dump("raw", obj)
        d = obj.get("data") or {}
        bids = d.get("bids") or []
        asks = d.get("asks") or []
        if bids:
            print(f"\n  Top bid: {bids[0]}  ({len(bids)} levels)")
            total = sum(float(b[1]) for b in bids if len(b) >= 2)
            print(f"  Cumulative bid qty (top {len(bids)}): {total:,.2f} {EXPECTED_EARN_ASSET}")
        if asks:
            print(f"  Top ask: {asks[0]}")
    except Exception as e:
        print(f"  ✗ failed: {type(e).__name__}: {e}")


def main() -> int:
    print("carry-guardian smoke test — 4 endpoints, read-only key")
    print(f"Expected order id: {EXPECTED_ORDER_ID}")
    print(f"Expected assets: loan={EXPECTED_LOAN_COIN}, pledge={EXPECTED_PLEDGE_COIN}, "
          f"earn={EXPECTED_EARN_ASSET}\n")
    if not (KEY and SEC and PASS):
        print("✗ Missing BITGET_API_KEY/SECRET/PASSPHRASE in .env")
        return 1
    version, _ = probe_loan_ongoing_orders() or (None, None)
    probe_loan_hour_interest()
    probe_savings_assets()
    probe_savings_records()
    probe_spot_orderbook()
    print("\n" + "=" * 80)
    print("Smoke complete. Copy notes to docs/superpowers/specs/carry-smoke-notes.md")
    print(f"Account version guess: {version!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
