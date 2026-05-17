# Complete Indicator List with FRED Series IDs, Thresholds, and Interpretation

Merged from: InvestSkill/economics-analysis, data-snapshot/indicators-us.md, data-snapshot/indicators-tw.md, data-snapshot/indicators-global.md

---

## Yield Curve Analysis

### Key Spreads to Monitor

| Spread | FRED Series | Definition | Signal |
|--------|-------------|-----------|--------|
| 2s10s | T10Y2Y | 10yr Treasury minus 2yr Treasury | Most watched recession indicator |
| 3M10Y | T10Y3M | 10yr Treasury minus 3-Month T-Bill | **Historically strongest recession predictor** (NY Fed model) |
| 5s30s | — | 30yr Treasury minus 5yr Treasury | Long-end curve shape |

### Yield Curve Shapes

| Shape | Description | Economic Implication |
|-------|------------|---------------------|
| Normal (Steep) | Long-term rates well above short-term | Healthy growth expectations, bank margins expanding |
| Flat | Short and long-term rates near parity | Late-cycle signal, growth slowing, Fed near peak |
| Inverted | Short-term rates above long-term rates | Recession warning — markets pricing rate cuts ahead |
| Bear Steepening | Both ends rise, long end rises faster | Inflation concern, term premium expanding |
| Bull Steepening | Both ends fall, short end falls faster | Cutting cycle underway, growth relief expected |

### Inversion Duration and Recession Lead Time

| Inversion Duration | Historical Recession Lead Time |
|--------------------|-------------------------------|
| < 3 months | Unreliable signal |
| 3–6 months | 12–18 months typically |
| 6–12 months | 6–15 months typically |
| > 12 months | High confidence; within 12 months |

**Rule of thumb**: Yield curve uninversion (re-steepening after inversion) is often the more immediate warning — recession tends to arrive shortly after the curve re-steepens.

### Fed Rate Cycle Positioning
- **Hiking Cycle**: Short end rises faster, curve flattens/inverts. Growth stocks under pressure.
- **Pause**: Curve stabilizes. Markets watch for pivot signals.
- **Cutting Cycle**: Short end falls faster, curve steepens. Risk-on, cyclicals and growth benefit.

### Real Yields (TIPS) Analysis
- **Real Yield** = Nominal Treasury Yield − Breakeven Inflation Rate
- **Rising real yields**: Tighten financial conditions. Negative for long-duration assets.
- **Falling real yields**: Easier financial conditions. Positive for growth, gold, EM.
- **10-Year Real Yield thresholds**: Below 0% = historically accommodative; above 2% = meaningfully restrictive.
- **Breakeven inflation** (5Y forward): Persistently above 2.5% signals inflation concern.

---

## Credit Market Indicators

### Investment Grade (IG) Credit Spreads (OAS)

| Spread Level | Condition | Interpretation |
|-------------|-----------|---------------|
| < 100 bps | Normal | Risk appetite healthy, credit markets functioning |
| 100–150 bps | Caution | Stress emerging, watch for tightening conditions |
| > 150 bps | Stress | Credit markets seizing, risk-off, watch equities |

### High Yield (HY) Credit Spreads

| FRED Series | BAMLH0A0HYM2 |
|------------|---------------|

| Spread Level | Condition | Interpretation |
|-------------|-----------|---------------|
| < 350 bps | Normal | Benign default environment, strong risk appetite |
| 350–500 bps | Caution | Elevated risk aversion, avoid lower-quality credits |
| > 500 bps | Distress | Recession/financial stress scenario |
| > 800 bps | Crisis | Systemic credit event risk (2008/2020 levels) |

**Rule**: HY spreads lead equity markets by 2–4 weeks on average. Widening HY spreads while equities hold = warning signal.

### TED Spread
- 3-Month SOFR minus 3-Month T-Bill yield
- **Normal**: < 50 bps
- **Elevated stress**: 50–100 bps
- **Crisis signal**: > 100 bps (peaked ~450 bps during 2008 GFC)

### MOVE Index (Bond Market Volatility)
- Bond market equivalent of VIX
- **Normal**: 80–100
- **Elevated**: 100–130 (policy uncertainty)
- **Crisis**: > 150 (1994, 2008, 2020, 2023 banking crisis)

### Credit as a Leading Indicator
- **IG/HY spread widening** before equity weakness = leading warning
- **Spread compression** while equities lag = catch-up potential
- **IG vs HY divergence**: HY widens but IG holds = idiosyncratic credit stress
- **Leveraged loan market**: CLO issuance and leveraged loan spreads reflect private credit conditions

---

## US Growth & Output Indicators

| Indicator | FRED Series | Frequency | Unit | Threshold |
|-----------|-------------|-----------|------|-----------|
| Real GDP Growth (QoQ ann.) | A191RL1Q225SBEA | Quarterly | % | <0% = contraction, >3% = strong |
| GDP Now (Atlanta Fed) | GDPNOW | Daily | % | Real-time GDP estimate |
| Industrial Production | INDPRO | Monthly | Index | MoM decline 3+ months = warning |
| Capacity Utilization | TCU | Monthly | % | >80% = inflation pressure |

