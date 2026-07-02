"""Tests for arb_sentinel/carry.py — pure rule-engine functions for
Bitget carry-guardian. Follows the exits.py style: pure, never raises,
returns list-of-messages OR structured dicts for the caller to format."""
import types
from arb_sentinel import carry


def _cfg(**kw):
    """Minimal cfg for carry rules. Matches config.yaml `carry:` block."""
    base = dict(
        ltv_watch=0.72, ltv_alert=0.78, ltv_critical=0.82,
        margin_call_ltv=0.85, liquidation_ltv=0.91,
        savings_apr_tiers=[[100000, 0.10], [1000000, 0.065], [None, 0.04]],
        borrow_hour_rate_warn=0.0000057, borrow_hour_rate_alert=0.0000080,
        net_spread_floor=0.02,
        bid_floor_warn=0.9990, bid_floor_critical=0.9970,
        depth_multiple=2.0,
        payout_ratio_floor=0.9,
    )
    base.update(kw)
    return types.SimpleNamespace(**base)


# ── classify_ltv ─────────────────────────────────────────────────────────────
def test_classify_ltv_tiers():
    cfg = _cfg()
    assert carry.classify_ltv(0.60, cfg) == "OK"
    assert carry.classify_ltv(0.72, cfg) == "WATCH"           # boundary
    assert carry.classify_ltv(0.77, cfg) == "WATCH"
    assert carry.classify_ltv(0.78, cfg) == "ALERT"           # boundary
    assert carry.classify_ltv(0.81, cfg) == "ALERT"
    assert carry.classify_ltv(0.82, cfg) == "CRITICAL"         # boundary
    assert carry.classify_ltv(0.95, cfg) == "CRITICAL"


# ── escape_hatch (BTC price at critical thresholds) ──────────────────────────
def test_escape_hatch_computes_btc_prices():
    # LTV = debt / (collateral × price). Price at target ltv = debt / (ltv × col).
    # Given debt 21580 USDC, collateral 0.56571 BTC, current price ≈ 60_465 USD.
    hatch = carry.escape_hatch(
        loan_amount=21580.39, pledge_amount=0.56571,
        current_ltv=0.6171, margin_call_ltv=0.85, liquidation_ltv=0.91)
    # Current price ≈ 21580.39 / (0.6171 × 0.56571) ≈ 61,822
    assert abs(hatch["btc_price_now"] - 21580.39 / (0.6171 * 0.56571)) < 1
    # Price at margin call = 21580.39 / (0.85 × 0.56571)
    assert abs(hatch["price_at_margin_call"] - 21580.39 / (0.85 * 0.56571)) < 1
    # Distance from current to margin call as fraction (drop %)
    assert 0 < hatch["pct_to_margin_call"] < 1
    assert hatch["pct_to_margin_call"] < hatch["pct_to_liquidation"]


# ── expected_daily_payout via APR tiers ──────────────────────────────────────
def test_expected_daily_payout_first_tier_only():
    # Balance 24,604 fully in first tier (10%): expected ~6.74/day
    tiers = [[100000, 0.10], [1000000, 0.065], [None, 0.04]]
    exp = carry.expected_daily_payout(balance=24604.61, tiers=tiers)
    # 24604.61 × 0.10 / 365 = 6.741...
    assert abs(exp - 24604.61 * 0.10 / 365) < 1e-3


def test_expected_daily_payout_spans_two_tiers():
    # Balance 150k → 100k @ 10% + 50k @ 6.5%
    tiers = [[100000, 0.10], [1000000, 0.065], [None, 0.04]]
    exp = carry.expected_daily_payout(balance=150000, tiers=tiers)
    # (100000 × 0.10 + 50000 × 0.065) / 365 = (10000 + 3250) / 365 = 36.30
    assert abs(exp - (100000 * 0.10 + 50000 * 0.065) / 365) < 1e-3


