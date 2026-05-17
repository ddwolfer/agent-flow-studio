# Recession Probability Scoring & Risk Assessment

Merged from: InvestSkill/economics-analysis (recession probability section), economic-models.md (business cycle)

---

## Recession Probability Models

### 1. New York Fed Recession Model

Based on the 3M10Y yield curve spread. Monthly publication.

| Probability Range | Interpretation |
|-------------------|---------------|
| 0–10% | Expansion — very low recession risk |
| 10–25% | Low risk — monitor indicators |
| 25–50% | Elevated — caution warranted |
| 50–75% | High risk — recession likely within 12 months |
| > 75% | Near-certain — defensive positioning required |

**Data**: FRED series for 10Y-3M spread (T10Y3M). NY Fed publishes model output monthly.

### 2. Conference Board Leading Economic Index (LEI)

Composite of 10 leading indicators across financial markets, labor, manufacturing, and consumer expectations.

**Components**: Manufacturing hours, building permits, consumer expectations, credit spread, yield curve, stock prices, initial jobless claims, ISM new orders, capital goods orders, consumer goods orders.

**Signals**:
- **Consecutive monthly declines (3+)**: Strong recession warning
- **Year-over-year decline > 4%**: Historically aligned with recessions
- **YoY decline > 6%**: Near-certain recession signal

### 3. Sahm Rule

**Formula**: Current 3-month average unemployment rate minus the minimum 3-month average over the prior 12 months.

**Threshold: ≥ 0.5 percentage points** = Real-time recession signal

- Triggered in every US recession since 1970
- Works in real-time without revision lag
- High historical accuracy, very few false positives
- FRED series: SAHMREALTIME

### 4. Custom Composite Recession Probability

Scoring model combining multiple indicators:

| Component | Weight | Data Source | Threshold for Warning |
|-----------|--------|-------------|----------------------|
| 3M10Y Yield Curve | 25% | FRED T10Y3M | Inverted >3 months |
| LEI YoY Change | 20% | Conference Board | Declining >3 months |
| Sahm Rule | 20% | FRED SAHMREALTIME | ≥0.5pp |
| HY Credit Spreads | 15% | FRED BAMLH0A0HYM2 | >500 bps |
| ISM Mfg PMI | 10% | ISM | <48 for 2+ months |
| Initial Claims Trend | 10% | FRED ICSA | Rising >20% from trough |

### Composite Score Interpretation

| Zone | Score | Interpretation | Positioning |
|------|-------|---------------|-------------|
| Expansion | 0–25% | Risk-on; cyclicals, growth outperform | Overweight equities, underweight bonds |
| Caution | 25–50% | Balanced; reduce cyclical overweights | Diversify, increase quality |
| High Risk | 50–75% | Defensive rotation; increase quality, reduce leverage | Overweight bonds, defensive sectors |
| Near-Certain | 75–100% | Full defensive; cash, defensives, short vol | Maximize capital preservation |

---

## Historical Recession Episodes & Leading Indicators

| Recession | Yield Curve Inversion | LEI Decline | Sahm Trigger | S&P 500 Peak-to-Trough | Duration |
|-----------|-----------------------|-------------|-------------|------------------------|----------|
| 1990-91 (S&L Crisis) | 1989 | Yes | Yes | −20% | 8 months |
| 2001 (Dot-com) | 2000 | Yes | Yes | −49% | 8 months |
| 2008 (GFC) | 2006–2007 | Yes | Yes | −57% | 18 months |
| 2020 (COVID) | 2019 | Yes | Yes | −34% | 2 months |
| 2022-2023 (NOT recession) | 2022-2023 | Yes | No | −25% (bear market) | N/A |

**Note on 2022-2023**: Yield curve inverted and LEI declined, but Sahm Rule did NOT trigger and it was not officially a recession. This is a critical counter-example showing that not all inversions lead to recessions. The aggressive Fed tightening caused a bear market without an NBER-defined recession.

---

## Business Cycle Phase Identification

### Phase Indicators Matrix

| Indicator | Early Expansion | Mid Expansion | Late Expansion | Contraction |
|-----------|----------------|---------------|----------------|-------------|
| GDP | Accelerating | Steady >2% | Slowing | Negative |
| Employment | Recovering | Full employment | Tight, wage pressure | Rising jobless |
| Inflation | Low/falling | Moderate ~2% | Rising >3% | Falling |
| Policy | Easing | Neutral | Tightening | Emergency ease |
| Yield Curve | Steep | Flattening | Flat/inverted | Steepening |
| Credit Spreads | Narrowing | Tight | Widening | Very wide |
| Corp Margins | Expanding | Peak | Compressing | Trough |
| Equities | Strongest returns | Good returns | Lower returns, high vol | Negative, bottoming |
| Best Sectors | Cyclicals, small-caps | Broad | Defensives, quality | Bonds, cash, then early cyclicals |

### Credit Cycle Overlay

1. **Recovery**: Defaults peak, spreads start narrowing, credit tightening eases
2. **Expansion**: Low defaults, tight spreads, easy credit, leverage builds
3. **Downturn**: Spreads widen, defaults rise, credit tightens, deleveraging
4. **Repair**: Balance sheets cleaned up, conservative lending, next cycle setup

**Warning**: Peak profit margins are a WARNING signal, not a comfort signal. Margin compression follows.

---

## Emerging Market Vulnerability

When assessing global recession spillover:
- **EM FX pressure**: Current account deficits + elevated external USD debt = vulnerable to dollar strength
- **EM Debt Stress**: Sovereign spread widening (EMBI+ spread)
- **Capital outflow risks**: Rate differential between US and EM
- **China contagion**: Property sector stress, credit impulse, stimulus effectiveness
- **Commodity EMs**: Benefit from commodity supercycles, hurt by USD strength
