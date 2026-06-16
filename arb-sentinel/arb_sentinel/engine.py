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


def estimate_yield(o: Opportunity, net: float | None, cfg) -> dict:
    """Reference-capital projection (spec 5.3). Returns {} if net is None."""
    if net is None:
        return {}
    holding_days = max(o.min_hold_days, cfg.default_horizon_days)
    est_gross = cfg.ref_capital * net * holding_days / 365
    entry_slip = cfg.ref_capital * cfg.entry_slippage_assumption
    # subsidy covering exit -> no exit slippage; else symmetric to entry
    exit_slip = 0.0 if (o.subsidy_note and "exit" in o.subsidy_note.lower()) else entry_slip
    return {
        "holding_days": holding_days,
        "est_gross": round(est_gross, 2),
        "est_net": round(est_gross - entry_slip - exit_slip, 2),
    }


def classify(net: float | None, flag: str, o: Opportunity, cfg) -> str:
    """Grade (spec 5.4). Order matters: drop-outs first, then risk caps, then
    positive grades. directional_risk (dual-invest) and TIGHT timing cap at WATCH
    — they must never auto-act, even with a high net."""
    time_ok = flag in (OK_TIME, NO_DEADLINE)
    if net is None or flag == TOO_LATE:
        return LOG_ONLY
    if o.directional_risk or flag == TIGHT:
        return WATCH
    if net >= cfg.threshold_high and time_ok:
        return ACT_NOW
    if net >= cfg.threshold_mid and time_ok:
        return GOOD
    if net >= cfg.threshold_mid * 0.5:
        return WATCH
    return LOG_ONLY
