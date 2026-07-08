"""SMC 結構視角下的價格區間計算腳本(price-zone v0.2)。

Spec: docs/superpowers/specs/2026-07-08-price-zone-design.md

原則:
  - 純確定性計算,不經 LLM
  - 同數據跑 N 次,JSON 逐 byte 一致(除 as_of 當日日期字串)
  - 所有價位 round(., 2),避免浮點漂移
  - 欄位可增不可減;算不出來填 null 並在 warnings 註明

CLI:
  python compute_zones.py TICKER [--period 12mo] [--out path.json]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import pathlib
import sys
from dataclasses import dataclass
from typing import Any

import yfinance as yf

SCHEMA_VERSION = "v0.3"
FRACTAL_N = 3
ATR_PERIOD = 14
RANGE_WINDOW = 120
EQ_TOLERANCE_ATR_MULT = 0.3
LIQUIDITY_LOOKBACK_ATR_MULT = 1.5
MIN_BARS_FOR_FULL_MODE = 60
FVG_RECENT_BARS = 90                  # v0.3 §2.6: FVG time decay window
STRESS_ATR_MULT = 0.3                 # v0.3 §2.5: intraday_stress_level offset

# v0.3 §2.2 warning → 中文說明 mapping
ZONE_NULL_NOTES = {
    "structure_already_broken_above":
        "無 SMC 減碼目標:所有 premium swing high 皆已被突破,需等待新 swing high 形成",
    "no_valid_sell_basis_in_premium":
        "無 SMC 減碼目標:premium 區無 confirmed swing high 或 equal highs",
    "no_valid_buy_basis_in_discount":
        "無 SMC 買進目標:discount 區無未回補 bullish FVG 或 confirmed swing low",
    "buy_zone_above_price_anomaly":
        "異常:buy_zone.low 高於現價,基準邏輯需人工檢視",
    "choch_functionally_fired_but_swing_structure_still_down":
        "趨勢分歧:swing 結構仍為 down,但價格已高於所有 confirmed swing high;CHoCH 可能已功能性觸發",
}


# ── data class ─────────────────────────────────────────────────────────────
@dataclass
class Bar:
    date: str          # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Swing:
    date: str
    price: float
    kind: str          # "H" or "L"
    confirmed: bool    # False if within last FRACTAL_N bars


# ── helpers ────────────────────────────────────────────────────────────────
def _r(x: float) -> float:
    """Round to 2 decimals, guarding NaN/inf."""
    if x is None or not math.isfinite(x):
        return 0.0
    return round(float(x), 2)


def _r4(x: float) -> float:
    if x is None or not math.isfinite(x):
        return 0.0
    return round(float(x), 4)


# ── data fetch ─────────────────────────────────────────────────────────────
def fetch_bars(ticker: str, period: str = "12mo") -> list[Bar]:
    df = yf.Ticker(ticker).history(period=period, interval="1d", auto_adjust=True)
    if df is None or df.empty:
        return []
    bars: list[Bar] = []
    for idx, row in df.iterrows():
        # normalize date: drop time & tz for schema stability
        d = idx.date() if hasattr(idx, "date") else dt.date.fromisoformat(str(idx)[:10])
        bars.append(Bar(
            date=d.strftime("%Y-%m-%d"),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row.get("Volume", 0.0) or 0.0),
        ))
    return bars


# ── indicators ─────────────────────────────────────────────────────────────
def wilder_atr(bars: list[Bar], period: int = ATR_PERIOD) -> list[float]:
    """Wilder-smoothed ATR series; index-aligned with bars.
    Values before `period` are 0.0 (seed indeterminate)."""
    n = len(bars)
    if n <= period:
        return [0.0] * n
    tr = [0.0] * n
    for i in range(1, n):
        h, l = bars[i].high, bars[i].low
        pc = bars[i - 1].close
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    atr = [0.0] * n
    # seed at index `period` = mean(TR[1:period+1])
    seed = sum(tr[1:period + 1]) / period
    atr[period] = seed
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def find_swings(bars: list[Bar], n: int = FRACTAL_N) -> list[Swing]:
    """Fractal swing detection. Last `n` bars marked confirmed=False."""
    swings: list[Swing] = []
    total = len(bars)
    for i in range(n, total - n):
        window_h = [bars[i + k].high for k in range(-n, n + 1) if k != 0]
        window_l = [bars[i + k].low for k in range(-n, n + 1) if k != 0]
        # Swing High: strict >  all neighbours (avoids duplicate flat highs)
        if bars[i].high > max(window_h):
            swings.append(Swing(bars[i].date, _r(bars[i].high), "H", True))
        if bars[i].low < min(window_l):
            swings.append(Swing(bars[i].date, _r(bars[i].low), "L", True))
    # Also scan pending: bars in [total-n, total) can only be tentatively flagged
    # against the LEFT-side window; we mark them pending explicitly.
    for i in range(max(n, total - n), total):
        left_h = [bars[i - k].high for k in range(1, n + 1) if i - k >= 0]
        left_l = [bars[i - k].low for k in range(1, n + 1) if i - k >= 0]
        if left_h and bars[i].high > max(left_h):
            swings.append(Swing(bars[i].date, _r(bars[i].high), "H", False))
        if left_l and bars[i].low < min(left_l):
            swings.append(Swing(bars[i].date, _r(bars[i].low), "L", False))
    swings.sort(key=lambda s: (s.date, s.kind))
    return swings


# ── trend / BOS / CHoCH ────────────────────────────────────────────────────
def determine_trend(swings: list[Swing]) -> tuple[str, str]:
    """Return (direction, basis_text).
    direction ∈ {'up', 'down', 'range'}."""
    confirmed = [s for s in swings if s.confirmed]
    highs = [s for s in confirmed if s.kind == "H"][-2:]
    lows = [s for s in confirmed if s.kind == "L"][-2:]
    if len(highs) < 2 or len(lows) < 2:
        return "range", "insufficient confirmed swings"
    hh = highs[-1].price > highs[-2].price
    hl = lows[-1].price > lows[-2].price
    ll = lows[-1].price < lows[-2].price
    lh = highs[-1].price < highs[-2].price
    if hh and hl:
        return "up", f"HH/HL since {lows[-2].date}"
    if lh and ll:
        return "down", f"LH/LL since {highs[-2].date}"
    return "range", f"mixed swings since {min(highs[-2].date, lows[-2].date)}"


def find_last_bos_choch(
    bars: list[Bar], swings: list[Swing]
) -> tuple[dict | None, dict | None]:
    """Detect last BOS + last CHoCH by walking bars and comparing to prior
    confirmed swings.

    Algorithm (simplified for v0.2):
      - Walk bars in order. For each bar's close, find any confirmed swing
        strictly before it whose level is crossed for the first time.
      - The FIRST such cross defines an initial "direction" (up if H crossed,
        down if L crossed). Subsequent crosses:
          * same direction → BOS event
          * opposite direction → CHoCH event
      - Return most recent BOS + most recent CHoCH.
    """
    events = []  # (date, price, direction)
    broken: set[tuple[str, str]] = set()  # (swing.date, swing.kind) already broken
    for bar in bars:
        prior_swings = [s for s in swings
                        if s.confirmed and s.date < bar.date
                        and (s.date, s.kind) not in broken]
        for s in prior_swings:
            if s.kind == "H" and bar.close > s.price:
                events.append({"date": bar.date, "price": _r(s.price), "direction": "up"})
                broken.add((s.date, s.kind))
            elif s.kind == "L" and bar.close < s.price:
                events.append({"date": bar.date, "price": _r(s.price), "direction": "down"})
                broken.add((s.date, s.kind))
    if not events:
        return None, None
    last_bos = None
    last_choch = None
    prev_dir = None
    for ev in events:
        if prev_dir is None:
            prev_dir = ev["direction"]
            last_bos = ev
            continue
        if ev["direction"] == prev_dir:
            last_bos = ev
        else:
            last_choch = ev
            prev_dir = ev["direction"]
            last_bos = ev  # CHoCH also counts as a break in new direction
    return last_bos, last_choch


# ── equal highs / lows clusters ────────────────────────────────────────────
def equal_clusters(
    swings: list[Swing], kind: str, tol: float
) -> list[dict]:
    """Cluster confirmed swings of given kind within `tol`.
    Returns list of {price, touches} for clusters with >= 2 touches,
    sorted by touches desc then price."""
    pool = sorted([s.price for s in swings if s.confirmed and s.kind == kind])
    if not pool or tol <= 0:
        return []
    clusters: list[list[float]] = []
    cur: list[float] = [pool[0]]
    for p in pool[1:]:
        if p - cur[0] <= tol:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    out = []
    for c in clusters:
        if len(c) >= 2:
            out.append({"price": _r(sum(c) / len(c)), "touches": len(c)})
    out.sort(key=lambda x: (-x["touches"], x["price"]))
    return out


# ── unfilled FVG ───────────────────────────────────────────────────────────
def find_unfilled_fvg(bars: list[Bar], recent_bars: int = FVG_RECENT_BARS) -> list[dict]:
    """Detect bullish/bearish 3-bar FVGs and keep only those not yet retraced.

    v0.3 §2.6: only scan the most recent `recent_bars` bars (default 90).
    Old FVGs are typically irrelevant to daily swing zones."""
    out = []
    # Compute the earliest bar index we care about (need i >= 2 for k1)
    start_idx = max(2, len(bars) - recent_bars) if len(bars) > recent_bars else 2
    for i in range(start_idx, len(bars)):
        k1, k3 = bars[i - 2], bars[i]
        # bullish FVG: k1.high < k3.low → gap [k1.high, k3.low]
        if k1.high < k3.low:
            top, bottom = _r(k3.low), _r(k1.high)
            filled = any(b.low <= bottom for b in bars[i + 1:])
            if not filled:
                out.append({"type": "bullish", "top": top, "bottom": bottom,
                            "date": bars[i].date})
        # bearish FVG: k1.low > k3.high → gap [k3.high, k1.low]
        if k1.low > k3.high:
            top, bottom = _r(k1.low), _r(k3.high)
            filled = any(b.high >= top for b in bars[i + 1:])
            if not filled:
                out.append({"type": "bearish", "top": top, "bottom": bottom,
                            "date": bars[i].date})
    return out


# ── zone building ──────────────────────────────────────────────────────────
def half_width(price: float, atr14: float) -> float:
    """v0.2 formula: ATR-based with price % floor/ceiling."""
    if atr14 <= 0:
        return _r(0.015 * price)
    return _r(min(
        max(0.5 * atr14, 0.0075 * price),
        0.025 * price,
    ))


def pick_buy_basis(
    swings: list[Swing], fvgs: list[dict], equilibrium: float, current_price: float
) -> dict | None:
    """Highest-priority basis in discount zone, at or below current price.

    Priority:
      1. Nearest unfilled bullish FVG below current price (top < price)
      2. Most recent confirmed swing low below equilibrium
    """
    below_price_fvgs = [
        f for f in fvgs if f["type"] == "bullish" and f["top"] < current_price
        and (f["top"] + f["bottom"]) / 2 < equilibrium
    ]
    if below_price_fvgs:
        # pick the nearest below current price (largest top)
        best = max(below_price_fvgs, key=lambda f: f["top"])
        return {"kind": "fvg", "price": _r((best["top"] + best["bottom"]) / 2),
                "text": f"unfilled bullish FVG {best['date']}",
                "invalidation_price": _r(best["bottom"]),
                "extras": best}
    lows = [s for s in swings if s.confirmed and s.kind == "L"
            and s.price < equilibrium]
    if lows:
        last = max(lows, key=lambda s: s.date)
        return {"kind": "swing_low", "price": last.price,
                "text": f"HL swing low {last.date}",
                "invalidation_price": last.price,
                "extras": None}
    return None


def pick_sell_basis(
    swings: list[Swing], eq_highs: list[dict], equilibrium: float
) -> dict | None:
    """Priority:
      1. Highest-touches equal-highs cluster in premium
      2. Most recent confirmed swing high in premium
    """
    prem_ehs = [e for e in eq_highs if e["price"] > equilibrium]
    if prem_ehs:
        best = prem_ehs[0]  # sorted by touches desc already
        return {"kind": "equal_highs", "price": _r(best["price"]),
                "text": f"equal highs cluster ({best['touches']} touches)",
                "invalidation_price": _r(best["price"]),
                "extras": None}
    highs = [s for s in swings if s.confirmed and s.kind == "H"
             and s.price > equilibrium]
    if highs:
        last = max(highs, key=lambda s: s.date)
        return {"kind": "swing_high", "price": last.price,
                "text": f"swing high {last.date}",
                "invalidation_price": last.price,
                "extras": None}
    return None


def check_liquidity_below(
    buy_low: float, eq_lows: list[dict], atr14: float
) -> dict | None:
    """Return liquidity pool spec if equal lows exist within 1.5×ATR below."""
    if atr14 <= 0 or not eq_lows:
        return None
    threshold = buy_low - LIQUIDITY_LOOKBACK_ATR_MULT * atr14
    nearby = [e for e in eq_lows if threshold <= e["price"] <= buy_low]
    if not nearby:
        return None
    nearest = max(nearby, key=lambda e: e["price"])
    return {"exists": True, "price": _r(nearest["price"])}


# ── main orchestration ────────────────────────────────────────────────────
def build_output(ticker: str, bars: list[Bar]) -> dict[str, Any]:
    as_of = dt.date.today().strftime("%Y-%m-%d")
    if len(bars) < MIN_BARS_FOR_FULL_MODE:
        return _build_degraded(ticker, bars, as_of)

    atr_series = wilder_atr(bars)
    atr14 = _r(atr_series[-1])
    price = _r(bars[-1].close)

    swings = find_swings(bars)
    confirmed_swings = [s for s in swings if s.confirmed]
    as_of_confirmed_swing = max(
        (s.date for s in confirmed_swings), default=bars[0].date
    )

    trend_dir, trend_basis = determine_trend(swings)
    last_bos, last_choch = find_last_bos_choch(bars, swings)

    # range + equilibrium (last 120 bars)
    window = bars[-RANGE_WINDOW:] if len(bars) >= RANGE_WINDOW else bars
    r_high = _r(max(b.high for b in window))
    r_low = _r(min(b.low for b in window))
    r_eq = _r((r_high + r_low) / 2)
    position = "premium" if price > r_eq else "discount"

    tol = EQ_TOLERANCE_ATR_MULT * atr14
    eq_lows = equal_clusters(swings, "L", tol)
    eq_highs = equal_clusters(swings, "H", tol)

    unfilled_fvg = find_unfilled_fvg(bars)

    warnings: list[str] = []
    hw = half_width(price, atr14)

    # buy zone
    buy_zone = None
    buy_zone_pending = None
    if trend_dir == "down":
        # v0.3 §2.1 fix: pick swing high STRICTLY ABOVE current price
        # (a swing high already below price has been broken — cannot be
        #  the CHoCH trigger any longer).
        recent_high = None
        for s in reversed(swings):
            if s.confirmed and s.kind == "H" and s.price > price:
                recent_high = s
                break
        if recent_high:
            buy_zone_pending = {
                "reason": "downtrend — 目前無有效買區,需先 CHoCH 反轉",
                "watch_price_for_choch": _r(recent_high.price),
                "watch_rule": f"daily close above {_r(recent_high.price)}",
            }
        else:
            # No swing high above current price → CHoCH may have functionally
            # fired even though swing sequence still reads as down.
            buy_zone_pending = {
                "reason": "downtrend by swing structure, but price already above all confirmed swing highs — CHoCH may have functionally fired",
                "watch_price_for_choch": None,
                "watch_rule": None,
            }
            warnings.append("choch_functionally_fired_but_swing_structure_still_down")
    else:
        basis = pick_buy_basis(swings, unfilled_fvg, r_eq, price)
        if basis:
            # v0.2.1: anchor zone.low to invalidation level.
            invalidation = _r(basis["invalidation_price"])
            bz_low = invalidation
            if basis["kind"] == "fvg":
                fvg_top = basis["extras"]["top"]
                bz_high = _r(max(fvg_top, invalidation + 2 * hw))
            else:  # swing_low
                bz_high = _r(invalidation + 2 * hw)
            needs_pullback = bz_high < price
            if bz_low > price:
                warnings.append("buy_zone_above_price_anomaly")
            liq = check_liquidity_below(bz_low, eq_lows, atr14)
            # v0.3 §2.3: price_in_zone; §2.5: intraday_stress_level
            stress = _r(invalidation - STRESS_ATR_MULT * atr14)
            buy_zone = {
                "low": bz_low,
                "high": bz_high,
                "basis": basis["text"],
                "needs_pullback": needs_pullback,
                "price_in_zone": bz_low <= price <= bz_high,
                "liquidity_below": liq,
                "invalidation_price": invalidation,
                "invalidation_rule": f"daily close below {invalidation}",
                "intraday_stress_level": stress,
                "intraday_stress_rule": f"intraday low <= {stress} without daily close below {invalidation}",
            }
        else:
            warnings.append("no_valid_buy_basis_in_discount")

    # sell zone (mirror of buy_zone: anchored at zone.high = invalidation)
    sell_zone = None
    sbasis = pick_sell_basis(swings, eq_highs, r_eq)
    if sbasis:
        invalidation_s = _r(sbasis["invalidation_price"])
        sz_high = invalidation_s
        sz_low = _r(invalidation_s - 2 * hw)
        if sz_high < price:
            warnings.append("structure_already_broken_above")
        else:
            # v0.3 §2.3 + §2.5
            stress_s = _r(invalidation_s + STRESS_ATR_MULT * atr14)
            sell_zone = {
                "low": sz_low,
                "high": sz_high,
                "basis": sbasis["text"],
                "price_in_zone": sz_low <= price <= sz_high,
                "invalidation_price": invalidation_s,
                "invalidation_rule": f"daily close above {invalidation_s}",
                "intraday_stress_level": stress_s,
                "intraday_stress_rule": f"intraday high >= {stress_s} without daily close above {invalidation_s}",
            }
    else:
        warnings.append("no_valid_sell_basis_in_premium")

    # v0.3 §2.4: overlap detection
    if buy_zone and sell_zone and buy_zone["high"] > sell_zone["low"]:
        warnings.append("zones_overlapping_pivotal")

    # v0.3 §2.2: derive buy_zone_note / sell_zone_note from warnings
    def _note_for(zone_type: str) -> str | None:
        if zone_type == "buy" and buy_zone is not None:
            return None
        if zone_type == "sell" and sell_zone is not None:
            return None
        relevant = {
            "buy": ["no_valid_buy_basis_in_discount", "buy_zone_above_price_anomaly",
                    "choch_functionally_fired_but_swing_structure_still_down"],
            "sell": ["no_valid_sell_basis_in_premium", "structure_already_broken_above"],
        }[zone_type]
        for w in warnings:
            if w in relevant and w in ZONE_NULL_NOTES:
                return ZONE_NULL_NOTES[w]
        return None
    buy_zone_note = _note_for("buy")
    sell_zone_note = _note_for("sell")

    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "as_of": as_of,
        "as_of_confirmed_swing": as_of_confirmed_swing,
        "mode": "full",
        "price": price,
        "atr14": atr14,
        "trend": {"direction": trend_dir, "basis": trend_basis},
        "last_bos": last_bos,
        "last_choch": last_choch,
        "range": {"high": r_high, "low": r_low,
                  "equilibrium": r_eq, "position": position},
        "equal_lows": eq_lows,
        "equal_highs": eq_highs,
        "unfilled_fvg": unfilled_fvg,
        "buy_zone": buy_zone,
        "buy_zone_note": buy_zone_note,
        "buy_zone_pending": buy_zone_pending,
        "sell_zone": sell_zone,
        "sell_zone_note": sell_zone_note,
        "warnings": warnings,
    }


def _build_degraded(ticker: str, bars: list[Bar], as_of: str) -> dict[str, Any]:
    if not bars:
        return {
            "schema_version": SCHEMA_VERSION,
            "ticker": ticker,
            "as_of": as_of,
            "mode": "degraded",
            "reason": "no_data",
            "warnings": ["no_bars_from_yfinance"],
        }
    ipo = _r(bars[0].open)
    hi = _r(max(b.high for b in bars))
    lo = _r(min(b.low for b in bars))
    px = _r(bars[-1].close)
    pct = _r4((px - lo) / (hi - lo) if hi > lo else 0.0)
    atr_series = wilder_atr(bars)
    atr14 = _r(atr_series[-1]) if atr_series else 0.0
    return {
        "schema_version": SCHEMA_VERSION,
        "ticker": ticker,
        "as_of": as_of,
        "mode": "degraded",
        "reason": "insufficient_bars",
        "bar_count": len(bars),
        "min_bars_required": MIN_BARS_FOR_FULL_MODE,
        "ipo_open": ipo,
        "historical_high": hi,
        "historical_low": lo,
        "price": px,
        "position_pct": pct,
        "atr14": atr14,
        "warnings": ["degraded_mode_no_zones"],
    }


# ── CLI ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--period", default="12mo")
    ap.add_argument("--out", default=None,
                    help="Write JSON to path; if omitted, print to stdout")
    args = ap.parse_args()

    ticker = args.ticker.upper()
    try:
        bars = fetch_bars(ticker, args.period)
    except Exception as e:  # noqa: BLE001 — external I/O boundary
        err = {"schema_version": SCHEMA_VERSION, "ticker": ticker,
               "as_of": dt.date.today().strftime("%Y-%m-%d"),
               "mode": "error", "error": str(e)[:200],
               "warnings": ["fetch_failed"]}
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return 1

    out = build_output(ticker, bars)
    text = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=False)
    if args.out:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p} ({len(bars)} bars)", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
