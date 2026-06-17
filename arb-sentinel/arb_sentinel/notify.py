import html, sys, time
import httpx
from .models import Opportunity

API = "https://api.telegram.org"
_TIER_EMOJI = {"ACT_NOW": "🔴", "GOOD": "🟠", "WATCH": "🟡", "LOG_ONLY": "⚫"}


def send_message(text: str, cfg, pause: float = 1.1) -> bool:
    """Best-effort send to the arb forum topic. HTML parse_mode. Never raises."""
    if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
        return False
    data = {"chat_id": cfg.telegram_chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if cfg.telegram_topic_arb:
        data["message_thread_id"] = cfg.telegram_topic_arb
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(f"{API}/bot{cfg.telegram_bot_token}/sendMessage", data=data)
        if r.status_code != 200:
            # M6 hardening will honour 429 retry_after / backoff; for M1's low
            # volume we just log and treat any non-200 as a best-effort failure.
            print(f"[telegram] {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return False
        time.sleep(pause)          # respect 1 msg/sec/chat
        return True
    except Exception as e:
        print(f"[telegram] send failed (silent): {e}", file=sys.stderr)
        return False


def format_opportunity(o: Opportunity, net, est, flag, tier, cfg) -> str:
    e = lambda s: html.escape(str(s))
    emoji = _TIER_EMOJI.get(tier, "⚫")
    promo = " (促銷)" if o.apr_is_promotional else ""
    apr_str = f"{o.apr * 100:.1f}%" if o.apr is not None else "—"   # depeg/unparsed promos carry apr=None
    lines = [f"{emoji} <b>Earn 機會 | {e(o.exchange.upper())}</b>", "",
             f"{e(o.asset)} 活期 {apr_str}{promo}"]
    if net is not None:
        mode = "自有資金" if cfg.own_funds_mode else f"借款 {((o.borrow_apr_same_asset or 0)*100):.1f}%"
        lines.append(f"淨利差 ≈ {net*100:.1f}% 年化 ({mode})")
    if est.get("est_net") is not None:
        lines.append(f"參考 {cfg.ref_capital:,.0f} × {est['holding_days']} 天 ≈ +${est['est_net']:,.0f}")
    if o.end_date:
        lines.append(f"⏳ 活動至 {o.end_date.isoformat()}({flag})")
    if o.entry_asset_required:
        lines.append(f"💱 入場幣種: {e(o.entry_asset_required)}")
    if o.subsidy_note:
        lines.append(f"🎁 {e(o.subsidy_note)}")
    if o.source_url:
        lines.append(f"🔗 {e(o.source_url)}")
    lines.append(f"⚠️ 來源: {e(o.apr_source)}（顯示值未必可持續,進場前於 App 確認）")
    return "\n".join(lines)


def format_headsup(items, limit=20) -> str:
    """items = [(exchange, title, url)]. One batched WATCH heads-up; each line names
    the exchange. Qualitative — no APR math, just 'don't miss this activity'."""
    e = lambda s: html.escape(str(s))
    lines = [f"🟡 <b>套利哨兵 | 新活動 heads-up</b>（{len(items)} 則）", ""]
    for exch, title, url in items[:limit]:
        lines.append(f"• <b>{e(exch.upper())}</b> | {e(title)}")
        if url:
            lines.append(f"  🔗 {e(url)}")
    if len(items) > limit:
        lines.append(f"…+{len(items) - limit} 則")
    lines.append("\n⚠️ 收益/條件/時間窗請進各家 App 確認")
    return "\n".join(lines)


def format_digest(graded: list, cfg) -> str:
    """graded = [(Opportunity, net, tier)]. Compact baseline summary, grouped by exchange."""
    lines = [f"🟡 <b>套利哨兵 | 利率基線</b> ({len(graded)} 項)"]
    by_ex: dict = {}
    for o, net, tier in graded:
        by_ex.setdefault(o.exchange, []).append((o, net, tier))
    for ex in sorted(by_ex):
        lines.append("")
        lines.append(f"<b>{html.escape(ex.upper())}</b>")
        for o, net, tier in sorted(by_ex[ex], key=lambda t: -(t[0].apr or 0)):
            apr = f"{o.apr*100:.2f}%" if o.apr is not None else "—"
            promo = " (促銷)" if o.apr_is_promotional else ""
            lines.append(f"{_TIER_EMOJI.get(tier,'⚫')} {html.escape(o.asset)} {apr}{promo}")
    return "\n".join(lines)
