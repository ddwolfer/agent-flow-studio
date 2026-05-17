# Market Regime Detection Framework

Merged from: claude-trading-skills/regime-detection

---

## Four-Quadrant Regime Model

Two orthogonal axes define the regime:

|  | Low Volatility | High Volatility |
|---|---|---|
| **Trending** | Q1: Clean trend — trend-following works best | Q2: Volatile trend — momentum with caution |
| **Ranging** | Q3: Quiet range — mean-reversion works best | Q4: Choppy chaos — reduce or sit out |

## Classification Inputs

### 1. ATR Volatility Percentile
Current ATR ranked against 100-day history:
- **< 25th percentile** → Low volatility regime
- **25th–75th** → Normal volatility
- **> 75th percentile** → High volatility regime

### 2. ADX Trend Strength
- **ADX > 25** → Trending market
- **ADX 20-25** → Transitional
- **ADX < 20** → Ranging market

### 3. Hurst Exponent (optional, for deeper analysis)
- **H < 0.4** → Mean-reverting (anti-persistent)
- **0.4 ≤ H ≤ 0.6** → Random walk
- **H > 0.6** → Trending (persistent)

### 4. Bollinger Band Width
BB width percentile — "squeeze" (low percentile) often precedes breakout.

## Strategy Adaptation by Regime

| Regime | Position Size | Stop Width | Strategy Type | Risk Level |
|--------|-------------|-----------|--------------|-----------|
| Q1: Low vol + trending | Full (100%) | Tight (1-2 ATR) | Trend-following | Normal |
| Q2: High vol + trending | Half (50%) | Wide (2-3 ATR) | Momentum, reduced size | Elevated |
| Q3: Low vol + ranging | Full (100%) | Tight | Mean-reversion, range trades | Normal |
| Q4: High vol + ranging | Quarter (25%) or cash | Very wide or N/A | Reduce exposure, wait | High |
| Regime transition | Minimum size | Widened | Flatten or observe | Elevated |

## Additional Regime Indicators

### VIX Term Structure
- **Contango** (VIX < VIX futures): Normal, complacent — favors risk-on
- **Backwardation** (VIX > VIX futures): Fear, hedging demand — risk-off signal
- **Steep contango** (spread > 5%): Extreme complacency — contrarian warning

### Market Breadth as Regime Confirm
- **> 70% stocks above 200d MA**: Broad uptrend regime confirmed
- **30-70%**: Mixed/transitional
- **< 30%**: Broad downtrend regime, even if index holds up (narrow leadership)

### Volume as Regime Confirm
- High volume + trend → Strong conviction, ride it
- Low volume + trend → Drift, unreliable
- High volume + range → Distribution or accumulation, watch for breakout
- Low volume + range → Dead market, skip

## Regime Transition Detection

Watch for:
1. **Bollinger Band squeeze** → Imminent breakout from Q3 to Q1/Q2
2. **VIX spike from low levels** → Transition from Q1/Q3 to Q2/Q4
3. **ADX rising from below 20** → Transition from ranging to trending
4. **ADX falling from above 30** → Trend exhaustion, potential range ahead
