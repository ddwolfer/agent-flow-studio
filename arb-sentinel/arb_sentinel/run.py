import datetime, sys, time
from .collectors import okx, binance, bitget, announcements
from . import engine, notify, llm, exits
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


def borrow_rates(cfg):
    """Cheapest borrow APR per asset across exchanges (OKX public + Binance signed).
    Returns {asset: min_apr}. Bitget borrow is a TODO. Never raises."""
    best = {}
    for mod in (okx, binance):
        rates, errs = mod.collect_borrow(cfg)
        for err in errs:
            print(f"[borrow] {err}", file=sys.stderr)
        for asset, r in rates.items():
            if asset not in best or r < best[asset]:
                best[asset] = r
    return best


def run_rates(cfg, state_path=None, today=None) -> int:
    """Collect OKX rates -> grade -> dedup -> alert actionable. Returns #notifications sent."""
    today = today or _today()
    st = State(state_path)
    opps, errors = collect_all_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    borrow_map = {} if cfg.own_funds_mode else borrow_rates(cfg)
    sent = 0
    for o in opps:
        if cfg.own_funds_mode:
            borrow = 0.0
        else:
            borrow = borrow_map.get(o.asset, 0.0)
            o.borrow_apr_same_asset = borrow
        net = engine.net_spread(o, borrow)
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        tier = engine.classify(net, flag, o, cfg)
        if st.should_notify(o, tier, cfg):
            est = engine.estimate_yield(o, net, cfg, today=today)
            if notify.send_message(notify.format_opportunity(o, net, est, flag, tier, cfg), cfg):
                sent += 1
        st.record(o, tier)
    return sent


def run_digest(cfg, state_path=None, today=None) -> int:
    """Post a compact baseline rate digest (proves the pipeline; not deduped)."""
    today = today or _today()
    opps, errors = collect_all_rates(cfg)
    for err in errors:
        print(f"[collect] {err}", file=sys.stderr)
    borrow_map = {} if cfg.own_funds_mode else borrow_rates(cfg)
    graded = []
    for o in opps:
        borrow = 0.0 if cfg.own_funds_mode else borrow_map.get(o.asset, 0.0)
        net = engine.net_spread(o, borrow)
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


def run_announcements(cfg, state_path=None, today=None, max_llm=20, pause=2.5) -> int:
    """Announcement promos. Default = deterministic heads-up (no LLM, zero tokens). Set
    config `announcement_llm: true` to use Groq for quantitative promo parsing instead.

    State divergence between paths: the heads-up path writes only `seen_announcements`;
    the LLM path also writes `seen_opportunities` (tier-graded entries). After switching
    from LLM to heads-up (commit 956056f, 2026-06-22), existing `seen_opportunities`
    entries with the `bitget-promotion-*` / `okx-promotion-*` / `binance-promotion-*`
    prefix freeze at their last LLM-run timestamp by design — not a bug. The stale
    entries remain inert; if you ever flip `announcement_llm` back to true, dedup still
    works because both paths share `seen_announcements`."""
    if getattr(cfg, "announcement_llm", False):
        return _run_announcements_llm(cfg, state_path, today, max_llm, pause)
    return _run_announcements_headsup(cfg, state_path)


def _run_announcements_headsup(cfg, state_path=None, limit=20) -> int:
    """Deterministic promo heads-up — surface NEW promo-looking announcements (no LLM),
    batched into ONE WATCH message so a backlog never spams. Never raises out."""
    st = State(state_path)
    anns, errors = announcements.fetch_all(cfg)
    for err in errors:
        print(f"[ann] {err}", file=sys.stderr)
    fresh = []
    for a in anns:
        exch = a.get("_exchange", "bitget")
        ann_id = a.get("annId")
        if not ann_id:
            continue
        seen_key = f"{exch}:{ann_id}"
        if not st.is_new_announcement(seen_key):
            continue
        title = a.get("annTitle", "")
        is_promo = announcements.looks_like_promo(title, a.get("annType"))
        st.mark_announcement(seen_key, {"exchange": exch, "title": title, "is_promo": is_promo})
        if is_promo:
            fresh.append((exch, title, a.get("annUrl")))
    if not fresh:
        return 0
    return 1 if notify.send_message(notify.format_headsup(fresh, limit=limit), cfg) else 0


