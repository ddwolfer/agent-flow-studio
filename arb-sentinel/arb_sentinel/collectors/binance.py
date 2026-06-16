import datetime, hashlib, hmac, time
import httpx
from ..models import Opportunity

BASE = "https://api.binance.com"
FLEX = "/sapi/v1/simple-earn/flexible/list"
NEXT_RATE = "/sapi/v1/margin/next-hourly-interest-rate"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _signed_get(path, params, key, secret, timeout=20.0):
    """Signed Binance GET -> (json, None) | (None, err). Never raises.
    Signature = hex(HMAC-SHA256(querystring, secret)); X-MBX-APIKEY header."""
    try:
        params = dict(params)
        params["recvWindow"] = 5000
        params["timestamp"] = int(time.time() * 1000)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        sig = hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
        url = f"{BASE}{path}?{qs}&signature={sig}"
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, headers={"X-MBX-APIKEY": key})
        if r.status_code != 200:
            return None, f"binance {path} HTTP {r.status_code}: {r.text[:120]}"
        return r.json(), None
    except Exception as e:
        return None, f"binance {path} {type(e).__name__}: {e}"


def collect_rates(cfg) -> tuple[list[Opportunity], list[str]]:
    """Binance Simple Earn flexible APR for cfg.assets (SIGNED, read-only key).
    latestAnnualPercentageRate is already a decimal string. Never raises."""
    key = getattr(cfg, "binance_api_key", "")
    secret = getattr(cfg, "binance_api_secret", "")
    if not key or not secret:
        return [], ["binance: no api key/secret in .env (skipped)"]
    opps, errors = [], []
    for asset in cfg.assets:
        data, err = _signed_get(FLEX, {"asset": asset, "size": 100}, key, secret)
        if err:
            errors.append(err); continue
        rows = data.get("rows") or []
        row = next((x for x in rows if x.get("asset") == asset and x.get("canPurchase")), None)
        if row is None:
            row = next((x for x in rows if x.get("asset") == asset), None)
        if row is None:
            continue
        try:
            apr = float(row["latestAnnualPercentageRate"])
        except (KeyError, ValueError, TypeError):
            errors.append(f"binance {asset}: bad latestAnnualPercentageRate"); continue
        tier = row.get("tierAnnualPercentageRate")
        opps.append(Opportunity(
            exchange="binance", category="flexible_earn", asset=asset,
            apr=apr, apr_source="api",
            tier_info=(str(tier) if tier else None),
            source_url="https://www.binance.com/en/earn",
            raw_snapshot=row, collected_at=_now_iso()))
    return opps, errors


def collect_borrow(cfg) -> tuple[dict, list[str]]:
    """Binance cross-margin borrow rates per asset, annualised (hourly × 24 × 365).
    SIGNED (read-only key). Returns ({asset: borrow_apr}, errors). Never raises."""
    key = getattr(cfg, "binance_api_key", "")
    secret = getattr(cfg, "binance_api_secret", "")
    if not key or not secret:
        return {}, ["binance borrow: no api key/secret (skipped)"]
    data, err = _signed_get(NEXT_RATE, {"assets": ",".join(cfg.assets), "isIsolated": "FALSE"},
                            key, secret)
    if err:
        return {}, [err]
    out = {}
    for row in (data or []):
        asset = row.get("asset")
        try:
            out[asset] = float(row["nextHourlyInterestRate"]) * 24 * 365
        except (KeyError, ValueError, TypeError):
            pass
    return out, []
