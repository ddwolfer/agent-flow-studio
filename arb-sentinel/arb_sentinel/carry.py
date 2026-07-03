"""Carry-guardian rule engine — pure functions, style parallels exits.py.

All functions here are pure: no I/O, no state mutation, no side effects.
Callers in run.py wire live data + state through and act on results.

Mode: **Plan A** — digest-only + 🔴 CRITICAL immediate exception.
`evaluate_immediate()` returns messages ONLY for genuinely urgent conditions
(LTV CRITICAL, order disappeared, prolonged API blindness). All lower-tier
signals (WATCH, ALERT, borrow rate warnings, depth warnings, payout audit)
are surfaced via the daily digest builder instead.

Spec: docs/superpowers/specs/2026-07-02-carry-guardian.md
Collectors: arb_sentinel/collectors/bitget.py (loan_ongoing_orders /
savings_assets / spot_orderbook)."""
import html


# ── LTV classification ──────────────────────────────────────────────────────
def classify_ltv(ltv: float, cfg) -> str:
    """Return one of 'OK' / 'WATCH' / 'ALERT' / 'CRITICAL'. Boundaries are
    inclusive-lower so ltv == threshold jumps into the higher tier."""
    if ltv >= cfg.ltv_critical:
        return "CRITICAL"
    if ltv >= cfg.ltv_alert:
        return "ALERT"
    if ltv >= cfg.ltv_watch:
        return "WATCH"
    return "OK"


# ── escape hatch (BTC price at margin-call / liquidation) ───────────────────
def escape_hatch(loan_amount: float, pledge_amount: float,
                 current_ltv: float, margin_call_ltv: float,
                 liquidation_ltv: float) -> dict:
    """Given current position, compute the BTC price levels where LTV would
    hit margin-call and liquidation, plus the drop % from now. LTV formula:
        ltv = debt / (collateral × price)
    So price at target ltv = debt / (ltv × collateral). All returned prices
    in the loan-currency terms (USDC ≈ USD)."""
    if pledge_amount <= 0 or current_ltv <= 0:
        return {"btc_price_now": 0.0, "price_at_margin_call": 0.0,
                "price_at_liquidation": 0.0,
                "pct_to_margin_call": 0.0, "pct_to_liquidation": 0.0}
    price_now = loan_amount / (current_ltv * pledge_amount)
    price_mc = loan_amount / (margin_call_ltv * pledge_amount)
    price_liq = loan_amount / (liquidation_ltv * pledge_amount)
    return {
        "btc_price_now": price_now,
        "price_at_margin_call": price_mc,
        "price_at_liquidation": price_liq,
        # Drop fraction from now (0.15 = -15%). Never negative for a
        # long-BTC carry where current_ltv < margin_call_ltv.
        "pct_to_margin_call": max(0.0, (price_now - price_mc) / price_now),
        "pct_to_liquidation": max(0.0, (price_now - price_liq) / price_now),
    }


# ── expected payout via APR tiers ───────────────────────────────────────────
def expected_daily_payout(balance: float, tiers: list) -> float:
    """Weighted expected daily payout across tier bands. `tiers` is list of
    `[upper_cap_or_None, apr_decimal]` in ascending cap order. `None` cap =
    no upper bound (rest of the balance settles at that APR)."""
    remaining = max(0.0, float(balance))
    prev_cap = 0.0
    total = 0.0
    for entry in tiers:
        cap, apr = entry[0], float(entry[1])
        if cap is None:
            total += remaining * apr / 365.0
            return total
        cap = float(cap)
        band_size = max(0.0, cap - prev_cap)
        in_band = min(remaining, band_size)
        total += in_band * apr / 365.0
        remaining -= in_band
        prev_cap = cap
        if remaining <= 0:
            break
    return total