def test_expected_daily_payout_null_tier_uppermost():
    # 5M → 100k @ 10 + 900k @ 6.5 + 4M @ 4
    tiers = [[100000, 0.10], [1000000, 0.065], [None, 0.04]]
    exp = carry.expected_daily_payout(balance=5_000_000, tiers=tiers)
    assert abs(exp - (100000*0.10 + 900000*0.065 + 4_000_000*0.04) / 365) < 1e-3


# ── audit_payout (via totalProfit delta) ─────────────────────────────────────
def test_audit_payout_healthy():
    cfg = _cfg()
    tiers = [[100000, 0.10], [1000000, 0.065], [None, 0.04]]
    # Delta = 6.5 vs expected 6.74 (24604 × 10% / 365) → ratio 0.964 > floor 0.9 → OK
    result = carry.audit_payout(
        today_total_profit=15.7, yesterday_total_profit=9.2,
        balance=24604.61, tiers=tiers, floor_ratio=cfg.payout_ratio_floor)
    assert result["level"] == "OK"
    assert abs(result["actual"] - 6.5) < 1e-6
    assert result["ratio"] > 0.9


def test_audit_payout_degraded_warns():
    cfg = _cfg()
    tiers = [[100000, 0.10], [None, 0.04]]
    # Delta = 3.0 vs expected 6.74 → ratio 0.45 → WARN
    result = carry.audit_payout(
        today_total_profit=12.2, yesterday_total_profit=9.2,
        balance=24604.61, tiers=tiers, floor_ratio=cfg.payout_ratio_floor)
    assert result["level"] == "WARN"
    assert result["ratio"] < 0.5


def test_audit_payout_zero_is_critical():
    cfg = _cfg()
    tiers = [[100000, 0.10], [None, 0.04]]
    # No delta at all → CRITICAL (payout gone)
    result = carry.audit_payout(
        today_total_profit=9.2, yesterday_total_profit=9.2,
        balance=24604.61, tiers=tiers, floor_ratio=cfg.payout_ratio_floor)
    assert result["level"] == "CRITICAL"
    assert result["actual"] == 0.0


def test_audit_payout_no_yesterday_snapshot_returns_unknown():
    # Fresh install: no prior snapshot → skip audit rather than false-positive
    result = carry.audit_payout(
        today_total_profit=9.2, yesterday_total_profit=None,
        balance=24604.61, tiers=[[100000, 0.10]], floor_ratio=0.9)
    assert result["level"] == "UNKNOWN"


# ── evaluate_borrow_rate ──────────────────────────────────────────────────────
def test_evaluate_borrow_rate_healthy():
    cfg = _cfg()
    # 0.000313% per hour → decimal 0.00000313; well under warn 0.0000057
    level, _ = carry.evaluate_borrow_rate(hour_rate=0.00000313,
                                           savings_apr=0.10, cfg=cfg)
    assert level == "OK"


def test_evaluate_borrow_rate_warn_when_rising():
    cfg = _cfg()
    level, _ = carry.evaluate_borrow_rate(hour_rate=0.0000060,
                                           savings_apr=0.10, cfg=cfg)
    assert level == "WARN"


def test_evaluate_borrow_rate_alert_when_high():
    cfg = _cfg()
    level, _ = carry.evaluate_borrow_rate(hour_rate=0.0000085,
                                           savings_apr=0.10, cfg=cfg)
    assert level == "ALERT"


def test_evaluate_borrow_rate_alert_when_net_spread_thin():
    # Rate fine but spread thin → still ALERT
    cfg = _cfg(net_spread_floor=0.02)
    level, reason = carry.evaluate_borrow_rate(
        hour_rate=0.00000313, savings_apr=0.03, cfg=cfg)
    assert level == "ALERT"
    assert "利差" in reason or "spread" in reason.lower()


# ── evaluate_depth ────────────────────────────────────────────────────────────
def test_evaluate_depth_healthy():
    cfg = _cfg()
    level, _ = carry.evaluate_depth(
        bid1_price=1.0002, cum_bid_qty=1_500_000,
        position_size=24_600, cfg=cfg)
    assert level == "OK"