## US Labor Market

| Indicator | FRED Series | Frequency | Unit | Threshold |
|-----------|-------------|-----------|------|-----------|
| Unemployment Rate (U-3) | UNRATE | Monthly | % | <4% = tight, >6% = significant slack |
| U-6 Unemployment | U6RATE | Monthly | % | Broader measure including underemployed |
| Nonfarm Payrolls | PAYEMS | Monthly | Thousands | <100K = weak, >200K = strong |
| Avg Hourly Earnings YoY | CES0500000003 | Monthly | $/hr | >4% = wage inflation concern |
| Initial Jobless Claims | ICSA | Weekly | Thousands | >300K = deteriorating, <200K = very tight |
| Continuing Claims | CCSA | Weekly | Thousands | Trend matters more than level |
| Job Openings (JOLTS) | JTSJOL | Monthly | Thousands | Declining = cooling labor market |
| Quits Rate | JTSQUR | Monthly | % | High = worker confidence |
| Labor Force Participation | CIVPART | Monthly | % | Structural vs cyclical changes |

## US Inflation

| Indicator | FRED Series | Frequency | Unit | Threshold |
|-----------|-------------|-----------|------|-----------|
| CPI All Items YoY | CPIAUCSL | Monthly | % | Fed target ~2%, >3% = concern, >5% = serious |
| Core CPI YoY | CPILFESL | Monthly | % | Excludes food & energy |
| **Core PCE YoY** | **PCEPILFE** | **Monthly** | **%** | **Fed's preferred — 2% target** |
| PCE Price Index YoY | PCEPI | Monthly | % | Broader than CPI |
| PPI Final Demand YoY | PPIFIS | Monthly | % | Leads CPI |
| 5Y Breakeven Inflation | T5YIE | Daily | % | Market inflation expectations |
| 10Y Breakeven Inflation | T10YIE | Daily | % | Long-run inflation expectations |
| UMich Inflation Expectations | MICH | Monthly | % | Consumer inflation expectations |

## US Interest Rates & Monetary Policy

| Indicator | FRED Series | Frequency | Unit |
|-----------|-------------|-----------|------|
| Fed Funds Rate (Upper) | DFEDTARU | Daily | % |
| Fed Funds Effective | DFF | Daily | % |
| 2-Year Treasury | DGS2 | Daily | % |
| 5-Year Treasury | DGS5 | Daily | % |
| 10-Year Treasury | DGS10 | Daily | % |
| 30-Year Treasury | DGS30 | Daily | % |
| 10Y-2Y Spread | T10Y2Y | Daily | % |
| 10Y-3M Spread | T10Y3M | Daily | % |
| 3-Month T-Bill | DTB3 | Daily | % |
| Fed Balance Sheet | WALCL | Weekly | Millions $ |
| Reverse Repo | RRPONTSYD | Daily | Billions $ |
| 30Y Mortgage Rate | MORTGAGE30US | Weekly | % |

## US Sentiment & Activity

| Indicator | FRED Series | Frequency | Threshold |
|-----------|-------------|-----------|-----------|
| UMich Consumer Sentiment | UMCSENT | Monthly | <70 = pessimistic |
| ISM Manufacturing PMI | — (Yahoo) | Monthly | >50 = expansion, <50 = contraction |
| ISM Services PMI | — (Yahoo) | Monthly | >50 = expansion |
| Retail Sales MoM | RSAFS | Monthly | Negative = consumer weakness |
| Personal Saving Rate | PSAVERT | Monthly | Low = stretched, High = cautious |

## US Financial Conditions

| Indicator | FRED Series | Frequency | Interpretation |
|-----------|-------------|-----------|---------------|
| Chicago Fed NFCI | NFCI | Weekly | 0 = average, positive = tight |
| St. Louis Fin. Stress | STLFSI2 | Weekly | Higher = more stress |
| HY Spread | BAMLH0A0HYM2 | Daily | See credit section above |
| IG Spread | BAMLC0A0CM | Daily | See credit section above |
| VIX | ^VIX (Yahoo) | Daily | <15 = complacent, 15-25 = normal, >35 = panic |

## US Housing

| Indicator | FRED Series | Frequency |
|-----------|-------------|-----------|
| Housing Starts | HOUST | Monthly |
| Building Permits | PERMIT | Monthly |
| Case-Shiller Home Price | CSUSHPINSA | Monthly |

---

## Global Macro Comparison

### Economic Cycle Positioning Template

| Economy | Phase | GDP Growth | Inflation | Policy Stance | Equity Implication |
|---------|-------|-----------|-----------|---------------|-------------------|
| United States | | | | | |
| Eurozone | | | | | |
| China | | | | | |
| Japan | | | | | |
| Taiwan | | | | | |
| UK | | | | | |

Phases: Early Expansion → Mid Expansion → Late Expansion → Contraction → Recovery

### PMI Comparison

