# Technical Analysis Framework — Complete Reference

Merged from: InvestSkill/technical-analysis (Ichimoku, Volume Profile, Options Flow, MTF, all chart specs)

---

## Trend Indicators

### Moving Averages
- **SMA 20**: Short-term trend
- **SMA 50**: Intermediate trend — institutional benchmark
- **SMA 200**: Long-term trend — bull/bear market divider
- **Golden Cross**: 50d crosses above 200d → Bullish
- **Death Cross**: 50d crosses below 200d → Bearish
- **Price vs MAs**: Above all = strong uptrend, Below all = strong downtrend

### MACD (Moving Average Convergence Divergence)
- MACD Line = EMA(12) - EMA(26)
- Signal Line = EMA(9) of MACD Line
- Histogram = MACD - Signal
- **Bullish crossover**: MACD crosses above Signal
- **Bearish crossover**: MACD crosses below Signal
- **Divergence**: Price makes new high but MACD doesn't (bearish divergence) or vice versa

### ADX (Average Directional Index)
- **> 25**: Trending market (strong directional move)
- **20-25**: Transitional
- **< 20**: Ranging market (no clear trend)
- **+DI > -DI**: Uptrend dominant
- **-DI > +DI**: Downtrend dominant

---

## Momentum Indicators

### RSI (Relative Strength Index, 14-period)
- **> 70**: Overbought — potential pullback
- **50-70**: Bullish momentum
- **30-50**: Bearish momentum
- **< 30**: Oversold — potential bounce
- **Divergence**: Price new high + RSI lower high = bearish warning

### Stochastic Oscillator
- **%K crosses above %D below 20**: Bullish signal
- **%K crosses below %D above 80**: Bearish signal

### Williams %R
- **Above -20**: Overbought zone
- **Below -80**: Oversold zone

---

## Volatility Indicators

### Bollinger Bands (20-period, 2 std dev)
- **Price touches upper band**: Overbought / strong momentum
- **Price touches lower band**: Oversold / selling climax
- **Band squeeze**: Width narrows → Expect breakout
- **%B > 1**: Price above upper band
- **%B < 0**: Price below lower band
- **Bandwidth percentile**: Low = squeeze, High = expansion

### ATR (Average True Range)
- Measures volatility, NOT direction
- Rising ATR = increasing volatility
- Falling ATR = decreasing volatility
- Use for stop-loss distance: 1.5-2x ATR from entry

---

## Volume Indicators

### On-Balance Volume (OBV)
- Cumulative volume: adds volume on up days, subtracts on down days
- Rising OBV + rising price = confirmed uptrend
- Rising OBV + flat price = accumulation (bullish divergence)
- Falling OBV + rising price = distribution (bearish divergence)

### Volume-Weighted Average Price (VWAP)
- Average price weighted by volume for the session
- Price above VWAP = bullish intraday bias
- Price below VWAP = bearish intraday bias
- Institutional benchmark for execution quality

### Accumulation/Distribution Line (A/D)
- Combines price and volume to show money flow
- Rising A/D = accumulation (buying pressure)
- Falling A/D = distribution (selling pressure)
- Divergence from price = early warning of reversal

---

## Advanced: Ichimoku Cloud (一目均衡表)

### Five Components

| Component | Calculation | Period | Purpose |
|-----------|-----------|--------|---------|
| Tenkan-sen (轉換線) | (9-period High + 9-period Low) / 2 | 9 | Short-term trend/momentum |
| Kijun-sen (基準線) | (26-period High + 26-period Low) / 2 | 26 | Medium-term trend/baseline |
| Senkou Span A (先行帶A) | (Tenkan + Kijun) / 2, plotted 26 ahead | Leading | Fast cloud boundary |
| Senkou Span B (先行帶B) | (52-period High + 52-period Low) / 2, plotted 26 ahead | 52 | Slow cloud boundary |
| Chikou Span (遲行帶) | Current close plotted 26 periods back | Lagging | Trend confirmation |

**Kumo (雲帶)** = shaded area between Senkou Span A and B

### Bullish Signals

