import datetime
from arb_sentinel.exits import check_position

TODAY = datetime.date(2026, 6, 16)

def _pos(**kw):
    base = dict(exchange="bitget", asset="USDGO", entry_date="2026-06-01",
                min_hold_until="2026-06-30", activity_end_date="2026-06-30",
                entry_price=1.0003, entry_apr=0.12, ref_amount=30000)
    base.update(kw); return base

def test_approaching_end_triggers(cfg):
    msgs = check_position(_pos(activity_end_date="2026-06-17"), TODAY, None, None, cfg)
    assert any("退場提醒" in m for m in msgs)

def test_past_min_hold_triggers(cfg):
    msgs = check_position(_pos(min_hold_until="2026-06-15", activity_end_date=None), TODAY, None, None, cfg)
    assert any("已滿最低持有" in m for m in msgs)

def test_rate_crash_triggers(cfg):
    msgs = check_position(_pos(activity_end_date=None, min_hold_until="2026-12-31"),
                          TODAY, current_apr=0.04, depeg_price=None, cfg=cfg)  # 0.04 < 0.12*0.5
    assert any("利率腰斬" in m for m in msgs)

def test_depeg_triggers(cfg):
    msgs = check_position(_pos(activity_end_date=None, min_hold_until="2026-12-31"),
                          TODAY, current_apr=0.12, depeg_price=0.99, cfg=cfg)  # 100 bps > 30
    assert any("脫鉤" in m for m in msgs)

def test_nothing_triggers_when_healthy(cfg):
    msgs = check_position(_pos(activity_end_date="2026-12-31", min_hold_until="2026-12-31"),
                          TODAY, current_apr=0.12, depeg_price=1.0001, cfg=cfg)
    assert msgs == []

def test_messages_include_exchange_label(cfg):
    msgs = check_position(_pos(exchange="okx", activity_end_date="2026-06-17"), TODAY, None, None, cfg)
    assert msgs and all("OKX USDGO" in m for m in msgs)   # every alert names the exchange
