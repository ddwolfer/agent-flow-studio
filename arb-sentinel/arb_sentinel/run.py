import datetime, sys
from .collectors import okx, binance, bitget, announcements
from . import engine, notify, llm
from .models import Opportunity
from .state import State

_COLLECTORS = {"okx": okx, "binance": binance, "bitget": bitget}


def _today():
    return datetime.date.today()


def collect_all_rates(cfg):
    """Collect flexible-earn rates from every exchange in cfg.exchanges. Never raises."""
    opps, errors = [], []
    for ex in cfg.exchanges:
        mod = _COLLECTORS.get(ex)
        if mod is None:
            errors.append(f"unknown exchange '{ex}'"); continue
        o, e = mod.collect_rates(cfg)
        opps.extend(o); errors.extend(e)
    return opps, errors


def run_rates(cfg, state_path="state/state.json", today=None) -> int:
    """Collect OKX rates -> grade -> dedup -> alert actionable. Returns #notifications sent."""
    today = today or _today()
    st = State(state_path)
    opps, errors = collect_all_rates(cfg)
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
    opps, errors = collect_all_rates(cfg)
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


def _parse_date(s):
    try:
        return datetime.date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def run_announcements(cfg, state_path="state/state.json", today=None) -> int:
    """Pull exchange announcements, LLM-extract promo structure for NEW ones, grade,
    and alert actionable promotions. The LLM (Groq) is called only on un-seen
    announcements, so cost is bounded. Returns #notifications sent. Never raises out."""
    today = today or _today()
    st = State(state_path)
    anns, errors = announcements.fetch_bitget()
    for err in errors:
        print(f"[ann] {err}", file=sys.stderr)
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sent = 0
    for a in anns:
        ann_id = a.get("annId")
        if not ann_id or not st.is_new_announcement(ann_id):
            continue
        info = llm.extract_promo(a.get("annTitle", ""), a.get("annDesc", ""),
                                 api_key=getattr(cfg, "groq_api_key", "") or None)
        st.mark_announcement(ann_id, {"title": a.get("annTitle"),
                                      "is_promo": bool(info and info.get("is_promotion"))})
        if not info or not info.get("is_promotion"):
            continue
        o = Opportunity(
            exchange="bitget", category="promotion",
            asset=(info.get("entry_asset") or "?"),
            apr=info.get("apr"), apr_source="announcement", apr_is_promotional=True,
            min_hold_days=int(info.get("min_hold_days") or 0),
            start_date=_parse_date(info.get("start_date")),
            end_date=_parse_date(info.get("end_date")),
            entry_asset_required=info.get("entry_asset"),
            subsidy_note=info.get("subsidy_note"),
            directional_risk=bool(info.get("directional_risk")),
            source_url=a.get("annUrl"), raw_snapshot=a, collected_at=now_iso)
        net = engine.net_spread(o, 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0))
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        tier = engine.classify(net, flag, o, cfg)
        if st.should_notify(o, tier, cfg):
            est = engine.estimate_yield(o, net, cfg)
            if notify.send_message(notify.format_opportunity(o, net, est, flag, tier, cfg), cfg):
                sent += 1
        st.record(o, tier)
    return sent