# ── payout audit (via totalProfit delta) ────────────────────────────────────
def audit_payout(today_total_profit: float, yesterday_total_profit,
                 balance: float, tiers: list, floor_ratio: float) -> dict:
    """Compare `today_totalProfit - yesterday_totalProfit` (actual 24h payout)
    against expected. Returns {actual, expected, ratio, level}.

    Levels:
      UNKNOWN  — no yesterday snapshot yet (fresh install; skip audit)
      OK       — actual >= floor_ratio × expected  (default 0.9)
      WARN     — 0 < actual < floor × expected
      CRITICAL — actual == 0 (payout dried up completely)"""
    if yesterday_total_profit is None:
        return {"level": "UNKNOWN", "actual": 0.0, "expected": 0.0, "ratio": 0.0}
    actual = float(today_total_profit) - float(yesterday_total_profit)
    if actual < 0:            # accounting anomaly; treat as unknown
        return {"level": "UNKNOWN", "actual": actual, "expected": 0.0,
                "ratio": 0.0}
    expected = expected_daily_payout(balance, tiers)
    ratio = (actual / expected) if expected > 0 else 0.0
    if actual == 0.0 and expected > 0:
        level = "CRITICAL"
    elif ratio >= floor_ratio:
        level = "OK"
    else:
        level = "WARN"
    return {"level": level, "actual": actual, "expected": expected,
            "ratio": ratio}


# ── borrow rate check (config thresholds + net spread) ───────────────────────
def evaluate_borrow_rate(hour_rate: float, savings_apr: float,
                         cfg) -> tuple[str, str]:
    """Return (level, reason). `hour_rate` is per-hour decimal (already
    normalised by the collector). Thresholds in cfg are per-hour decimal too."""
    annual = hour_rate * 24 * 365
    net_spread = savings_apr - annual
    if net_spread < cfg.net_spread_floor:
        return ("ALERT", f"利差瀕死 {net_spread*100:.2f}% "
                         f"(APR {savings_apr*100:.2f}% − 借款 {annual*100:.2f}%)")
    if hour_rate >= cfg.borrow_hour_rate_alert:
        return ("ALERT", f"借款年化 {annual*100:.2f}% 已高")
    if hour_rate >= cfg.borrow_hour_rate_warn:
        return ("WARN", f"借款年化 {annual*100:.2f}% 上升")
    return ("OK", f"借款年化 {annual*100:.2f}%")


# ── depth / bid check for USDGO exit liquidity ──────────────────────────────
def evaluate_depth(bid1_price: float, cum_bid_qty: float,
                   position_size: float, cfg) -> tuple[str, str]:
    """Return (level, reason). Combines two checks:
    - bid1 vs bid_floor_warn / bid_floor_critical
    - cum_bid_qty vs cfg.depth_multiple × position_size"""
    if bid1_price < cfg.bid_floor_critical:
        return ("CRITICAL", f"USDGO bid1 {bid1_price:.4f} 深度脫錨")
    if bid1_price < cfg.bid_floor_warn:
        return ("WARN", f"USDGO bid1 {bid1_price:.4f} 略低於 1.0")
    if cum_bid_qty < cfg.depth_multiple * position_size:
        depth_ratio = cum_bid_qty / max(position_size, 1)
        return ("WARN", f"買方深度 {depth_ratio:.1f}x 部位,不足全平出場")
    return ("OK", f"bid1 {bid1_price:.4f}, 深度 {cum_bid_qty/max(position_size,1):.1f}x")