| Country/Region | PMI Index | Reading | Trend | Above/Below 50 |
|---------------|-----------|---------|-------|----------------|
| US | ISM Mfg | | | |
| US | ISM Services | | | |
| Eurozone | Markit Mfg | | | |
| China | Caixin Mfg | | | |
| China | Official PMI | | | |

**Rule**: Composite PMI below 48 for 2+ months = recessionary signal.

### Central Bank Divergence

| Central Bank | Current Rate | Last Move | Next Expected | Cycle Phase |
|-------------|-------------|-----------|--------------|-------------|
| Federal Reserve | | | | |
| ECB | | | | |
| BOJ | | | | |
| BOE | | | | |
| PBOC | | | | |
| Taiwan CBC | | | | |

**Divergence signals:**
- Fed tightening while ECB/BOJ easing → USD strengthens, EM weakens
- Synchronized easing → Global risk-on, EM outperforms, commodities bid
- BOJ normalization → JPY strengthens, unwinds carry trades

### DXY Impact Matrix

| DXY Direction | US Multinationals | Commodities | EM | US Small-Caps |
|--------------|------------------|------------|-----|--------------|
| Strengthening | Headwind (FX translation) | Bearish | Bearish | Relative outperform |
| Weakening | Tailwind | Bullish | Bullish | Relative underperform |

- **DXY > 105**: Meaningful headwind for S&P 500 multinationals (~40% foreign revenue)
- **DXY < 95**: Significant tailwind

---

## Taiwan-Specific Indicators

### Stock Market (TWSE MCP)
- 加權股價指數 (TAIEX) — ^TWII via Yahoo Finance
- 成交量: 正常 2000-3000 億/日, >4000 億=高量, <1500 億=量縮
- 外資買賣超: 連續 5 日同方向=趨勢性, 單日 >200 億=大量
- 投信/自營商買賣超
- 融資餘額: 大增+上漲=散戶追高(警戒), 大減+下跌=恐慌殺出

### Key Economic (CBC/DGBAS, via web-research)
- 重貼現率: CBC 基準利率, 每季調整 (3/6/9/12月), 每次 0.125% (半碼)
- GDP 成長率, CPI, 核心 CPI, 失業率, 薪資成長率
- 外銷訂單: 連續 N 月年增/年減 = 出口景氣判斷
- 景氣燈號: 紅(38-45)=過熱, 黃紅(32-37), 綠(23-31)=穩定, 黃藍(17-22), 藍(9-16)=衰退
- 外匯存底, M2 貨幣供給年增率

### Taiwan Sector Classification
| Sector | Representative | Weight |
|--------|---------------|--------|
| 半導體 | 台積電(2330), 聯發科(2454) | ~40% |
| 電子零組件 | 鴻海(2317), 台達電(2308) | ~15% |
| 金融保險 | 富邦金(2881), 國泰金(2882) | ~12% |
| 航運 | 長榮(2603), 陽明(2609) | ~3% |
| 塑化 | 台塑(1301), 南亞(1303) | ~3% |

### Taiwan Economic Calendar
- 每月 7 日前: 海關進出口統計
- 每月 5-10 日: CPI/WPI
- 每月 20 日前: 外銷訂單
- 每月月底: 失業率、工業生產
- 每季末+1 月: GDP
- 3/6/9/12 月: 央行理監事會議
- 每月 27 日前後: 景氣燈號

---

## Cross-Market Signal Regimes

| Regime | Equities | VIX | DXY | Gold | HY Spreads | EM |
|--------|---------|-----|-----|------|-----------|-----|
| **Risk-On** | ↑ | ↓ | ↓ | ↓ | ↓ | ↑ |
| **Risk-Off** | ↓ | ↑ | ↑ | ↑ | ↑ | ↓ |
| **Reflation** | Cyclicals ↑ | — | ↓ | — | ↓ | ↑ |
| **Deflation Fear** | ↓ | ↑ | — | ↑ | ↑ | ↓ |
| **Stagflation** | ↓ | ↑ | — | ↑ | ↑ | ↓ |

---

## US Release Calendar (approximate)
- **Weekly**: Jobless Claims (Thu), Fed Balance Sheet (Thu)
- **Monthly Week 1**: ISM Mfg PMI (1st biz day), Nonfarm Payrolls (1st Fri)
- **Monthly Week 2**: CPI (10th-14th), PPI (same week)
- **Monthly Week 3**: Retail Sales, Housing Starts, Industrial Production
- **Monthly Week 4**: PCE, Personal Income/Spending, Consumer Confidence
- **Quarterly**: GDP (advance ~4 weeks after quarter end)
- **FOMC**: 8 meetings/year (~every 6 weeks)

## Global Central Banks Calendar
| Central Bank | Meetings/Year |
|-------------|---------------|
| Fed (FOMC) | 8 |
| ECB | 8 |
| BOJ | 8 |
| BOE | 8 |
| Taiwan CBC | 4 (Mar/Jun/Sep/Dec) |
| PBOC | LPR fixing monthly (20th) |
