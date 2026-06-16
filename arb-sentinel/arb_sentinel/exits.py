import datetime


def _date(s):
    try:
        return datetime.date.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def check_position(pos, today, current_apr, depeg_price, cfg):
    """Return triggered exit-alert messages (spec §7) for one active position.
    current_apr / depeg_price may be None when unavailable. Pure; never raises."""
    msgs = []
    asset = pos.get("asset", "?")
    label = f"{(pos.get('exchange') or '?').upper()} {asset}"   # always name the exchange
    end = _date(pos.get("activity_end_date"))
    if end is not None:
        days = (end - today).days
        if days <= cfg.exit_lead_days:
            msgs.append(f"⏰ 退場提醒 | {label} 活動將於 {end.isoformat()} 結束（剩 {days} 天）,準備在踩踏前出場")
    mhu = _date(pos.get("min_hold_until"))
    if mhu is not None and today >= mhu:
        msgs.append(f"✅ {label} 已滿最低持有（{mhu.isoformat()}）,補貼資格達成,可自由出場")
    entry_apr = pos.get("entry_apr")
    if current_apr is not None and entry_apr:
        try:
            if current_apr < float(entry_apr) * cfg.rate_drop_ratio:
                msgs.append(f"📉 {label} 利率腰斬至 {current_apr*100:.2f}%（進場 {float(entry_apr)*100:.2f}%）,利差消失,考慮撤")
        except (ValueError, TypeError):
            pass
    if depeg_price is not None:
        try:
            if abs(float(depeg_price) - 1.0) * 10000 > cfg.depeg_bps:
                msgs.append(f"🚨 {label} 價格 {depeg_price} 偏離 1.0,脫鉤/踩踏早期訊號")
        except (ValueError, TypeError):
            pass
    return msgs
