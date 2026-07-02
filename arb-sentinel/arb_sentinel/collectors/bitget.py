import base64, datetime, hashlib, hmac, time
import httpx
from ..models import Opportunity
from . import base as _base

BASE = "https://api.bitget.com"
PRODUCT = "/api/v2/earn/savings/product"
SPOT_TICKER = "/api/v2/spot/market/tickers"   # keyless, used for ref_capital coin conversion

# carry-guardian endpoints (Slice B, added 2026-07-02). See
# docs/superpowers/specs/carry-smoke-notes.md for live-verified shapes.
LOAN_ORDERS = "/api/v2/earn/loan/ongoing-orders"           # signed
LOAN_HOUR_INTEREST = "/api/v2/earn/loan/public/hour-interest"  # public
SAVINGS_ASSETS = "/api/v2/earn/savings/assets"             # signed
SPOT_ORDERBOOK = "/api/v2/spot/market/orderbook"           # public

# Coins we treat as 1 USD for tier-band conversion. Any non-stable falls back to
# the live spot ticker lookup; if that fails, _spot_usd returns None and band
# matching uses ref_capital as coin units (current legacy behaviour).
_STABLECOINS = {"USDT", "USDC", "DAI", "FDUSD", "TUSD", "PYUSD", "USDE"}


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


def _spot_usd(asset, timeout=10.0):
    """Best-effort coin-to-USD spot price for converting a USD ref_capital into
    coin units before tier-band matching. Stables return 1.0 without a network
    call. Non-stables hit Bitget's keyless spot ticker (BTCUSDT etc.) via
    base.get_json (so transient 5xx / 429 / TransportError go through the
    standard retry-with-backoff envelope rather than failing on the first
    blip). Returns a positive float on success, None on any failure."""
    if asset.upper() in _STABLECOINS:
        return 1.0
    data, err = _base.get_json(BASE + SPOT_TICKER,
                               params={"symbol": f"{asset.upper()}USDT"},
                               timeout=timeout)
    if err or not isinstance(data, dict):
        return None
    if str(data.get("code")) != "00000":
        return None
    rows = data.get("data") or []
    if not rows or not isinstance(rows[0], dict):
        return None
    try:
        px = float(rows[0].get("lastPr") or 0)
    except (ValueError, TypeError):
        return None
    return px if px > 0 else None


