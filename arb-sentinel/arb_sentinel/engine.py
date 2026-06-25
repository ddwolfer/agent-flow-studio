from datetime import date
from .models import (Opportunity, ACT_NOW, GOOD, WATCH, LOG_ONLY,
                     OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE)


def net_spread(o: Opportunity, best_borrow_apr: float = 0.0) -> float | None:
    """apr - cheapest borrow cost for the asset. own-funds mode -> best_borrow_apr=0."""
    if o.apr is None:
        return None
    return o.apr - (best_borrow_apr or 0.0)


def time_flag(o: Opportunity, today: date, default_horizon_days: int = 14) -> str:
    if o.end_date is None:
        return NO_DEADLINE
    days_left = (o.end_date - today).days
    if days_left < o.min_hold_days:
        return TOO_LATE
    if days_left < o.min_hold_days + 3:
        return TIGHT
    return OK_TIME


def estimate_yield(o: Opportunity, net: float | None, cfg, today: date | None = None) -> dict:
    """Reference-capital projection (spec 5.3). Returns {} if net is None.

    Holding-days cap: when the opportunity has an end_date and that date is
    closer than cfg.default_horizon_days, the projection must NOT linear-
    extrapolate the full horizon — a 14-day extrapolation on a 5-day promo
    overstates est_net by ~3x. min_hold_days still dominates because the
    engine cannot show a duration shorter than the protocol's own lock."""
    if net is None:
        return {}
    horizon = cfg.default_horizon_days
    if o.end_date is not None:
        if today is None:
            today = date.today()
        days_to_end = (o.end_date - today).days
        if days_to_end > 0:
            horizon = min(horizon, days_to_end)
    holding_days = max(o.min_hold_days, horizon)
    est_gross = cfg.ref_capital * net * holding_days / 365
    entry_slip = cfg.ref_capital * cfg.entry_slippage_assumption
    # subsidy covering exit -> no exit slippage; else symmetric to entry.
    # Match EN + ZH exit/redeem terms (the LLM emits Chinese subsidy notes).
    note = (o.subsidy_note or "").lower()
    covers_exit = any(t in note for t in ("exit", "redeem", "出場", "出场", "兌回", "兑回", "贖回", "赎回"))
    exit_slip = 0.0 if covers_exit else entry_slip
    return {
        "holding_days": holding_days,
        "est_gross": round(est_gross, 2),
        "est_net": round(est_gross - entry_slip - exit_slip, 2),
    }


def classify(net: float | None, flag: str, o: Opportunity, cfg) -> str:
    """Grade (spec 5.4). Order matters: drop-outs first, then magnitude-based
    base grade, then risk CAPS the result downward. directional_risk and TIGHT
    timing CAP at WATCH — they must never auto-act even with a high net, but
    they also must never UPGRADE a negative-spread or sub-threshold opportunity
    out of LOG_ONLY (the previous implementation did exactly that)."""
    time_ok = flag in (OK_TIME, NO_DEADLINE)
    if net is None or flag == TOO_LATE:
        return LOG_ONLY
    if net >= cfg.threshold_high and time_ok:
        base = ACT_NOW
    elif net >= cfg.threshold_mid and time_ok:
        base = GOOD
    elif net >= cfg.threshold_mid * 0.5:
        base = WATCH
    else:
        base = LOG_ONLY
    if base == LOG_ONLY:
        return LOG_ONLY
    if o.directional_risk or flag == TIGHT:
        return WATCH
    return base
