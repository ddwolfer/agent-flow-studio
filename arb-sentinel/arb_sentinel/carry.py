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
def build_digest(orders: list, savings: dict | None, book: dict | None,
                 yesterday_snapshot: dict | None,
                 ltv_24h_high: float | None, cfg) -> dict:
    """Assemble all data needed for the daily digest. Returns a dict the
    format layer can render. `yesterday_snapshot` holds
    {total_profit: float, ltv: float} recorded 24h ago; used for payout
    audit + trend annotation. `ltv_24h_high` is the max LTV observed in the
    last 24h ticks (state-tracked)."""
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
    savings_apr = 0.0
    balance = 0.0
    last_profit = 0.0
    total_profit = 0.0
    payout_audit = {"level": "UNKNOWN", "actual": 0.0, "expected": 0.0,
                    "ratio": 0.0}
    if savings:
        balance = savings.get("balance") or 0.0
        last_profit = savings.get("last_profit") or 0.0
        total_profit = savings.get("total_profit") or 0.0
        # Apply the first tier's APR as headline reference for the digest
        tiers = savings.get("apy_tiers") or []
        if tiers:
            savings_apr = (tiers[0].get("apy_percent") or 0.0) / 100.0
        yprev = (yesterday_snapshot or {}).get("total_profit")
        payout_audit = audit_payout(
            today_total_profit=total_profit,
            yesterday_total_profit=yprev,
            balance=balance,
            tiers=cfg.savings_apr_tiers,
            floor_ratio=cfg.payout_ratio_floor)
    hour_rate = order.get("hour_rate") or 0.0
    borrow_level, borrow_reason = evaluate_borrow_rate(
        hour_rate=hour_rate, savings_apr=savings_apr, cfg=cfg)
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
        "savings_apr_headline": savings_apr,
        "annual_borrow": hour_rate * 24 * 365,
        "net_spread": savings_apr - hour_rate * 24 * 365,
        "payout_audit": payout_audit,
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
    pa = data["payout_audit"]
    payout_line = (
        f"• 派息實收: {pa['actual']:.2f} {e(data['savings']['asset'])}"
        f" (預期 {pa['expected']:.2f}, 達成 {pa['ratio']*100:.0f}%)"
        if pa["level"] != "UNKNOWN"
        else f"• 派息累積 {data['total_profit']:.2f} "
             f"{e(data['savings']['asset']) if data.get('savings') else ''} "
             f"(首日,尚無 24h 對照)")
    ns = data["net_spread"]
    checks = (
        f"{_LEVEL_ICON.get(data['ltv_level'],'⚪')} LTV · "
        f"{_LEVEL_ICON.get(pa['level'],'⚪')} 派息 · "
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
        f"• 餘額: {data['balance']:,.4f} "
        f"{e(data['savings']['asset']) if data.get('savings') else ''}\n\n"
        f"💰 <b>昨日收益</b>\n"
        f"{payout_line}\n"
        f"• 借款利息累計: {order.get('interest_amount',0):.4f} "
        f"{e(order.get('loan_coin','?'))}\n\n"
        f"📈 <b>利差健康</b>\n"
        f"• 淨利差: {ns*100:+.2f}% "
        f"(APR {data['savings_apr_headline']*100:.2f}% "
        f"− 借款 {data['annual_borrow']*100:.2f}%)\n\n"
        f"🩺 <b>4 項檢查</b>\n"
        f"{checks}\n\n"
        f"—\n"
        f"⚠️ 沒收到此訊息 = 監控掛了,請手動查\n"
        f"⚠️ LTV ≥ {data['order'].get('margin_call_ltv',0.85)*100 - 3:.0f}% "
        f"會另外即時推播(last-resort)")
