"""BTC 大週期 / 部位風險資料 — crypto-daily 的預載來源。

補上 crypto-daily 原本缺的「確定性市場結構數據」:LLM 只負責敘述,
所有數字都由本腳本算出,和 compute_zones.py 同樣的分工。

抓什麼(每個來源獨立容錯,失敗只影響自己那一塊):
  1. 幣本位資金費率 (dapi BTCUSD_PERP) — 現值 + 10/30 天/全期均值、負值佔比
     為什麼:幣本位長抱多單的持有成本,和 U 本位費率常常不同,
     morning-briefing 的 fetch_extras 只抓 U 本位 (fapi BTCUSDT)。
  2. KDJ(9,3,3) 4h / 1d / 1w — 使用者指定的三個週期
  3. 200 日均線 + 乖離% — 週期位置的客觀錨
  4. 全網難度 + 近期調整幅度 — 礦工投降訊號(難度下調 = 礦工關機)
     為什麼:「挖礦成本地板」會隨難度下調而下移,不是固定支撐。
  5. 全網算力

用法:
  python fetch_btc_cycle.py --output reports/crypto-daily/_extras/2026-07-29.json
"""
import argparse
import datetime
import json
import pathlib
import statistics
import sys

import httpx

_TIMEOUT = 20.0
_DAPI = "https://dapi.binance.com/dapi/v1"          # coin-margined 幣本位
_SPOT = "https://api.binance.com/api/v3"
_CHAIN = "https://api.blockchain.info/charts"

# 資金費率每 8h 結算一次 → 一年 3*365 期
_FUNDING_PERIODS_PER_YEAR = 3 * 365


