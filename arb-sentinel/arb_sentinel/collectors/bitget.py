import base64, datetime, hashlib, hmac, time
import httpx
from ..models import Opportunity

BASE = "https://api.bitget.com"
PRODUCT = "/api/v2/earn/savings/product"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _signed_get(path, query, key, secret, passphrase, timeout=20.0):
    """Signed Bitget GET -> (json, None) | (None, err). Never raises.
    ACCESS-SIGN = base64(HMAC-SHA256(ts + 'GET' + path + ('?'+query), secret))."""
    try:
        ts = str(int(time.time() * 1000))
        prehash = ts + "GET" + path + (("?" + query) if query else "")
        sign = base64.b64encode(
            hmac.new(secret.encode(), prehash.encode(), hashlib.sha256).digest()).decode()
        url = f"{BASE}{path}" + (("?" + query) if query else "")
        headers = {"ACCESS-KEY": key, "ACCESS-SIGN": sign,
                   "ACCESS-PASSPHRASE": passphrase, "ACCESS-TIMESTAMP": ts,
                   "Content-Type": "application/json", "locale": "en-US"}
        with httpx.Client(timeout=timeout) as c:
            r = c.get(url, headers=headers)
        if r.status_code != 200:
            return None, f"bitget {path} HTTP {r.status_code}: {r.text[:120]}"
        j = r.json()
        if str(j.get("code")) != "00000":
            return None, f"bitget {path} code {j.get('code')}: {j.get('msg')}"
        return j, None
    except Exception as e:
        return None, f"bitget {path} {type(e).__name__}: {e}"


def _applicable_apy(apylist, ref_capital):
    """currentApy (percent) for the tier whose [minStepVal, maxStepVal) band contains
    ref_capital. Bitget rates are TIERED by amount and DECLINE — the headline first-tier
    rate usually only applies to a tiny band (the spec's 'displayed APR != sustainable APR'
    trap). Returns (apy_pct, rateLevel) or None. With ref_capital<=0 (or band fields
    missing) the open first tier matches."""
    for a in apylist:
        try:
            lo = float(a.get("minStepVal") or 0)
            hi = float(a.get("maxStepVal") or 0)
            apy = float(a["currentApy"])
        except (KeyError, ValueError, TypeError):
            continue
        in_band = ref_capital >= lo and (hi <= 0 or ref_capital < hi)
        if in_band:
            return apy, a.get("rateLevel")
    if apylist:                                  # ref_capital beyond all bands → last tier
        try:
            return float(apylist[-1]["currentApy"]), apylist[-1].get("rateLevel")
        except (KeyError, ValueError, TypeError):
            return None
    return None


def collect_rates(cfg) -> tuple[list[Opportunity], list[str]]:
    """Bitget flexible savings APR for cfg.assets (SIGNED, read-only key). Never raises.
    For each coin, considers ALL flexible products and reports the BEST rate applicable
    to cfg.ref_capital (not the misleading small-tier headline). Flags the opportunity
    promotional when the advertised headline is far above the capital-applicable rate.

    LIMITATION (M4-proper TODO): ref_capital is in USD, but tier bands are denominated
    in the COIN. For stablecoins (~1:1) the band match is correct; for BTC/ETH it is
    approximate (would need a spot-price conversion of ref_capital to coin units)."""
    key = getattr(cfg, "bitget_api_key", "")
    secret = getattr(cfg, "bitget_api_secret", "")
    passphrase = getattr(cfg, "bitget_api_passphrase", "")
    if not (key and secret and passphrase):
        return [], ["bitget: no api key/secret/passphrase in .env (skipped)"]
    data, err = _signed_get(PRODUCT, "filter=available_and_held", key, secret, passphrase)
    if err:
        return [], [err]
    ref_capital = float(getattr(cfg, "ref_capital", 0) or 0)
    by_coin: dict = {}
    for p in (data.get("data") or []):
        coin = p.get("coin")
        if coin in cfg.assets and p.get("periodType") == "flexible":
            by_coin.setdefault(coin, []).append(p)
    opps, errors = [], []
    for asset in cfg.assets:
        prods = by_coin.get(asset)
        if not prods:
            continue
        best_apr_pct = None
        best_apylist = None
        headline_pct = None
        for p in prods:
            apylist = p.get("apyList") or []
            for a in apylist:                    # headline = highest advertised tier rate
                try:
                    hv = float(a["currentApy"])
                except (KeyError, ValueError, TypeError):
                    continue
                headline_pct = hv if headline_pct is None else max(headline_pct, hv)
            applic = _applicable_apy(apylist, ref_capital)
            if applic is None:
                continue
            apy_pct, _level = applic
            if best_apr_pct is None or apy_pct > best_apr_pct:
                best_apr_pct, best_apylist = apy_pct, apylist
        if best_apr_pct is None:
            errors.append(f"bitget {asset}: no applicable tier"); continue
        apr = best_apr_pct / 100.0
        tier_info = " / ".join(
            f"L{a.get('rateLevel')}:{a.get('currentApy')}%@[{a.get('minStepVal')}-{a.get('maxStepVal')}]"
            for a in best_apylist)
        promo = (headline_pct is not None
                 and headline_pct >= best_apr_pct * 1.5
                 and (headline_pct - best_apr_pct) / 100.0 > 0.01)
        note = (f"headline {headline_pct:.2f}% applies only to a small first tier; "
                f"{best_apr_pct:.2f}% applies to ref_capital {ref_capital:,.0f}") if promo else None
        opps.append(Opportunity(
            exchange="bitget", category="flexible_earn", asset=asset,
            apr=apr, apr_source="api", apr_is_promotional=promo,
            tier_info=tier_info, subsidy_note=note,
            source_url="https://www.bitget.com/earn", raw_snapshot={"products": prods},
            collected_at=_now_iso()))
    return opps, errors