| Signal | Condition | Strength |
|--------|-----------|----------|
| Price above Cloud | Price > both Span A and B | Base condition |
| Green Cloud | Span A > Span B | Trend support |
| TK Cross (Bullish) | Tenkan crosses above Kijun | Medium |
| TK Cross above Cloud | Bullish TK cross + price above cloud | Strong |
| Chikou above price | Chikou > historical price 26 periods ago | Confirms uptrend |
| **All 5 aligned** | All conditions bullish | **Strongest** |

### Bearish Signals

| Signal | Condition | Strength |
|--------|-----------|----------|
| Price below Cloud | Price < both Span A and B | Base condition |
| Red Cloud | Span B > Span A | Trend resistance |
| TK Cross (Bearish) | Tenkan crosses below Kijun | Medium |
| TK Cross below Cloud | Bearish TK cross + price below cloud | Strong |
| Chikou below price | Chikou < historical price 26 periods ago | Confirms downtrend |
| **All 5 aligned** | All conditions bearish | **Strongest** |

### Kumo Twist
- Span A and B cross → Cloud color changes
- Plotted 26 periods ahead = early warning
- Thin cloud = weak support/resistance
- Thick cloud = strong support/resistance

### Signal Strength Matrix

| # Bullish Conditions | Grade | Bias |
|---------------------|-------|------|
| 5/5 | Maximum Bullish | Strong long |
| 4/5 | Strong Bullish | Long bias |
| 3/5 | Moderate Bullish | Lean long |
| 2/5 | Mixed/Transitioning | Neutral |
| 1/5 or 0/5 | Bearish | Short bias |

---

## Advanced: Volume Profile Analysis

### Key Concepts

| Term | Definition | Trading Implication |
|------|-----------|-------------------|
| **POC** (Point of Control) | Price with highest volume | Magnetic price level, consolidation point |
| **Value Area (VA)** | Price range with ~70% of volume | Fair value zone |
| **VAH** (Value Area High) | Upper VA boundary | Resistance from below |
| **VAL** (Value Area Low) | Lower VA boundary | Support from above |
| **LVN** (Low Volume Node) | Thin volume area | Price passes through quickly |
| **HVN** (High Volume Node) | Dense volume area | Consolidation magnet |

### Volume Profile Shapes

| Shape | Description | Implication |
|-------|------------|-------------|
| Normal (Bell Curve) | Symmetric, clear POC | Balanced, range-bound |
| P-Shape | High volume at top, thin tail below | Short-covering rally, bullish |
| b-Shape | High volume at bottom, thin tail above | Distribution/top, bearish |
| Double Distribution | Two HVNs with LVN gap | Market transitioning, LVN break = direction |
| Thin Profile | Even spread, no clear POC | Trending, follow trend |

### Trading Rules

| Scenario | Action |
|----------|--------|
| Price > VAH | Bullish — buy breakouts with volume |
| Price < VAL | Bearish — sell breakdowns with volume |
| Price at POC | Range-bound — fade edges (buy VAL, sell VAH) |
| Price enters LVN | Expect acceleration — don't fade |
| Price at HVN | Consolidation — mean-reversion |

---

## Advanced: Options Flow Integration

### Put/Call Ratio

| P/C Ratio | Interpretation |
|-----------|---------------|
| < 0.6 | Extreme bullishness / complacency — contrarian warning |
| 0.6–0.7 | Bullish — call buyers dominating |
| 0.7–1.0 | Neutral — balanced |
| 1.0–1.3 | Bearish fear — put buyers dominating |
| > 1.3 | Extreme fear — potential contrarian buy |

### IV vs HV

| Condition | Implication |
|-----------|------------|
| IV >> HV | Options expensive — premium selling opportunity |
| IV ≈ HV | Fairly priced |
| IV << HV | Options cheap — buying opportunity |

- **IV Rank > 50**: Elevated implied volatility
- **IV Percentile > 80%**: Historically very high IV

### Unusual Options Activity (UOA)
- **Large block trades**: Single orders 500+ contracts, especially OTM
- **OTM sweeps**: Aggressive market orders sweeping multiple exchanges at ask — directional conviction
- **Dark pool prints**: Large off-exchange block prints signal institutional action
- **Short-dated OTM calls**: One of the most reliable pre-announcement signals
- **Key UOA filters**: Volume > 5x open interest, expiry within 30 days, OTM strike