# ── 1. 幣本位資金費率 ────────────────────────────────────────────────────────
def fetch_coinm_funding(symbol: str = "BTCUSD_PERP",
                        timeout: float = _TIMEOUT) -> dict:
    """幣本位永續的資金費率現值 + 歷史統計(年化)。"""
    try:
        pi = httpx.get(f"{_DAPI}/premiumIndex", params={"symbol": symbol},
                       timeout=timeout).json()
        if isinstance(pi, list):
            pi = pi[0]
        hist = httpx.get(f"{_DAPI}/fundingRate",
                         params={"symbol": symbol, "limit": 1000},
                         timeout=timeout).json()
        rates = [float(x["fundingRate"]) for x in hist]
        if not rates:
            return {"error": "empty fundingRate history"}

        def window(n):
            sub = rates[-n:] if n else rates
            m = statistics.mean(sub)
            return {
                "samples": len(sub),
                "mean_per_8h_pct": round(m * 100, 6),
                "annualized_pct": round(m * _FUNDING_PERIODS_PER_YEAR * 100, 3),
                "negative_share_pct": round(
                    sum(1 for r in sub if r < 0) / len(sub) * 100, 1),
            }

        return {
            "symbol": symbol,
            "mark_price": float(pi["markPrice"]),
            "current_rate_per_8h_pct": round(float(pi["lastFundingRate"]) * 100, 6),
            "current_annualized_pct": round(
                float(pi["lastFundingRate"]) * _FUNDING_PERIODS_PER_YEAR * 100, 3),
            "next_funding_utc": datetime.datetime.utcfromtimestamp(
                int(pi["nextFundingTime"]) / 1000).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_10d": window(30),      # 30 筆 ≈ 10 天
            "window_30d": window(90),
            "window_all": window(0),
            "max_per_8h_pct": round(max(rates) * 100, 6),
            "min_per_8h_pct": round(min(rates) * 100, 6),
            "note": "負值代表空方付錢給多方(做多者收錢)",
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 2. KDJ ───────────────────────────────────────────────────────────────────
def _klines(symbol: str, interval: str, limit: int, timeout: float) -> list:
    r = httpx.get(f"{_SPOT}/klines",
                  params={"symbol": symbol, "interval": interval, "limit": limit},
                  timeout=timeout)
    return [{"h": float(k[2]), "l": float(k[3]), "c": float(k[4])} for k in r.json()]


def _kdj(bars: list, n: int = 9) -> dict:
    """KDJ(9,3,3):K/D 用 1/3 平滑,J = 3K - 2D。"""
    k = d = 50.0
    for i, b in enumerate(bars):
        w = bars[max(0, i - n + 1): i + 1]
        hi = max(x["h"] for x in w)
        lo = min(x["l"] for x in w)
        rsv = 50.0 if hi == lo else (b["c"] - lo) / (hi - lo) * 100
        k = 2 / 3 * k + 1 / 3 * rsv
        d = 2 / 3 * d + 1 / 3 * k
    return {"k": round(k, 2), "d": round(d, 2), "j": round(3 * k - 2 * d, 2)}


def fetch_kdj(symbol: str = "BTCUSDT", timeout: float = _TIMEOUT) -> dict:
    """4h / 1d / 1w 三週期 KDJ。超買 >80、超賣 <20。"""
    out = {"symbol": symbol,
           "zones": {"overbought": 80, "oversold": 20},
           "note": "多週期分歧屬常態;以較大週期為主,小週期僅微調"}
    for label, interval in (("4h", "4h"), ("1d", "1d"), ("1w", "1w")):
        try:
            out[label] = _kdj(_klines(symbol, interval, 200, timeout))
        except Exception as e:
            out[label] = {"error": f"{type(e).__name__}: {e}"}
    return out


# ── 3. 200 日均線 ────────────────────────────────────────────────────────────
def fetch_ma200(symbol: str = "BTCUSDT", timeout: float = _TIMEOUT) -> dict:
    try:
        bars = _klines(symbol, "1d", 201, timeout)
        closes = [b["c"] for b in bars][-201:]
        price = closes[-1]
        ma = sum(closes[-201:-1]) / 200
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "ma200": round(ma, 2),
            "deviation_pct": round((price / ma - 1) * 100, 2),
            "above_ma200": price > ma,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── 4-5. 難度 / 算力 ─────────────────────────────────────────────────────────
def _chart(name: str, span: str, timeout: float) -> list:
    r = httpx.get(f"{_CHAIN}/{name}",
                  params={"timespan": span, "format": "json"}, timeout=timeout)
    return [{"t": datetime.datetime.utcfromtimestamp(v["x"]).strftime("%Y-%m-%d"),
             "v": v["y"]} for v in r.json()["values"]]


def fetch_difficulty(timeout: float = _TIMEOUT) -> dict:
    """全網難度 + 近期調整幅度。連續大幅下調 = 礦工投降。"""
    try:
        pts = _chart("difficulty", "1year", timeout)
        adj, prev = [], None
        for p in pts:
            if prev is None:
                prev = p["v"]
                continue
            if abs(p["v"] - prev) / prev > 1e-9:
                adj.append({"date": p["t"], "pct": round((p["v"] / prev - 1) * 100, 2)})
                prev = p["v"]
        recent = adj[-6:]
        return {
            "latest": pts[-1]["v"],
            "as_of": pts[-1]["t"],
            "recent_adjustments": recent,
            "capitulation_signals_1y": [a for a in adj if a["pct"] <= -5],
            "note": "難度下調 = 礦工關機投降;連續下調代表挖礦成本地板正在下移",
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def fetch_hashrate(timeout: float = _TIMEOUT) -> dict:
    try:
        pts = _chart("hash-rate", "1year", timeout)
        latest = pts[-1]["v"]
        ago30 = pts[-31]["v"] if len(pts) > 31 else pts[0]["v"]
        # blockchain.info /charts/hash-rate 回傳單位是 TH/s(1 EH/s = 1e6 TH/s)。
        # 標成 GH/s 會讓報告差 1000 倍 — 這裡明確換算好再交給 prompt。
        return {
            "latest_th_s": latest,
            "latest_eh_s": round(latest / 1e6, 1),
            "as_of": pts[-1]["t"],
            "change_30d_pct": round((latest / ago30 - 1) * 100, 2) if ago30 else None,
        }
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── orchestration ────────────────────────────────────────────────────────────
def collect_all() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    return {
        "generated_at_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coinm_funding": fetch_coinm_funding(),
        "kdj": fetch_kdj(),
        "ma200": fetch_ma200(),
        "difficulty": fetch_difficulty(),
        "hashrate": fetch_hashrate(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="path to write JSON")
    args = ap.parse_args(argv)
    data = collect_all()
    out = pathlib.Path(args.output).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    print(f"[fetch_btc_cycle] wrote {out} ({len(json.dumps(data))} bytes)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