# ── immediate-push evaluator (Plan A: CRITICAL + system health only) ────────
def evaluate_immediate(orders: list, api_fail_count: int, cfg,
                       orders_valid: bool = True) -> list[str]:
    """Called every 5-min tick. Returns list of Telegram-ready HTML messages
    for genuinely urgent conditions ONLY. Plan A skips WATCH / ALERT / borrow
    warnings — those wait for the digest.

    Message hierarchy:
      1. 風控失明 (api_fail_count >= 3): API blindness — silently treating
         empty orders as 'liquidated' would be catastrophic, so this MUST
         come first and overrides the orders check.
      2. 訂單消失 (orders == [] AND orders_valid AND api_fail_count < 3):
         position closed or liquidated. `orders_valid` is caller's assertion
         that the fetch succeeded — with orders_valid=False the empty list
         is 'we couldn't tell', not 'gone'.
      3. 🔴 CRITICAL LTV: LTV >= ltv_critical for any surfaced order.
         Fires EVERY tick until LTV falls (spec §5.1: '每次執行都通知')."""
    msgs = []
    if api_fail_count >= 3:
        msgs.append(
            "🟠 <b>套利哨兵 | BITGET Carry · 風控失明</b>\n\n"
            f"連續 {api_fail_count} 次抓 loan/ongoing-orders 失敗。"
            "在恢復前,請手動檢查 Bitget App 的 LTV。")
        return msgs                           # do not evaluate CRITICAL blind
    if not orders and orders_valid:
        msgs.append(
            "🟡 <b>套利哨兵 | BITGET Carry · 借款訂單消失</b>\n\n"
            "查無進行中的 loan 訂單。可能是:\n"
            "• 你自己還清了 → 把 <code>carry.enabled</code> 設 false 停監控\n"
            "• 被強平了 → 立刻打開 Bitget App 檢查現貨帳戶\n\n"
            "自動停用後續 carry 檢查,直到 order_id 更新或 state 重置。")
        return msgs
    for order in orders:
        ltv = order.get("ltv") or 0.0
        if ltv < cfg.ltv_critical:
            continue
        loan_amount = order.get("loan_amount") or 0.0
        pledge_amount = order.get("pledge_amount") or 0.0
        mc_ltv = order.get("margin_call_ltv") or cfg.margin_call_ltv
        liq_ltv = order.get("liquidation_ltv") or cfg.liquidation_ltv
        hatch = escape_hatch(loan_amount, pledge_amount, ltv, mc_ltv, liq_ltv)
        msgs.append(
            f"🔴🔴🔴 <b>套利哨兵 | BITGET Carry · CRITICAL</b>\n\n"
            f"<b>LTV: {ltv*100:.1f}%</b> "
            f"(距補保 {mc_ltv*100:.0f}% 差 {(mc_ltv-ltv)*100:.1f}pp / "
            f"距強平 {liq_ltv*100:.0f}% 差 {(liq_ltv-ltv)*100:.1f}pp)\n\n"
            f"📉 BTC 換算:\n"
            f"• 現價估算: ${hatch['btc_price_now']:,.0f}\n"
            f"• 觸發補保還要跌: {hatch['pct_to_margin_call']*100:.1f}%"
            f" (→ ${hatch['price_at_margin_call']:,.0f})\n"
            f"• 觸發強平還要跌: {hatch['pct_to_liquidation']*100:.1f}%"
            f" (→ ${hatch['price_at_liquidation']:,.0f})\n\n"
            f"🚨 立刻做:\n"
            f"方案 A (推薦): 賣 USDGO 還 USDC → 立刻壓 LTV\n"
            f"方案 B: 補 BTC 抵押\n\n"
            f"⚠️ 每 5 分鐘會重複通知直到 LTV 回落\n"
            f"🔗 https://www.bitget.com/asset/futures/margin/isolated")
    return msgs


# ── digest state builder ────────────────────────────────────────────────────
def _current_tier(balance: float, tiers: list) -> tuple[float, str]:
    """Walk live tier bands from the savings/assets response to find the
    ACTIVE tier for the current balance. Returns (apy_decimal, level_str).
    Uses live tier data (not cfg.savings_apr_tiers) so a Bitget-side rate
    change surfaces immediately in the next digest."""
    for tier in tiers or []:
        lo = float(tier.get("min") or 0)
        hi_raw = tier.get("max")
        hi = float(hi_raw) if hi_raw not in (None, 0) else float("inf")
        if lo <= balance < hi:
            return (float(tier.get("apy_percent") or 0.0) / 100.0,
                    str(tier.get("level") or "?"))
    # Balance beyond all defined bands — last tier applies
    if tiers:
        last = tiers[-1]
        return (float(last.get("apy_percent") or 0.0) / 100.0,
                str(last.get("level") or "?"))
    return (0.0, "?")


