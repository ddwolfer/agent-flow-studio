"""Integration tests for run.run_carry / run.run_carry_digest.

Mock the collector functions + notify.send_message; verify state persistence,
alert routing to TELEGRAM_TOPIC_CARRY, and digest builder wiring."""
import datetime
import types
from arb_sentinel import run as run_mod
from arb_sentinel.state import State


def _cfg(**kw):
    base = dict(
        telegram_bot_token="x", telegram_chat_id="-100",
        telegram_topic_arb="1390",
        telegram_topic_carry="1521",       # NEW — dedicated carry topic
        # carry rules (same as test_carry.py's fixture)
        ltv_watch=0.72, ltv_alert=0.78, ltv_critical=0.82,
        margin_call_ltv=0.85, liquidation_ltv=0.91,
        savings_apr_tiers=[[100000, 0.10], [1000000, 0.065], [None, 0.04]],
        borrow_hour_rate_warn=0.0000057, borrow_hour_rate_alert=0.0000080,
        net_spread_floor=0.02,
        bid_floor_warn=0.9990, bid_floor_critical=0.9970,
        depth_multiple=2.0,
        payout_ratio_floor=0.9,
        carry_loan_order_id="1454384882276573190",
        carry_loan_coin="USDC",
        carry_earn_asset="USDGO",
        carry_pair="USDGOUSDC",
    )
    base.update(kw)
    return types.SimpleNamespace(**base)


def _sample_order(ltv=0.6171):
    return {"order_id": "1454384882276573190", "loan_coin": "USDC",
            "pledge_coin": "BTC", "loan_amount": 21580.39,
            "interest_amount": 0.7163, "pledge_amount": 0.56571,
            "ltv": ltv, "margin_call_ltv": 0.85, "liquidation_ltv": 0.91,
            "hour_rate": 0.00000313, "annual_rate": 0.02742,
            "borrow_time_ms": "1782478297775"}


def _sample_savings():
    return {"asset": "USDGO", "balance": 24604.61, "last_profit": 0.84,
            "total_profit": 15.70,
            "apy_tiers": [{"level": "1", "min": 0, "max": 100000,
                           "apy_percent": 10.00}]}


def _sample_book():
    return {"symbol": "USDGOUSDC", "bid1_price": 1.0002, "bid1_qty": 500,
            "cum_bid_qty": 1_500_000, "bid_levels": 15,
            "ask1_price": 1.0004}


# ── run_carry immediate path ────────────────────────────────────────────────
def test_run_carry_silent_when_healthy(monkeypatch, tmp_path):
    """LTV OK, orders present — no push (Plan A)."""
    cfg = _cfg()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([_sample_order(ltv=0.6171)], []))
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (_sample_savings(), []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (_sample_book(), []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append((text, kw)) or True)
    n = run_mod.run_carry(cfg, state_path=tmp_path / "s.json")
    assert n == 0 and sent == []


def test_run_carry_fires_critical_to_carry_topic(monkeypatch, tmp_path):
    """LTV 83% → 🔴 CRITICAL push to TELEGRAM_TOPIC_CARRY (1521), not _ARB."""
    cfg = _cfg()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([_sample_order(ltv=0.83)], []))
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (_sample_savings(), []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (_sample_book(), []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append((text, kw)) or True)
    n = run_mod.run_carry(cfg, state_path=tmp_path / "s.json")
    assert n == 1 and len(sent) == 1
    text, kw = sent[0]
    assert "🔴" in text and "CRITICAL" in text
    assert kw.get("topic") == "1521"           # routed to carry topic
    # Second tick: LTV still critical → fires AGAIN (spec §5.1 no dedup)
    n2 = run_mod.run_carry(cfg, state_path=tmp_path / "s.json")
    assert n2 == 1 and len(sent) == 2


def test_run_carry_increments_api_fail_count(monkeypatch, tmp_path):
    """Consecutive fetch failures build up; 3rd fires 風控失明."""
    cfg = _cfg()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([], ["connect error"]))
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (None, ["err"]))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (None, ["err"]))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append(text) or True)
    state_path = tmp_path / "s.json"
    # Tick 1: fail_count 1 → silent
    n1 = run_mod.run_carry(cfg, state_path=state_path)
    assert n1 == 0 and sent == []
    # Tick 2: fail_count 2 → still silent
    n2 = run_mod.run_carry(cfg, state_path=state_path)
    assert n2 == 0 and sent == []
    # Tick 3: fail_count 3 → 風控失明 alerts
    n3 = run_mod.run_carry(cfg, state_path=state_path)
    assert n3 == 1 and len(sent) == 1
    assert "風控失明" in sent[0]
    # Tick 4: recovery (success) → fail_count resets to 0, silent again
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([_sample_order(ltv=0.60)], []))
    n4 = run_mod.run_carry(cfg, state_path=state_path)
    assert n4 == 0            # silent recovery


