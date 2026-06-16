import datetime
from arb_sentinel.models import Opportunity, ACT_NOW, GOOD, WATCH, LOG_ONLY, \
    OK_TIME, TIGHT, TOO_LATE, NO_DEADLINE
from arb_sentinel.engine import net_spread, time_flag, estimate_yield, classify

def _opp(**kw):
    base = dict(exchange="okx", category="flexible_earn", asset="USDC",
                apr=0.06, apr_source="api")
    base.update(kw)
    return Opportunity(**base)

def test_net_spread_own_funds_is_apr():
    assert net_spread(_opp(apr=0.06), 0.0) == 0.06

def test_net_spread_subtracts_borrow():
    assert abs(net_spread(_opp(apr=0.06), 0.017) - 0.043) < 1e-9

def test_net_spread_none_apr():
    assert net_spread(_opp(apr=None)) is None

def test_time_flag_no_deadline(today):
    assert time_flag(_opp(end_date=None), today) == NO_DEADLINE

def test_time_flag_too_late(today):
    o = _opp(end_date=datetime.date(2026, 6, 20), min_hold_days=14)  # 4 days left < 14
    assert time_flag(o, today) == TOO_LATE

def test_time_flag_tight(today):
    o = _opp(end_date=datetime.date(2026, 6, 30), min_hold_days=14)  # 14 left, <14+3
    assert time_flag(o, today) == TIGHT

def test_time_flag_ok(today):
    o = _opp(end_date=datetime.date(2026, 7, 15), min_hold_days=14)  # 29 left
    assert time_flag(o, today) == OK_TIME

def test_classify_act_now(cfg):
    assert classify(0.06, NO_DEADLINE, _opp(), cfg) == ACT_NOW

def test_classify_good(cfg):
    assert classify(0.035, OK_TIME, _opp(), cfg) == GOOD

def test_classify_directional_risk_caps_at_watch(cfg):
    assert classify(0.06, OK_TIME, _opp(directional_risk=True), cfg) == WATCH

def test_classify_too_late_is_log_only(cfg):
    assert classify(0.06, TOO_LATE, _opp(), cfg) == LOG_ONLY

def test_estimate_yield(cfg):
    est = estimate_yield(_opp(apr=0.06), 0.06, cfg)
    # 30000 * 0.06 * 14/365 = 69.04 gross; minus 2x 15 slippage = 39.04 net
    assert est["est_gross"] == 69.04
    assert est["est_net"] == 39.04

def test_classify_directional_risk_plus_too_late_is_log_only(cfg):
    # drop-out (TOO_LATE) takes precedence over the directional-risk cap
    assert classify(0.06, TOO_LATE, _opp(directional_risk=True), cfg) == LOG_ONLY

def test_classify_negative_net_is_log_only(cfg):
    assert classify(-0.01, NO_DEADLINE, _opp(), cfg) == LOG_ONLY
