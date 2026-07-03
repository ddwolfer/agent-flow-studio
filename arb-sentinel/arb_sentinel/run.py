import datetime, os, sys, time
from .collectors import okx, binance, bitget, announcements, bitget_events
from . import engine, notify, llm, exits, carry
from .models import Opportunity
from .state import State

# Sanity cap on apr-from-LLM: belt-and-braces against prompt-injection that
# escapes the delimiter guard. 200% APR is an honest upper bound for any real
# crypto promo; anything past it gets clamped to None so engine.classify can't
# auto-grade ACT_NOW on a hallucinated/manipulated number.
_LLM_APR_SANITY_CAP = 2.0   # 200%

_COLLECTORS = {"okx": okx, "binance": binance, "bitget": bitget}


def _today():
    """Today as a UTC date. Announcement end_dates and exchange `cTime` /
    `pTime` are all UTC; mixing with the host-local `date.today()` causes a
    1-day boundary flip near UTC midnight for TPE/JST hosts (TOO_LATE vs
    TIGHT vs OK_TIME swap for the same opportunity)."""
    return datetime.datetime.now(datetime.timezone.utc).date()


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
    works because both paths share `seen_announcements`.

    Resilience: if announcement_llm is true but GROQ_API_KEY is empty, falls
    through to the heads-up path instead of burning per-run sleep budget on
    silent no-op LLM calls."""
    if getattr(cfg, "announcement_llm", False):
        if not (getattr(cfg, "groq_api_key", "") or os.environ.get("GROQ_API_KEY", "")):
            print("[ann] announcement_llm=true but GROQ_API_KEY missing — "
                  "falling back to heads-up path", file=sys.stderr)
        else:
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
            # Best-effort 繁中 translation via Groq. Returns None when the
            # title is already CJK, GROQ_API_KEY is unset, or Groq is down —
            # heads-up still fires with just the original title in that case.
            translated = llm.translate_title(
                title, api_key=getattr(cfg, "groq_api_key", "") or None)
            fresh.append((exch, title, a.get("annUrl"), translated))
    sent = 0
    if fresh:
        sent += 1 if notify.send_message(notify.format_headsup(fresh, limit=limit), cfg) else 0
    sent += _run_bitget_events_check(cfg, st)
    return sent


def _run_bitget_events_check(cfg, st) -> int:
    """Bitget PoolX + Launchpool — fire a heads-up when NEW project IDs
    appear. Uses the real keyless XHR endpoints captured 2026-06-30
    (/v1/finance/{poolx,launchpool}/product/count + /list); replaces the
    earlier SSR scraper that always saw the static (0)/(0) placeholder.

    State shape: `state["bitget_events_seen"][page] = {project_ids: [str, ...]}`.
    A project ending and disappearing from the running list silently updates
    state — no alert. A new ID (or a count rise when /list errors so we can't
    name the project) fires. Never raises out."""
    items, errors = bitget_events.fetch_event_status()
    for err in errors:
        print(f"[bitget-events] {err}", file=sys.stderr)
    if not items:
        return 0
    seen = st.data.setdefault("bitget_events_seen", {})
    fresh_per_page = []                        # [(page, url, [new_project, ...], count_delta)]
    for it in items:
        page = it["page"]
        cur_ids = [p["id"] for p in it.get("projects", []) if p.get("id")]
        prev = seen.get(page, {})
        prev_ids = set(prev.get("project_ids") or [])
        cur_id_set = set(cur_ids)
        # Genuinely new projects since last poll.
        added_ids = cur_id_set - prev_ids
        new_projects = [p for p in it.get("projects", [])
                        if p.get("id") in added_ids]
        # Edge case: /list errored so projects=[] but count went up — still
        # surface a "N new" alert without names.
        prev_count = int(prev.get("running_num", 0))
        count_delta = it["running_num"] - prev_count
        if new_projects:
            fresh_per_page.append((page, it["url"], new_projects, None))
        elif count_delta > 0 and not it.get("projects"):
            fresh_per_page.append((page, it["url"], [], count_delta))
        seen[page] = {
            "running_num": it["running_num"],
            "wait_start_num": it["wait_start_num"],
            "project_ids": cur_ids,
        }
    st._save()
    if not fresh_per_page:
        return 0
    return 1 if notify.send_message(
        notify.format_bitget_events(fresh_per_page), cfg) else 0


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
    # Dedup BEFORE the LLM loop: an article in multiple Binance catalogs
    # (e.g. a HODLer Airdrop indexed in both 128 and 49) would otherwise
    # burn one Groq call per duplicate. (exch, annId) is the canonical key
    # also used by seen_announcements downstream, so this dedup is safe.
    seen_keys = set()
    candidates = []
    for a in anns:
        ann_id = a.get("annId")
        if not ann_id:
            continue
        key = f"{a.get('_exchange', 'bitget')}:{ann_id}"
        if key in seen_keys or not st.is_new_announcement(key):
            continue
        seen_keys.add(key)
        candidates.append(a)
    for idx, a in enumerate(candidates):
        exch = a.get("_exchange", "bitget")
        ann_id = a.get("annId")
        seen_key = f"{exch}:{ann_id}"
        if processed >= max_llm:
            break                       # leave the rest for the next run (NOT marked seen)
        info = llm.extract_promo(a.get("annTitle", ""), a.get("annDesc", ""),
                                 api_key=getattr(cfg, "groq_api_key", "") or None)
        # Distinguish "transient/parse failure" (None — retry next run, no sleep,
        # no budget burn) from "rate-limited" / "model decommissioned" sentinels
        # (break the budget loop — every subsequent call is a guaranteed waste).
        if info == llm.RATE_LIMITED:
            print("[ann] groq 429 — breaking budget loop, retry next run",
                  file=sys.stderr)
            break
        if info == llm.MODEL_DECOMMISSIONED:
            print("[ann] groq model decommissioned — falling back to heads-up "
                  "and stopping LLM path for this run", file=sys.stderr)
            # Carry over any Telegram alerts we already sent in this loop;
            # otherwise the launchd journal undercounts when decommission
            # fires after the first few successful extractions.
            return sent + _run_announcements_headsup(cfg, state_path)
        processed += 1
        # Sleep AFTER the call, only when more work remains and we haven't
        # already used the budget — saves ~pause × 2 wasted seconds per run.
        more_work_remaining = (idx < len(candidates) - 1) and (processed < max_llm)
        if pause and more_work_remaining and info is not None:
            time.sleep(pause)           # throttle under Groq's rate limit
        if info is None:
            continue                    # transient failure -> DON'T mark seen; retry next run
        st.mark_announcement(seen_key, {"exchange": exch, "title": a.get("annTitle"),
                                        "is_promo": bool(info.get("is_promotion"))})
        if not info.get("is_promotion"):
            continue
        # Sanity cap apr in case prompt-injection escapes llm.py's delimiter
        # guard. Anything > 200% is implausible for a real crypto promo;
        # clamp to None so engine.classify can't auto-grade ACT_NOW on it.
        apr_raw = info.get("apr")
        apr = apr_raw if (apr_raw is None or 0 <= apr_raw <= _LLM_APR_SANITY_CAP) else None
        if apr_raw is not None and apr is None:
            print(f"[ann] llm returned implausible apr {apr_raw} on '{a.get('annTitle')!r}'"
                  f" — clamped to None", file=sys.stderr)
        o = Opportunity(
            exchange=exch, category="promotion",
            asset=(info.get("entry_asset") or "?"),
            apr=apr, apr_source="announcement", apr_is_promotional=True,
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


# ── carry-guardian tasks (Slice D) ───────────────────────────────────────────
# Wired via __main__ --task carry / --task carry-digest.
# All alerts route to TELEGRAM_TOPIC_CARRY (topic 1521), not the arb topic.


def _carry_topic(cfg):
    """Resolve carry topic env → cfg.telegram_topic_carry, with default None
    that makes send_message fail-closed and log the misconfig."""
    return getattr(cfg, "telegram_topic_carry", "") or None


def run_carry(cfg, state_path=None) -> int:
    """5-min tick: fetch position + savings + orderbook, evaluate immediate
    rules (Plan A: 🔴 CRITICAL LTV + system health only), update state
    trackers (24h LTV high, api_fail_count). Never raises out."""
    st = State(state_path)
    orders, order_errs = bitget.loan_ongoing_orders(cfg)
    for err in order_errs:
        print(f"[carry] {err}", file=sys.stderr)
    # api_fail_count: increments on any error touching the orders endpoint;
    # resets to 0 on any success (empty list AS a success is OK — that's the
    # "訂單消失" case, handled by evaluate_immediate).
    fail_count = int(st.data.get("carry_api_fail_count") or 0)
    if order_errs:
        fail_count += 1
    else:
        fail_count = 0
    st.data["carry_api_fail_count"] = fail_count
    # Track 24h LTV high across ticks (reset after digest by run_carry_digest)
    high = float(st.data.get("carry_ltv_24h_high") or 0.0)
    for o in orders:
        cur = float(o.get("ltv") or 0.0)
        if cur > high:
            high = cur
    st.data["carry_ltv_24h_high"] = high
    st._save()
    msgs = carry.evaluate_immediate(orders=orders, api_fail_count=fail_count,
                                     cfg=cfg,
                                     orders_valid=(not order_errs))
    if not msgs:
        return 0
    topic = _carry_topic(cfg)
    sent = 0
    for msg in msgs:
        if notify.send_message(msg, cfg, topic=topic):
            sent += 1
    return sent


def run_carry_digest(cfg, state_path=None) -> int:
    """08:00 daily digest — one message. Fires ALWAYS (heartbeat contract) —
    even if position is closed, so the user knows the monitor is alive.

    Slice G (2026-07-03): stopped writing carry_last_digest_snapshot. The
    delta-based payout audit was noisy when the user manually redeemed
    USDGO to repay interest, and Bitget's live apy_tiers is a cleaner
    silent-APR-cut detector. Still resets ltv_24h_high after send.

    The `carry_last_digest_snapshot` key remains in state.json for
    installs that predate this slice (harmless dead data)."""
    st = State(state_path)
    orders, _ = bitget.loan_ongoing_orders(cfg)
    savings_asset = getattr(cfg, "carry_earn_asset", "USDGO")
    savings, _ = bitget.savings_assets(savings_asset, cfg)
    pair = getattr(cfg, "carry_pair", f"{savings_asset}USDC")
    book, _ = bitget.spot_orderbook(pair, limit=15)
    ltv_24h_high = st.data.get("carry_ltv_24h_high")
    data = carry.build_digest(orders=orders, savings=savings, book=book,
                              yesterday_snapshot=None,   # audit removed
                              ltv_24h_high=ltv_24h_high, cfg=cfg)
    date_str = _today().isoformat()
    msg = carry.format_digest(data, date_str)
    topic = _carry_topic(cfg)
    ok = notify.send_message(msg, cfg, topic=topic)
    # Reset 24h LTV high for the next window (snapshot rotation removed).
    st.data["carry_ltv_24h_high"] = 0.0
    st._save()
    return 1 if ok else 0