def build_digest(orders: list, savings: dict | None, book: dict | None,
                 yesterday_snapshot: dict | None,
                 ltv_24h_high: float | None, cfg) -> dict:
    """Assemble all data needed for the daily digest. Returns a dict the
    format layer can render.

    Slice G (2026-07-03): removed the actual-vs-expected payout audit.
    Manual USDGO redeems / subscribes made the audit noisy (see spec
    discussion). Digest now surfaces the LIVE tier APR from savings.
    apy_tiers plus cumulative totalProfit — informational, not compared
    to a delta. `yesterday_snapshot` argument kept for back-compat but
    unused; can be removed in a later cleanup.

    `ltv_24h_high` is the max LTV observed in the last 24h ticks."""
    result = {
        "have_position": bool(orders),
        "ltv_24h_high": ltv_24h_high,
    }
    if not orders:
        return result
    order = orders[0]           # single-position deployment
    ltv = order.get("ltv") or 0.0
    hatch = escape_hatch(
        order.get("loan_amount") or 0.0, order.get("pledge_amount") or 0.0,
        ltv, order.get("margin_call_ltv") or cfg.margin_call_ltv,
        order.get("liquidation_ltv") or cfg.liquidation_ltv)
    balance = 0.0
    last_profit = 0.0
    total_profit = 0.0
    current_tier_apr = 0.0
    current_tier_level = "?"
    expected_daily = 0.0
    if savings:
        balance = savings.get("balance") or 0.0
        last_profit = savings.get("last_profit") or 0.0
        total_profit = savings.get("total_profit") or 0.0
        # Use LIVE tier data from savings.apy_tiers — reflects any Bitget
        # rate change the next tick.
        current_tier_apr, current_tier_level = _current_tier(
            balance, savings.get("apy_tiers") or [])
        expected_daily = expected_daily_payout(balance, cfg.savings_apr_tiers)
    hour_rate = order.get("hour_rate") or 0.0
    borrow_level, borrow_reason = evaluate_borrow_rate(
        hour_rate=hour_rate, savings_apr=current_tier_apr, cfg=cfg)
    depth_level, depth_reason = ("UNKNOWN", "orderbook 抓不到")
    if book:
        depth_level, depth_reason = evaluate_depth(
            bid1_price=book.get("bid1_price") or 0.0,
            cum_bid_qty=book.get("cum_bid_qty") or 0.0,
            position_size=balance, cfg=cfg)
    ltv_level = classify_ltv(ltv, cfg)
    return {
        "have_position": True,
        "order": order,
        "hatch": hatch,
        "ltv_level": ltv_level,
        "ltv_24h_high": ltv_24h_high,
        "savings": savings,
        "balance": balance,
        "last_profit": last_profit,
        "total_profit": total_profit,
        # NEW in Slice G: live tier + expected daily (no audit)
        "current_tier_apr": current_tier_apr,
        "current_tier_level": current_tier_level,
        "expected_daily_payout": expected_daily,
        "annual_borrow": hour_rate * 24 * 365,
        "net_spread": current_tier_apr - hour_rate * 24 * 365,
        "borrow_level": borrow_level,
        "borrow_reason": borrow_reason,
        "depth_level": depth_level,
        "depth_reason": depth_reason,
        "book": book,
    }


# ── digest formatter ────────────────────────────────────────────────────────
_LEVEL_ICON = {"OK": "✅", "WATCH": "🟡", "ALERT": "🟠", "CRITICAL": "🔴",
               "WARN": "🟡", "UNKNOWN": "⚪"}


