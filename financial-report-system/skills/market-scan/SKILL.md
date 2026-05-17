---
name: market-scan
description: "Comprehensive market scanning covering global indices, sector rotation, fund flows, technical signals, and notable movers. Use when: user wants market overview, sector performance, fund flow analysis, '市場掃描', '盤勢', '類股表現', '資金流向', 'sector rotation', 'market overview', index check, or asks what's moving today. Not for deep macro analysis (use /macro-analysis) or single-stock deep dive."
argument-hint: [focus: indices | sectors | flows | movers | technicals | regime | all]
effort: high
user-invocable: true
---

# Market Scan — 全方位市場掃描

Perform comprehensive market condition scan across global indices, sector rotation, institutional fund flows, technical regime, and notable movers.

## Reference Files

**Load relevant references based on scan scope:**

| File | Purpose | Load When |
|------|---------|-----------|
| [indices.md](references/indices.md) | Global index tickers, thresholds, cross-market signals | Always |
| [tw-sectors.md](references/tw-sectors.md) | Taiwan sector classification, representative stocks, cycle mapping | sectors/flows/all |
| [us-sectors.md](references/us-sectors.md) | S&P 500 11 sectors, cycle positioning, ETF tickers | sectors/all |
| [scan-criteria.md](references/scan-criteria.md) | Screening thresholds, ranking logic, alert conditions | movers/all |
| [technical-framework.md](references/technical-framework.md) | Technical indicators, chart patterns, MTF analysis, Ichimoku, Volume Profile | technicals/all |
| [regime-detection.md](references/regime-detection.md) | 4-quadrant regime model, volatility/trend classification | regime/all |

---

## Decision Tree

```
Scan Scope (from $ARGUMENTS)
├── indices    → Phase 1 only
├── sectors    → Phase 1 + 2
├── flows      → Phase 1 + 3
├── movers     → Phase 1 + 4
├── technicals → Phase 1 + 5
├── regime     → Phase 1 + 6
├── all        → All phases [DEFAULT]
└── (blank)    → All phases
```

---

## Phase 1: Global Index Performance (Always)

Use Yahoo Finance MCP to fetch all indices from [indices.md](references/indices.md):

**US Indices**: ^GSPC (S&P 500), ^DJI (Dow), ^IXIC (Nasdaq), ^NDX (Nasdaq 100), ^RUT (Russell 2000)
**Europe**: ^STOXX (STOXX 600), ^FTSE, ^GDAXI (DAX), ^FCHI (CAC 40)
**Asia**: ^N225 (Nikkei), ^HSI (Hang Seng), 000001.SS (Shanghai), ^KS11 (KOSPI), ^TWII (TAIEX)
**Volatility**: ^VIX
**Commodities**: GC=F (Gold), CL=F (WTI Oil), BZ=F (Brent), HG=F (Copper), SI=F (Silver), NG=F (Nat Gas)
**Currencies**: DX-Y.NYB (DXY), EURUSD=X, USDJPY=X, TWD=X, USDCNY=X

For each: current level, daily change %, weekly %, monthly %, YTD %

**Cross-market regime check** (from [indices.md](references/indices.md)):
- Risk-On: Equities ↑, VIX ↓, DXY ↓, Gold ↓, HY Spreads ↓
- Risk-Off: Equities ↓, VIX ↑, DXY ↑, Gold ↑, HY Spreads ↑
- Copper/Gold ratio: Rising = growth optimism, Falling = defensive

---

## Phase 2: Sector Analysis

### US Sectors (S&P 500)
Use Yahoo Finance MCP for sector ETFs listed in [us-sectors.md](references/us-sectors.md):

| Sector | ETF | Cycle Phase Preference |
|--------|-----|----------------------|
| Technology | XLK | Early/Mid cycle |
| Healthcare | XLV | Late cycle/Recession |
| Financials | XLF | Early cycle |
| Consumer Discretionary | XLY | Early/Mid cycle |
| Communication Services | XLC | Mid cycle |
| Industrials | XLI | Early/Mid cycle |
| Consumer Staples | XLP | Late/Recession |
| Energy | XLE | Mid/Late cycle |
| Utilities | XLU | Recession |
| Real Estate | XLRE | Early cycle (rate sensitive) |
| Materials | XLB | Mid cycle |

**Sector rotation signal**: Compare current cycle phase (from /macro-analysis or estimate) with sector performance to identify rotation.

