import datetime, sys
from .collectors import okx
from . import engine, notify
from .state import State


def _today():
    return datetime.date.today()


def run_rates(cfg, state_path="state/state.json", today=None) -> int:
    """Collect OKX rates -> grade -> dedup -> alert actionable. Returns #notifications sent."""
    today = today or _today()
    st = State(state_path)
    opps, errors = okx.collect_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    sent = 0
    for o in opps:
        borrow = 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0)
        net = engine.net_spread(o, borrow)
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        tier = engine.classify(net, flag, o, cfg)
        if st.should_notify(o, tier, cfg):
            est = engine.estimate_yield(o, net, cfg)
            if notify.send_message(notify.format_opportunity(o, net, est, flag, tier, cfg), cfg):
                sent += 1
        st.record(o, tier)
    return sent


def run_digest(cfg, state_path="state/state.json", today=None) -> int:
    """Post a compact baseline rate digest (proves the pipeline; not deduped)."""
    today = today or _today()
    opps, errors = okx.collect_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    graded = []
    for o in opps:
        net = engine.net_spread(o, 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0))
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        graded.append((o, net, engine.classify(net, flag, o, cfg)))
    return 1 if (graded and notify.send_message(notify.format_digest(graded, cfg), cfg)) else 0


def run_test(cfg) -> int:
    return 1 if notify.send_message("✅ 套利哨兵 wiring test → topic OK", cfg) else 0
