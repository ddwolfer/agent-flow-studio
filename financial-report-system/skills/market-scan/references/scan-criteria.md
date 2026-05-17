# Scan Criteria and Alert Thresholds

---

## Price Movement Alerts

| Condition | Threshold | Signal Type |
|-----------|-----------|-------------|
| Large daily move (up) | >+5% | Potential breakout / news event |
| Large daily move (down) | <-5% | Potential breakdown / bad news |
| Gap up | >+2% from previous close | Event-driven, earnings, news |
| Gap down | <-2% from previous close | Event-driven, negative catalyst |
| 52-week high | New high | Breakout, momentum |
| 52-week low | New low | Breakdown, potential value trap |
| Limit up (台股) | +10% | 漲停 — maximum daily move |
| Limit down (台股) | -10% | 跌停 — maximum daily move |

## Volume Alerts

| Condition | Threshold | Signal |
|-----------|-----------|--------|
| Volume spike | >3x 20-day average | Unusual activity, possible event |
| Extreme volume | >5x 20-day average | Major event, institutional action |
| Volume dry-up | <0.3x 20-day average | Disinterest, low liquidity |

## Taiwan-Specific (TWSE) Alerts

| Condition | Threshold | Signal |
|-----------|-----------|--------|
| 外資單日買超 | >200 億 | 大量外資流入 |
| 外資單日賣超 | >200 億 | 大量外資流出 |
| 外資連續買超 | >5 日 | 趨勢性買進 |
| 外資連續賣超 | >5 日 | 趨勢性賣出 |
| 融資大增 + 指數上漲 | 融資增 >30 億 | 散戶追高警戒 |
| 融資大減 + 指數下跌 | 融資減 >30 億 | 恐慌性殺出 |
| 成交量 | >4000 億/日 | 高量 (活躍) |
| 成交量 | <1500 億/日 | 量縮 (觀望) |

## Index-Level Alerts

| Condition | Threshold | Signal |
|-----------|-----------|--------|
| VIX | >35 | Panic — potential contrarian buy |
| VIX | <12 | Extreme complacency — caution |
| VIX daily spike | >+30% in one day | Fear event |
| DXY breakout | >105 | EM headwind, multinational headwind |
| DXY breakdown | <95 | EM tailwind, commodity support |
| Gold > $2500 | New ATH area | Risk-off / inflation hedge demand |
| Oil > $100 | Above $100/bbl | Cost-push inflation concern |

## Ranking Logic

### Top Movers Ranking
1. Sort all stocks by |daily change %|
2. Filter: volume > 1x 20-day average (exclude low-liquidity noise)
3. Display top 10 gainers and top 10 losers

### Volume Spike Ranking
1. Calculate: today's volume / 20-day average volume
2. Filter: ratio > 2x
3. Sort by ratio descending
4. Display top 10

### Sector Momentum Ranking
1. Calculate each sector's 1-week, 1-month, 3-month relative return vs index
2. Rank by composite momentum score (weighted: 50% 1-month, 30% 3-month, 20% 1-week)
3. Top 3 = leaders, Bottom 3 = laggards