### Taiwan Sectors (TWSE)
Use TWSE MCP for sector-level data from [tw-sectors.md](references/tw-sectors.md):
- Each sector: performance %, volume change %, foreign investor net position
- Key sectors: 半導體, 電子零組件, 金融, 航運, 鋼鐵, 塑化, 生技
- Identify: Which sectors are leading? Which are lagging? Money rotating from where to where?

---

## Phase 3: Fund Flow Analysis

### Taiwan Institutional Flows (TWSE MCP)
| 法人 | 數據 | 意義 |
|------|------|------|
| 外資 | 今日買賣超, 連續天數, 本週/月累計 | 最重要的方向性指標 |
| 投信 | 今日買賣超, 連續天數, 本週/月累計 | 國內基金動向 |
| 自營商 | 今日買賣超, 連續天數, 本週/月累計 | 短線避險/投機 |

**Divergence signals**:
- 外資買 + 投信買 = 強烈共識多方
- 外資買 + 投信賣 = 外資看好但國內基金謹慎
- 外資賣 + 投信買 = 法人分歧，注意

### Margin Trading (TWSE MCP)
- 融資餘額及變化: 融資大增+指數上漲 = 散戶追高(警戒)
- 融券餘額及變化: 融券大增 = 市場看空氣氛
- 融資/融券比: 極端值 = 反轉信號

---

## Phase 4: Notable Movers

Use TWSE MCP + Yahoo Finance MCP, filter by criteria in [scan-criteria.md](references/scan-criteria.md):

### Alert Conditions
| Condition | Threshold | Signal |
|-----------|-----------|--------|
| Daily price change | >5% or <-5% | Significant move |
| Volume vs 20-day avg | >3x | Unusual activity |
| 52-week high | New high | Breakout candidate |
| 52-week low | New low | Breakdown / value trap |
| Gap up/down | >2% gap from previous close | Event-driven |

### Output Tables
- **Top Gainers**: Top 10 by daily % change
- **Top Losers**: Top 10 by daily % decline
- **Volume Spikes**: Top 10 by volume/20d-avg ratio
- **52-Week Highs/Lows**: Stocks hitting extremes

---

## Phase 5: Technical Regime Assessment

Reference [technical-framework.md](references/technical-framework.md) for full methodology.

### Market-Level Technical Signals

**Trend indicators** (apply to major indices):
- Moving averages: 50d vs 200d (Golden Cross / Death Cross)
- MACD: Signal line crossover, histogram momentum
- ADX: >25 = trending, <20 = ranging

**Momentum indicators**:
- RSI (14): <30 oversold, >70 overbought
- Stochastic: Crossover signals

**Breadth indicators** (US market):
- Advance/Decline ratio
- % of S&P 500 stocks above 200-day MA: >70% = broad strength, <30% = broad weakness
- New Highs vs New Lows: NH-NL > 100 = bullish, < -100 = bearish

**Volatility**:
- VIX level and term structure (contango = complacent, backwardation = fear)
- Bollinger Band width: Squeeze → expect breakout

### Multi-Timeframe Alignment (MTF)

| Timeframe | Trend | Signal | Support | Resistance | Alignment |
|-----------|-------|--------|---------|-----------|-----------|
| Monthly | {Up/Down/Sideways} | {indicator} | {level} | {level} | |
| Weekly | {Up/Down/Sideways} | {indicator} | {level} | {level} | |
| Daily | {Up/Down/Sideways} | {indicator} | {level} | {level} | |
| **Overall** | | **Score: X/3** | | | |

- 3/3 aligned = Strong signal, act with confidence
- 2/3 aligned = Moderate, lean in direction of majority
- 1/3 or 0/3 = Conflicting, avoid new positions

---

## Phase 6: Regime Classification

Reference [regime-detection.md](references/regime-detection.md) for the 4-quadrant model.

### Four-Quadrant Regime Model

|  | Low Volatility | High Volatility |
|---|---|---|
| **Trending** | Q1: Clean trend — trend-following works | Q2: Volatile trend — momentum with caution |
| **Ranging** | Q3: Quiet range — mean-reversion works | Q4: Choppy chaos — reduce or sit out |

**Classification inputs**:
- ATR percentile (current vs 100-day history)
- ADX level (trend strength)
- Hurst exponent (mean-reversion vs persistence)