### Max Pain Theory
- **Max Pain** = Strike where total outstanding options expire worthless — maximum loss for option buyers
- Near expiration, prices tend to gravitate toward max pain (dealer hedging flows)
- Most useful in final 5-7 days before monthly OPEX
- If stock significantly above max pain near OPEX → short-term mean reversion possible

### Gamma Exposure (GEX)
- **Positive GEX** (dealer long gamma): Suppresses volatility, range-bound
- **Negative GEX** (dealer short gamma): Amplifies moves, increases volatility
- **GEX Flip Level**: Crossing this accelerates directional moves
- **Practical rule**: Low realized vol + tightening range = likely positive GEX. Breakouts more powerful when entering negative GEX zone.

### Data Source Note
> Real-time options flow, IV readings, and GEX levels must be sourced from the user's options data provider (e.g., Market Chameleon, Unusual Whales, SpotGamma, Thinkorswim).

### Session vs Composite Volume Profile
- **Session Profile**: Volume for a single day/week. Identifies intraday POC, VAH, VAL.
- **Composite Profile**: Aggregated over weeks/months. Identifies major structural levels.
- **Rule**: Composite HVNs = major structural S/R. LVNs = breakout acceleration zones. Session POC = short-term magnet.

---

## Multi-Timeframe Analysis (MTF)

### Framework
Analyze 3 timeframes simultaneously — higher TF = trend, primary TF = setup, lower TF = entry.

| Approach | Higher TF (Trend) | Primary TF (Setup) | Lower TF (Entry) |
|----------|-------------------|--------------------|-----------------|
| Day Trading | Weekly | Daily | 1-Hour |
| Swing Trading | Monthly | Weekly | Daily |
| Position Trading | Quarterly | Monthly | Weekly |

### MTF Alignment Scoring

| Score | Interpretation | Action |
|-------|---------------|--------|
| 3/3 Bullish | All timeframes confirm uptrend | Strong long setup |
| 3/3 Bearish | All timeframes confirm downtrend | Strong short setup |
| 2/3 Aligned | Primary direction clear, minor conflict | Moderate setup, lean majority |
| 1/3 Aligned | Conflicting — no clear direction | Avoid, wait for clarity |
| 0/3 | Contradiction across all | No trade |

**Rule**: Never act on 1/3 or lower. Wait for 2/3 minimum.

---

## Chart Pattern Recognition

### Reversal Patterns
- Head & Shoulders / Inverse H&S
- Double/Triple tops and bottoms
- Shooting Star, Hammer, Doji (candlestick)
- Engulfing patterns (bullish/bearish)

### Continuation Patterns
- Flags and Pennants
- Ascending/Descending/Symmetrical Triangles
- Cup and Handle
- Wedges and Channels

### Key Levels
- Fibonacci retracements: 23.6%, 38.2%, 50%, 61.8%, 78.6%
- Pivot points (daily, weekly)
- Round number psychology ($100, $200, 20000 for TAIEX)
- Gap fills

---

## Indicator Combinations by Strategy

| Strategy | Indicators |
|----------|-----------|
| Trend Following | SMA 50/200 + MACD + ADX |
| Mean Reversion | Bollinger Bands + RSI + Stochastic |
| Momentum | RSI + MACD + Volume |
| Breakout | Bollinger squeeze + Volume + Pattern |
| Ichimoku Complete | All 5 Ichimoku components + Volume |

---

## Chart Specifications (for Chart MCP generation)

### Price Chart
- Candlestick with SMA 20 (blue), 50 (orange), 200 (purple)
- Support/resistance as horizontal dashed lines
- Green candles up, Red candles down

### Volume Bars
- Green (up days), Red (down days)
- 20-day average as dashed line
- Highlight bars >2x average

### RSI Panel
- RSI line (blue), 70 overbought (red zone), 30 oversold (green zone)
- Midline 50 (dashed gray)

### MACD Panel
- MACD line (blue), Signal (red), Histogram (green/red)
- Zero line (black dashed)

### Timeframe Selection
- Day Trading: 1-min to 1-hour, last 5-10 days
- Swing Trading: 4-hour to daily, last 3-6 months
- Position Trading: Daily to weekly, last 1-3 years