def _applicable_apy(apylist, ref_capital, spot_usd=None):
    """currentApy (percent) for the tier whose [minStepVal, maxStepVal) band contains
    ref_capital. Bitget rates are TIERED by amount and DECLINE — the headline first-tier
    rate usually only applies to a tiny band (the spec's 'displayed APR != sustainable APR'
    trap). Returns (apy_pct, rateLevel) or None. With ref_capital<=0 (or band fields
    missing) the open first tier matches.

    Bands are denominated in the COIN; `ref_capital` arrives as USD. When `spot_usd`
    is provided (>0), this converts `ref_capital → ref_capital/spot_usd` for band
    comparison. None or 0 falls back to treating ref_capital as already in coin units
    (correct for stables, conservative — i.e. picks the smallest tier — for non-stables
    when the spot lookup failed)."""
    units = ref_capital / spot_usd if spot_usd and spot_usd > 0 else ref_capital
    for a in apylist:
        try:
            lo = float(a.get("minStepVal") or 0)
            hi = float(a.get("maxStepVal") or 0)
            apy = float(a["currentApy"])
        except (KeyError, ValueError, TypeError):
            continue
        in_band = units >= lo and (hi <= 0 or units < hi)
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

    For non-stable assets, `ref_capital` (USD) is converted to coin units via Bitget's
    keyless spot ticker before tier-band matching — fixes the systematic BTC/ETH APR
    underreporting where USD 30k vs coin-denominated bands always fell into the
    smallest tier."""
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
        spot = _spot_usd(asset)
        if spot is None and asset.upper() not in _STABLECOINS:
            errors.append(f"bitget {asset}: spot lookup failed, tier match may be conservative")
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
            applic = _applicable_apy(apylist, ref_capital, spot_usd=spot)
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


# ── carry-guardian collectors (Slice B) ──────────────────────────────────────
# All 4 functions live-verified 2026-07-02 via scripts/carry-smoke.py.
# See docs/superpowers/specs/carry-smoke-notes.md for shape + unit traps.


def _f(s, default=0.0):
    """Safe float coercion; empty/None/malformed → default."""
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def loan_ongoing_orders(cfg) -> tuple[list[dict], list[str]]:
    """Return active loan orders matching `cfg.carry_loan_order_id`, with
    fields normalised. PERCENT-formatted `pledgeRate` / `supRate` / `forceRate`
    / `hourInterestRate` divided by 100 into decimals so downstream rules can
    compare cleanly against config thresholds. Never raises."""
    key = getattr(cfg, "bitget_api_key", "")
    secret = getattr(cfg, "bitget_api_secret", "")
    passphrase = getattr(cfg, "bitget_api_passphrase", "")
    if not (key and secret and passphrase):
        return [], ["bitget carry: missing api key/secret/passphrase"]
    target_id = str(getattr(cfg, "carry_loan_order_id", "") or "")
    data, err = _signed_get(LOAN_ORDERS, "", key, secret, passphrase)
    if err:
        return [], [err]
    rows = data.get("data") if isinstance(data, dict) else None
    rows = rows if isinstance(rows, list) else []
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        order_id = str(row.get("orderId") or "")
        # If a target id is configured, only surface that one; empty target =
        # take everything (fallback path per spec §8 "空字串 = 自動取第一筆").
        if target_id and order_id != target_id:
            continue
        hour_rate = _f(row.get("hourInterestRate")) / 100.0    # % → decimal
        out.append({
            "order_id": order_id,
            "loan_coin": row.get("loanCoin"),
            "pledge_coin": row.get("pledgeCoin"),
            "loan_amount": _f(row.get("loanAmount")),
            "interest_amount": _f(row.get("interestAmount")),
            "pledge_amount": _f(row.get("pledgeAmount")),
            "ltv": _f(row.get("pledgeRate")) / 100.0,           # % → decimal
            "margin_call_ltv": _f(row.get("supRate")) / 100.0,
            "liquidation_ltv": _f(row.get("forceRate")) / 100.0,
            "hour_rate": hour_rate,
            "annual_rate": hour_rate * 24 * 365,
            "borrow_time_ms": row.get("borrowTime"),
        })
    return out, []


def loan_hour_interest(coin: str, timeout: float = 15.0) -> tuple[dict | None, list[str]]:
    """Public market baseline hourly interest rate for a loanable coin.
    Returned rate is normalised to decimal (per-hour) with annualised
    convenience field. Never raises."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(BASE + LOAN_HOUR_INTEREST, params={"coin": coin})
        if r.status_code != 200:
            return None, [f"bitget hour-interest HTTP {r.status_code}"]
        j = r.json()
        if str(j.get("code")) != "00000":
            return None, [f"bitget hour-interest code {j.get('code')}: {j.get('msg')}"]
        d = j.get("data") or {}
        # `data` observed as a dict for a single-coin query; be defensive
        # if it comes back as a list of coin rows.
        if isinstance(d, list):
            d = next((x for x in d if isinstance(x, dict)
                      and str(x.get("coin") or "").upper() == coin.upper()), {})
        if not isinstance(d, dict):
            return None, ["bitget hour-interest: unexpected shape"]
        hour_rate = _f(d.get("hourInterestRate")) / 100.0
        return {
            "coin": coin,
            "hour_rate": hour_rate,
            "annual_rate": hour_rate * 24 * 365,
        }, []
    except Exception as e:
        return None, [f"bitget hour-interest {type(e).__name__}: {e}"]