**Strategy implication by regime**:
| Regime | Recommended Action |
|--------|-------------------|
| Q1: Low vol + trending | Full exposure, tight stops, trend-following |
| Q2: High vol + trending | Half size, wide stops, momentum plays |
| Q3: Low vol + ranging | Mean-reversion, range-bound strategies |
| Q4: High vol + ranging | Reduce to 25% or cash, wait for clarity |

---

## Store in SQLite

Use SQLite MCP → `market_scans` table:
```
timestamp, scope, indices_data (JSON), sectors_data (JSON),
flows_data (JSON), movers_data (JSON), commodities_data (JSON),
currencies_data (JSON), summary (TEXT)
```

---

## Generate Charts

Use Chart MCP (AntV):
- Global index heatmap (daily/weekly/monthly changes)
- Sector performance bar chart (sorted by performance)
- Fund flow trend chart (3-institution stacked bar)
- VIX term structure line chart

---

## Output Format

```
## 🌐 市場掃描 — {date} {time}

### 📊 全球指數
| Index | Level | Daily | Weekly | Monthly | YTD | Signal |
|-------|-------|-------|--------|---------|-----|--------|
| S&P 500 | ... | ... | ... | ... | ... | ... |
| TAIEX | ... | ... | ... | ... | ... | ... |
| ... |

**VIX**: {level} ({change}) — {interpretation}
**Regime**: {Q1/Q2/Q3/Q4} — {description}
**Cross-Market**: {Risk-On / Risk-Off / Mixed} — {evidence}

### 🏭 類股表現

#### US Sectors (S&P 500)
| Sector | ETF | Daily | Weekly | Monthly | vs S&P 500 | Cycle Fit |
|--------|-----|-------|--------|---------|-----------|-----------|
| ... |

#### 台股類股
| 類股 | 漲跌% | 成交量變化 | 外資動態 | 趨勢 |
|------|--------|-----------|---------|------|
| ... |

**類股輪動觀察**: {sector rotation insights}

### 💰 法人資金流向
| 法人 | 今日買賣超(億) | 連續天數 | 本週累計 | 本月累計 |
|------|---------------|---------|---------|---------|
| 外資 | ... | ... | ... | ... |
| 投信 | ... | ... | ... | ... |
| 自營商 | ... | ... | ... | ... |

**融資餘額**: {level} ({change}) — {interpretation}
**法人共識**: {convergence or divergence signal}

### 🔥 異常標的
| 股票 | 代碼 | 漲跌% | 成交量倍數 | 事件 |
|------|------|--------|-----------|------|
| ... |

### 📐 技術面總覽
| Index | Trend | MA Signal | RSI | MACD | Breadth | MTF Score |
|-------|-------|-----------|-----|------|---------|-----------|
| S&P 500 | ... | ... | ... | ... | ... | .../3 |
| TAIEX | ... | ... | ... | ... | ... | .../3 |

### 🎯 Regime
**當前象限**: {Q1/Q2/Q3/Q4}
**建議策略**: {regime-appropriate strategy}

### 🛢️ 商品 & 💱 匯率
| Item | Price | Daily | Weekly | Signal |
|------|-------|-------|--------|--------|
| Gold | ... | ... | ... | ... |
| WTI Oil | ... | ... | ... | ... |
| DXY | ... | ... | ... | ... |
| USD/TWD | ... | ... | ... | ... |

### 📝 市場摘要
{3-5 sentences in Traditional Chinese highlighting the most notable developments}

╔══════════════════════════════════════════════╗
║              MARKET SIGNAL                   ║
╠══════════════════════════════════════════════╣
║ Signal:      BULLISH / NEUTRAL / BEARISH     ║
║ Confidence:  HIGH / MEDIUM / LOW             ║
║ Horizon:     SHORT-TERM                      ║
║ Score:       X.X / 10                        ║
╠══════════════════════════════════════════════╣
║ Conviction:  STRONG / MODERATE / WEAK        ║
╚══════════════════════════════════════════════╝
```

---

## Quality Checklist
- [ ] All indices fetched and displayed (no stale data)
- [ ] Sector data covers both US and Taiwan
- [ ] Fund flows include all 3 institutional types
- [ ] Movers filtered by meaningful thresholds (not noise)
- [ ] Technical signals computed on current data
- [ ] Regime classified with evidence
- [ ] Cross-market signals internally consistent
- [ ] Stored in SQLite
- [ ] Charts generated