def test_run_carry_tracks_ltv_24h_high(monkeypatch, tmp_path):
    """State should record max LTV seen so digest can surface the peak."""
    cfg = _cfg()
    seq = iter([0.61, 0.68, 0.63, 0.71, 0.62])
    def mock_orders(cfg):
        return [_sample_order(ltv=next(seq))], []
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders", mock_orders)
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (_sample_savings(), []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (_sample_book(), []))
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: True)
    state_path = tmp_path / "s.json"
    for _ in range(5):
        run_mod.run_carry(cfg, state_path=state_path)
    st = State(state_path)
    assert abs(st.data.get("carry_ltv_24h_high", 0) - 0.71) < 1e-9


# ── run_carry_digest ────────────────────────────────────────────────────────
def test_run_carry_digest_sends_to_carry_topic(monkeypatch, tmp_path):
    cfg = _cfg()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([_sample_order(ltv=0.61)], []))
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (_sample_savings(), []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (_sample_book(), []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append((text, kw)) or True)
    n = run_mod.run_carry_digest(cfg, state_path=tmp_path / "s.json")
    assert n == 1 and len(sent) == 1
    text, kw = sent[0]
    assert "Carry 日報" in text
    assert kw.get("topic") == "1521"
    # After the digest fires it snapshots today's totals for tomorrow's audit
    st = State(tmp_path / "s.json")
    snap = st.data.get("carry_last_digest_snapshot") or {}
    assert abs(snap.get("total_profit", 0) - 15.70) < 1e-6


def test_run_carry_digest_second_day_shows_delta(monkeypatch, tmp_path):
    """After yesterday's snapshot exists, today's audit uses delta."""
    cfg = _cfg()
    state_path = tmp_path / "s.json"
    # Seed yesterday's snapshot
    st0 = State(state_path)
    st0.data["carry_last_digest_snapshot"] = {"total_profit": 9.2}
    st0._save()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([_sample_order(ltv=0.61)], []))
    # totalProfit rose by 6.5 since yesterday → ~healthy vs 6.74 expected
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (_sample_savings(), []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (_sample_book(), []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append(text) or True)
    n = run_mod.run_carry_digest(cfg, state_path=state_path)
    assert n == 1
    msg = sent[0]
    # Digest now contains actual vs expected — the delta 6.5 shows up
    assert "6.5" in msg or "6.50" in msg


def test_run_carry_digest_silent_on_no_position(monkeypatch, tmp_path):
    """No active loan → digest still fires (heartbeat!), but body says
    '無 carry 部位'."""
    cfg = _cfg()
    monkeypatch.setattr(run_mod.bitget, "loan_ongoing_orders",
                        lambda cfg: ([], []))
    monkeypatch.setattr(run_mod.bitget, "savings_assets",
                        lambda asset, cfg: (None, []))
    monkeypatch.setattr(run_mod.bitget, "spot_orderbook",
                        lambda symbol, limit=15: (None, []))
    sent = []
    monkeypatch.setattr(run_mod.notify, "send_message",
                        lambda text, cfg, **kw: sent.append(text) or True)
    n = run_mod.run_carry_digest(cfg, state_path=tmp_path / "s.json")
    assert n == 1              # digest fires even without position (heartbeat)
    assert "無 carry 部位" in sent[0] or "無部位" in sent[0] or "無" in sent[0]