def test_evaluate_depth_warn_thin():
    cfg = _cfg(depth_multiple=2.0)
    level, _ = carry.evaluate_depth(
        bid1_price=1.0002, cum_bid_qty=40_000,
        position_size=24_600, cfg=cfg)
    assert level == "WARN"


def test_evaluate_depth_warn_bid_slipping():
    cfg = _cfg()
    level, _ = carry.evaluate_depth(
        bid1_price=0.9985, cum_bid_qty=1_500_000,
        position_size=24_600, cfg=cfg)
    assert level == "WARN"


def test_evaluate_depth_critical_depeg():
    cfg = _cfg()
    level, _ = carry.evaluate_depth(
        bid1_price=0.9960, cum_bid_qty=1_500_000,
        position_size=24_600, cfg=cfg)
    assert level == "CRITICAL"


# ── evaluate_immediate (plan A: only 🔴 CRITICAL + system health) ────────────
def test_evaluate_immediate_silent_when_ltv_ok():
    cfg = _cfg()
    order = {"ltv": 0.6171, "loan_amount": 21580.39, "pledge_amount": 0.56571,
             "margin_call_ltv": 0.85, "liquidation_ltv": 0.91}
    msgs = carry.evaluate_immediate(orders=[order], api_fail_count=0, cfg=cfg)
    assert msgs == []           # Plan A: no push below CRITICAL


def test_evaluate_immediate_silent_at_watch_and_alert():
    cfg = _cfg()
    for ltv in (0.72, 0.79):
        order = {"ltv": ltv, "loan_amount": 21580, "pledge_amount": 0.56571,
                 "margin_call_ltv": 0.85, "liquidation_ltv": 0.91}
        msgs = carry.evaluate_immediate(orders=[order], api_fail_count=0, cfg=cfg)
        assert msgs == [], f"WATCH/ALERT should be silent, got: {msgs}"


def test_evaluate_immediate_fires_critical():
    cfg = _cfg()
    order = {"ltv": 0.83, "loan_amount": 21580.39, "pledge_amount": 0.56571,
             "margin_call_ltv": 0.85, "liquidation_ltv": 0.91}
    msgs = carry.evaluate_immediate(orders=[order], api_fail_count=0, cfg=cfg)
    assert len(msgs) == 1
    m = msgs[0]
    assert "🔴" in m and "CRITICAL" in m
    assert "BITGET" in m         # exchange labelled per memory rule
    assert "83" in m              # LTV shown
    # BTC price hatch shown
    assert "$" in m or "BTC" in m


def test_evaluate_immediate_fires_when_orders_disappear():
    # 訂單消失 = liquidated or repaid — needs manual action either way
    cfg = _cfg()
    msgs = carry.evaluate_immediate(orders=[], api_fail_count=0, cfg=cfg)
    assert len(msgs) == 1
    assert "訂單消失" in msgs[0] or "訂單" in msgs[0]
    assert "BITGET" in msgs[0]


def test_evaluate_immediate_fires_on_3_consecutive_api_fails():
    cfg = _cfg()
    # api_fail_count is a state-carried counter incremented by run.py on
    # consecutive collector failures. carry.py just checks the threshold.
    msgs = carry.evaluate_immediate(orders=[], api_fail_count=3, cfg=cfg)
    # Both "訂單消失" (empty orders) AND "風控失明" (fails=3) — but the
    # blindness alert takes precedence since it's about not being able to
    # trust the empty-orders signal at all
    assert any("風控失明" in m or "失明" in m for m in msgs)


def test_evaluate_immediate_low_api_fail_count_ignored():
    cfg = _cfg()
    order = {"ltv": 0.60, "loan_amount": 21580, "pledge_amount": 0.56571,
             "margin_call_ltv": 0.85, "liquidation_ltv": 0.91}
    msgs = carry.evaluate_immediate(orders=[order], api_fail_count=2, cfg=cfg)
    assert msgs == []               # threshold is 3