def savings_assets(asset: str, cfg) -> tuple[dict | None, list[str]]:
    """Return the caller's holdings of `asset` in Bitget savings:
      {"balance": float, "last_profit": float, "total_profit": float,
       "apy_tiers": [{"level": str, "min": float, "max": float, "apy": float}]}
    or None when the asset has no subscribed product. Never raises.

    live-verified shape 2026-07-02: response is `data.resultList` list of
    per-product dicts with `holdAmount` (balance), `lastProfit` (most-recent
    settlement payout — the killer field for §5.2 audit,
    supersedes the balance-delta workaround in smoke-notes), `totalProfit`
    (accumulated), and `apy` (list of tier bands with currentApy)."""
    key = getattr(cfg, "bitget_api_key", "")
    secret = getattr(cfg, "bitget_api_secret", "")
    passphrase = getattr(cfg, "bitget_api_passphrase", "")
    if not (key and secret and passphrase):
        return None, ["bitget savings: missing api key/secret/passphrase"]
    data, err = _signed_get(SAVINGS_ASSETS, "", key, secret, passphrase)
    if err:
        return None, [err]
    dd = data.get("data") if isinstance(data, dict) else None
    rows = dd if isinstance(dd, list) else \
           (dd.get("resultList") if isinstance(dd, dict) else [])
    total_balance = 0.0
    latest_profit = 0.0
    total_profit = 0.0
    tiers = []
    found = False
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        coin = str(row.get("productCoin") or row.get("coin") or "").upper()
        if coin != asset.upper():
            continue
        found = True
        total_balance += _f(row.get("holdAmount") or row.get("productAmount")
                            or row.get("amount") or 0)
        # Sum lastProfit across products (usually there's just one product
        # per asset, but be defensive).
        latest_profit += _f(row.get("lastProfit") or 0)
        total_profit += _f(row.get("totalProfit") or 0)
        # Take tier bands from the first row we see for this asset.
        if not tiers:
            for a in (row.get("apy") or []):
                if isinstance(a, dict):
                    tiers.append({
                        "level": a.get("rateLevel"),
                        "min": _f(a.get("minApy")),
                        "max": _f(a.get("maxApy")),
                        "apy_percent": _f(a.get("currentApy")),
                    })
    if not found:
        return None, []
    return {
        "asset": asset.upper(),
        "balance": total_balance,
        "last_profit": latest_profit,
        "total_profit": total_profit,
        "apy_tiers": tiers,
    }, []


def spot_orderbook(symbol: str, limit: int = 15,
                   timeout: float = 10.0) -> tuple[dict | None, list[str]]:
    """Public spot orderbook — returns top-of-book + cumulative bid depth.
    Used by carry §5.4 to check USDGO exit liquidity. Never raises."""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.get(BASE + SPOT_ORDERBOOK,
                      params={"symbol": symbol, "limit": limit})
        if r.status_code != 200:
            return None, [f"bitget orderbook HTTP {r.status_code}"]
        j = r.json()
        if str(j.get("code")) != "00000":
            return None, [f"bitget orderbook code {j.get('code')}: {j.get('msg')}"]
        d = j.get("data") or {}
        bids = d.get("bids") or []
        asks = d.get("asks") or []
        bid1_price = _f(bids[0][0]) if bids and len(bids[0]) >= 2 else 0.0
        bid1_qty = _f(bids[0][1]) if bids and len(bids[0]) >= 2 else 0.0
        cum_bid_qty = sum(_f(row[1]) for row in bids
                          if len(row) >= 2)
        ask1_price = _f(asks[0][0]) if asks and len(asks[0]) >= 2 else 0.0
        return {
            "symbol": symbol,
            "bid1_price": bid1_price,
            "bid1_qty": bid1_qty,
            "cum_bid_qty": cum_bid_qty,
            "bid_levels": len(bids),
            "ask1_price": ask1_price,
        }, []
    except Exception as e:
        return None, [f"bitget orderbook {type(e).__name__}: {e}"]