def _run_announcements_llm(cfg, state_path=None, today=None, max_llm=20, pause=2.5) -> int:
    """Pull exchange announcements, LLM-extract promo structure for NEW ones, grade,
    and alert actionable promotions. The LLM (Groq) is called only on un-seen
    announcements, so cost is bounded. Returns #notifications sent. Never raises out."""
    today = today or _today()
    st = State(state_path)
    anns, errors = announcements.fetch_all(cfg)
    for err in errors:
        print(f"[ann] {err}", file=sys.stderr)
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sent = 0
    processed = 0                       # bounded LLM calls per run (Groq ~30 req/min)
    for a in anns:
        exch = a.get("_exchange", "bitget")
        ann_id = a.get("annId")
        seen_key = f"{exch}:{ann_id}"
        if not ann_id or not st.is_new_announcement(seen_key):
            continue
        if processed >= max_llm:
            break                       # leave the rest for the next run (NOT marked seen)
        info = llm.extract_promo(a.get("annTitle", ""), a.get("annDesc", ""),
                                 api_key=getattr(cfg, "groq_api_key", "") or None)
        processed += 1
        if pause:
            time.sleep(pause)           # throttle under Groq's rate limit
        if info is None:
            continue                    # LLM failed (e.g. 429) -> DON'T mark seen; retry next run
        st.mark_announcement(seen_key, {"exchange": exch, "title": a.get("annTitle"),
                                        "is_promo": bool(info.get("is_promotion"))})
        if not info.get("is_promotion"):
            continue
        o = Opportunity(
            exchange=exch, category="promotion",
            asset=(info.get("entry_asset") or "?"),
            apr=info.get("apr"), apr_source="announcement", apr_is_promotional=True,
            min_hold_days=int(info.get("min_hold_days") or 0),
            start_date=_parse_date(info.get("start_date")),
            end_date=_parse_date(info.get("end_date")),
            entry_asset_required=info.get("entry_asset"),
            subsidy_note=info.get("subsidy_note"),
            directional_risk=bool(info.get("directional_risk")),
            source_url=a.get("annUrl"), raw_snapshot=a, collected_at=now_iso,
            dedup_key=f"{exch}-promotion-{ann_id}")
        net = engine.net_spread(o, 0.0 if cfg.own_funds_mode else (o.borrow_apr_same_asset or 0.0))
        flag = engine.time_flag(o, today, cfg.default_horizon_days)
        tier = engine.classify(net, flag, o, cfg)
        if st.should_notify(o, tier, cfg):
            est = engine.estimate_yield(o, net, cfg, today=today)
            if notify.send_message(notify.format_opportunity(o, net, est, flag, tier, cfg), cfg):
                sent += 1
        st.record(o, tier)
    return sent


def add_position(pos, state_path=None):
    """Register an entered position so exit detection can watch it. Returns new count."""
    st = State(state_path)
    st.data.setdefault("active_positions", []).append(pos)
    st._save()
    return len(st.data["active_positions"])


def _okx_depeg_prices(cfg, pairs=("USDC-USDT",)):
    """Map {instId: last_price_float} from OKX public tickers. Never raises."""
    opps, errors = okx.collect_depeg(cfg, pairs=pairs)
    for err in errors:
        print(f"[depeg] {err}", file=sys.stderr)
    prices = {}
    for o in opps:
        try:
            prices[o.asset] = float(o.raw_snapshot.get("last"))
        except (AttributeError, ValueError, TypeError):
            pass
    return prices


def run_depeg(cfg, state_path=None, pairs=("USDC-USDT",)) -> int:
    """Alert when a tracked stablecoin pair deviates from 1.0 beyond depeg_bps.
    Light dedup: re-alert only if the deviation grows by >= depeg_bps/2 since last alert."""
    st = State(state_path)
    seen = st.data.setdefault("seen_depeg", {})
    prices = _okx_depeg_prices(cfg, pairs=pairs)
    sent = 0
    for pair, price in prices.items():
        dev_bps = abs(price - 1.0) * 10000
        if dev_bps <= cfg.depeg_bps:
            continue
        prev = seen.get(pair)
        if prev is not None and dev_bps < (abs(prev - 1.0) * 10000) + cfg.depeg_bps / 2:
            continue                      # not materially worse than last alert → skip
        if notify.send_message(f"🚨 脫鉤偵測 | OKX {pair} 現價 {price} 偏離 1.0（{dev_bps:.0f} bps）", cfg):
            sent += 1
        seen[pair] = price
    st._save()
    return sent


def run_exits(cfg, state_path=None, today=None) -> int:
    """Check each active position for the 4 exit triggers (spec §7) and alert."""
    today = today or _today()
    st = State(state_path)
    positions = st.data.get("active_positions", [])
    if not positions:
        return 0
    rate_opps, _err = collect_all_rates(cfg)
    apr_map = {(o.exchange, o.asset): o.apr for o in rate_opps}
    prices = _okx_depeg_prices(cfg)
    sent = 0
    for pos in positions:
        cur = apr_map.get((pos.get("exchange"), pos.get("asset")))
        dprice = None
        for inst, pr in prices.items():
            if pos.get("asset") and pos["asset"] in inst:
                dprice = pr; break
        for msg in exits.check_position(pos, today, cur, dprice, cfg):
            if notify.send_message(msg, cfg):
                sent += 1
    return sent


def run_monitor(cfg, state_path=None, today=None) -> int:
    """Combined position-watch task: de-peg + exit detection."""
    return run_depeg(cfg, state_path) + run_exits(cfg, state_path, today)
