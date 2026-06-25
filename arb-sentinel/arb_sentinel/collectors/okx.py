import datetime
from ..models import Opportunity
from . import base

BASE = "https://www.okx.com"
SUMMARY = "/api/v5/finance/savings/lending-rate-summary"
TICKER = "/api/v5/market/ticker"
LOAN_QUOTA = "/api/v5/public/interest-rate-loan-quota"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _okx_envelope_error(data, where: str) -> str | None:
    """OKX v5 wraps every response as {'code', 'msg', 'data'}. HTTP 200 with
    code != '0' is the documented error path (rate limit, geo block, param,
    system unavailable) and `data` is usually [] — i.e. indistinguishable
    from a real empty result unless we check the code. Returns an error
    string when the envelope reports failure, else None."""
    if not isinstance(data, dict):
        return f"okx {where}: unexpected response shape"
    code = data.get("code")
    if str(code) != "0":
        return f"okx {where} code {code}: {data.get('msg')}"
    return None


def collect_rates(cfg) -> tuple[list[Opportunity], list[str]]:
    """OKX public flexible-earn lending rates for cfg.assets. Keyless. Never raises."""
    opps, errors = [], []
    data, err = base.get_json(BASE + SUMMARY)
    if err:
        return [], [err]
    env_err = _okx_envelope_error(data, "rates")
    if env_err:
        return [], [env_err]
    by_ccy = {row.get("ccy"): row for row in (data.get("data") or [])}
    for asset in cfg.assets:
        row = by_ccy.get(asset)
        if not row:
            continue
        try:
            apr = float(row["estRate"])
        except (KeyError, ValueError, TypeError):
            errors.append(f"okx {asset}: bad estRate {row!r}")
            continue
        opps.append(Opportunity(
            exchange="okx", category="flexible_earn", asset=asset,
            apr=apr, apr_source="api",
            source_url="https://www.okx.com/earn/simple-earn",
            raw_snapshot=row, collected_at=_now_iso()))
    return opps, errors


def collect_depeg(cfg, pairs=("USDC-USDT",)) -> tuple[list[Opportunity], list[str]]:
    """OKX public ticker deviation from 1.0 for stablecoin pairs (foundation for M5)."""
    opps, errors = [], []
    for inst in pairs:
        data, err = base.get_json(BASE + TICKER, params={"instId": inst})
        if err:
            errors.append(err); continue
        env_err = _okx_envelope_error(data, f"ticker {inst}")
        if env_err:
            errors.append(env_err); continue
        rows = data.get("data") or []
        if not rows:
            continue
        try:
            last = float(rows[0]["last"])
        except (KeyError, ValueError, TypeError):
            errors.append(f"okx ticker {inst}: bad last"); continue
        opps.append(Opportunity(
            exchange="okx", category="stable_depeg", asset=inst,
            apr=None, apr_source="api",
            subsidy_note=f"last={last}", raw_snapshot=rows[0], collected_at=_now_iso()))
    return opps, errors


def collect_borrow(cfg) -> tuple[dict, list[str]]:
    """OKX public margin borrow rates per asset, annualised (daily rate × 365).
    Keyless. Returns ({asset: borrow_apr}, errors). Never raises."""
    data, err = base.get_json(BASE + LOAN_QUOTA)
    if err:
        return {}, [err]
    env_err = _okx_envelope_error(data, "borrow")
    if env_err:
        return {}, [env_err]
    out = {}
    for row in (data.get("data") or []):
        for b in (row.get("basic") or []):
            ccy = b.get("ccy")
            if ccy in cfg.assets:
                try:
                    out[ccy] = float(b["rate"]) * 365.0
                except (KeyError, ValueError, TypeError):
                    pass
    return out, []