def format_digest(data: dict, date_str: str) -> str:
    """Render the digest data into a Telegram-ready HTML message. Includes
    the 24h LTV peak per user's explicit ask, and a heartbeat footer."""
    e = lambda s: html.escape(str(s))
    if not data.get("have_position"):
        return (f"📊 <b>套利哨兵 | Carry 日報 · {e(date_str)}</b>\n\n"
                f"⚫ 無 carry 部位。carry.enabled 設 true 或 order 消失。\n\n"
                f"—\n⚠️ 沒收到此訊息 = 監控掛了,請手動查")
    order = data["order"]
    hatch = data["hatch"]
    ltv = (order.get("ltv") or 0.0) * 100
    ltv_icon = {"OK": "⚫", "WATCH": "🟡", "ALERT": "🟠",
                "CRITICAL": "🔴"}[data["ltv_level"]]
    ltv_24h_high = data.get("ltv_24h_high")
    high_line = ""
    if ltv_24h_high is not None:
        high_line = (f"• LTV(24h 最高): {ltv_24h_high*100:.2f}% "
                     f"(BTC 昨日最低 ${hatch['price_at_margin_call']:,.0f} "
                     f"以上均安全)\n")
    asset = e(data['savings']['asset']) if data.get('savings') else ""
    tier_apr = data.get("current_tier_apr", 0.0)
    tier_level = data.get("current_tier_level", "?")
    expected_daily = data.get("expected_daily_payout", 0.0)
    ns = data["net_spread"]
    # Estimated daily USD net (rough: expected earnings − yesterday borrow cost)
    net_daily_usd = expected_daily - order.get('interest_amount', 0.0)
    checks = (
        f"{_LEVEL_ICON.get(data['ltv_level'],'⚪')} LTV · "
        f"{_LEVEL_ICON.get(data['borrow_level'],'⚪')} 借款 · "
        f"{_LEVEL_ICON.get(data['depth_level'],'⚪')} USDGO bid1 "
        f"{(data['book'] or {}).get('bid1_price', 0):.4f}")
    return (
        f"📊 <b>套利哨兵 | Carry 日報 · {e(date_str)}</b>\n\n"
        f"💼 <b>部位快照</b>\n"
        f"• LTV(現在): {ltv:.2f}% {ltv_icon} {data['ltv_level']} "
        f"(補保 {order.get('margin_call_ltv',0)*100:.0f}% / "
        f"強平 {order.get('liquidation_ltv',0)*100:.0f}%)\n"
        f"{high_line}"
        f"• 負債: {order.get('loan_amount',0):,.2f} {e(order.get('loan_coin','?'))} "
        f"(+{order.get('interest_amount',0):.4f} 累息)\n"
        f"• 抵押: {order.get('pledge_amount',0):.5f} {e(order.get('pledge_coin','?'))} "
        f"≈ ${hatch['btc_price_now']*(order.get('pledge_amount') or 0):,.0f}\n"
        f"• 餘額: {data['balance']:,.4f} {asset}\n\n"
        f"💰 <b>收益</b>\n"
        f"• 現行 APR: {tier_apr*100:.2f}%(tier {tier_level})\n"
        f"• 預估日派息: {expected_daily:.2f} {asset}\n"
        f"• 累積派息(自開倉): {data['total_profit']:.2f} {asset}\n"
        f"• 昨日借款利息: {order.get('interest_amount',0):.4f} "
        f"{e(order.get('loan_coin','?'))}\n"
        f"• 預估淨利: ≈ ${net_daily_usd:.2f}/日\n\n"
        f"📈 <b>利差健康</b>\n"
        f"• 淨利差: {ns*100:+.2f}% "
        f"(APR {tier_apr*100:.2f}% "
        f"− 借款 {data['annual_borrow']*100:.2f}%)\n\n"
        f"🩺 <b>3 項檢查</b>\n"
        f"{checks}\n\n"
        f"—\n"
        f"⚠️ 沒收到此訊息 = 監控掛了,請手動查\n"
        f"⚠️ LTV ≥ {data['order'].get('margin_call_ltv',0.85)*100 - 3:.0f}% "
        f"會另外即時推播(last-resort)")
