---
name: macro-analysis
description: "Multi-perspective macroeconomic analysis with structured research pipeline, data verification, and consensus scoring. Use when: user asks for macro analysis, economic impact assessment, policy analysis, multi-angle view on economic topics, '總經分析', '多角度分析', '影響分析', rate decision analysis, inflation analysis, tariff/trade war impact, recession risk assessment, sector rotation implications, or any topic requiring systematic economic reasoning from multiple viewpoints. Not for simple data lookups (use /data-snapshot) or single-stock analysis (use /market-scan)."
argument-hint: [topic or question in any language]
effort: high
user-invocable: true
---

# Multi-Perspective Macro Analysis

Conduct comprehensive, multi-perspective macroeconomic analysis through a structured research pipeline with data verification, source credibility scoring, and consensus-based conclusions.

**Autonomy Principle:** Operate independently. Infer assumptions from context. Only stop for critical errors or incomprehensible queries.

## Reference Files

**Read all reference files at task start before beginning any work.** These contain critical frameworks and data definitions.

| File | Purpose |
|------|---------|
| [perspectives.md](references/perspectives.md) | Four analytical perspectives: Central Bank, Market, Industry, Historical |
| [economic-models.md](references/economic-models.md) | Taylor Rule, IS-LM, Phillips Curve, yield curve models, valuation models, business cycle |
| [historical-episodes.md](references/historical-episodes.md) | Historical analog database for comparison |
| [analysis-template.md](references/analysis-template.md) | Output template and formatting standards |
| [indicators-and-thresholds.md](references/indicators-and-thresholds.md) | Complete indicator list with FRED series IDs, thresholds, and interpretation |
| [analyst-perspectives.md](references/analyst-perspectives.md) | Multi-analyst consensus framework (12 macro personas) |
| [recession-scoring.md](references/recession-scoring.md) | Recession probability model and credit market indicators |

---

## Decision Tree

```
Request Analysis
├── Simple data lookup? → STOP: Use /data-snapshot
├── Single stock analysis? → STOP: Use /market-scan
├── Verify a claim? → STOP: Use /cross-check
├── Complex macro analysis needed? → CONTINUE
│
Mode Selection (based on complexity)
├── Quick briefing (1 topic, known data) → lite (4 phases, ~5 min)
├── Standard analysis (policy/event impact) → standard (6 phases, ~15 min) [DEFAULT]
├── Deep analysis (multi-country, structural) → deep (8 phases, ~30 min)
└── Comprehensive review (full cycle assessment) → ultradeep (8+ phases, ~45 min)
```

---

## Workflow Overview

| Phase | Name | Lite | Standard | Deep | UltraDeep |
|-------|------|------|----------|------|-----------|
| 1 | SCOPE | Y | Y | Y | Y |
| 2 | DATA COLLECTION | Y | Y | Y | Y |
| 3 | FOUR-PERSPECTIVE ANALYSIS | Y | Y | Y | Y |
| 4 | MULTI-ANALYST CONSENSUS | - | Y | Y | Y |
| 5 | CROSS-VERIFICATION | - | Y | Y | Y |
| 6 | SCENARIO MODELING | - | - | Y | Y |
| 7 | CRITIQUE & REFINE | - | - | Y | Y |
| 8 | PACKAGE | Y | Y | Y | Y |

---

## Phase 1: SCOPE — Research Framing

1. **Decompose the topic** into core components using Sequential Thinking MCP:
   - What is the primary economic question?
   - What are the 3-7 sub-questions that must be answered?
   - What is the geographic scope? (US only / Taiwan only / Global / Multi-region)
   - What is the time horizon? (Short-term 1-3mo / Medium 3-12mo / Long 1-3yr)

2. **Identify relevant indicator categories** by mapping sub-questions to MCP data sources:
   - US macro → FRED MCP (see [indicators-and-thresholds.md](references/indicators-and-thresholds.md))
   - Taiwan macro → TWSE MCP + web-research for CBC/DGBAS
   - Global markets → Yahoo Finance MCP
   - Development data → World Bank MCP
   - Historical context → SQLite MCP (past analyses)
   - Analyst views → SQLite MCP (past YT briefings)

3. **Define success criteria**: What would a complete answer look like?

---

## Phase 2: DATA COLLECTION — Parallel Information Gathering

**CRITICAL: Execute ALL data pulls in parallel using multiple tool calls in a single message**

### Quantitative Data (from MCP servers)

Pull data relevant to the topic. Reference [indicators-and-thresholds.md](references/indicators-and-thresholds.md) for FRED series IDs and interpretation thresholds.

**US Data (FRED MCP):**
- Growth: GDP (A191RL1Q225SBEA), Industrial Production (INDPRO), Capacity Utilization (TCU)
- Labor: Unemployment (UNRATE), Nonfarm Payrolls (PAYEMS), Jobless Claims (ICSA), JOLTS (JTSJOL)
- Inflation: CPI (CPIAUCSL), Core PCE (PCEPILFE), PPI (PPIFIS), Breakeven (T5YIE, T10YIE)
- Rates: Fed Funds (DFF), 2Y (DGS2), 10Y (DGS10), 10Y-2Y Spread (T10Y2Y), 10Y-3M (T10Y3M)
- Sentiment: Consumer Confidence (UMCSENT), Retail Sales (RSAFS)
- Financial Conditions: NFCI, HY Spread (BAMLH0A0HYM2), IG Spread (BAMLC0A0CM)
- Housing: Starts (HOUST), Mortgage Rate (MORTGAGE30US), Case-Shiller (CSUSHPINSA)

**Taiwan Data (TWSE MCP + Yahoo Finance):**
- TAIEX level, volume, foreign investor flows, sector performance
- ^TWII, TWD=X via Yahoo Finance
- CBC rates, CPI, GDP, export orders via web-research if needed

**Global Data (Yahoo Finance MCP):**
- Major indices: ^GSPC, ^DJI, ^IXIC, ^N225, ^HSI, 000001.SS, ^FTSE, ^GDAXI
- Commodities: GC=F (Gold), CL=F (Oil), HG=F (Copper)
- Currencies: DX-Y.NYB (DXY), EURUSD=X, USDJPY=X, TWD=X
- Volatility: ^VIX

**Historical Context (SQLite MCP):**
- Query past macro_analyses for same or related topics
- Query past yt_summaries for relevant analyst views
- Query past macro_snapshots for trend data

### Qualitative Context
- Check SQLite for recent YT briefings from 游庭皓 and 張貽程 on related topics
- If needed, use Playwright MCP to scrape CBC/DGBAS/Fed statements

---

## Phase 3: FOUR-PERSPECTIVE ANALYSIS

Apply all four analytical perspectives. See [perspectives.md](references/perspectives.md) for the complete framework.

### Perspective 1: 央行/政策視角 (Central Bank / Policy)
- How does this affect central bank mandates (price stability + employment)?
- What is the likely policy response (rate path, balance sheet, forward guidance)?
- Apply Taylor Rule if relevant (see [economic-models.md](references/economic-models.md))
- Consider both Fed AND Taiwan CBC implications
- Assess fiscal policy interaction

### Perspective 2: 市場/交易視角 (Market / Trading)
- How much is already priced in? (implied probabilities, futures pricing)
- Current positioning: VIX level/term structure, put/call ratio, fund flows
- Key technical levels and market breadth
- Cross-asset signals: stock-bond correlation, DXY direction, copper/gold ratio
- What is the pain trade?

### Perspective 3: 產業/企業視角 (Industry / Corporate)
- First-order effects: Which sectors face direct revenue/cost impact?
- Second-order effects: Supply chain, substitution, investment cycle
- Taiwan-specific: Semiconductor (TSMC, MediaTek), Electronics (Foxconn), Financial, Traditional
- Earnings impact estimation and guidance risk
- Who are the winners and losers?

### Perspective 4: 歷史/週期視角 (Historical / Cyclical)
- Find most analogous historical episodes (see [historical-episodes.md](references/historical-episodes.md))
- Rate similarity score (1-10) for each analog
- Where are we in: business cycle, credit cycle, profit margin cycle?
- Current regime: Goldilocks / Reflation / Stagflation / Deflation
- "This Time Is Different" assessment: genuine structural differences vs narrative

---

## Phase 4: MULTI-ANALYST CONSENSUS

Apply the multi-perspective analyst framework from [analyst-perspectives.md](references/analyst-perspectives.md).

Evaluate the topic through **6 macro analyst lenses** (adapted from ConsensusAI):

| Analyst Lens | Focus | Key Question |
|-------------|-------|--------------|
| **Druckenmiller (Macro Trader)** | Trend, liquidity, sector rotation | Where is the macro trend heading and how to position? |
| **Damodaran (Valuation)** | Risk premiums, discount rates, fair value | How does this change the cost of capital and asset valuations? |
| **Buffett (Fundamental Value)** | Intrinsic value, moats, margin of safety | Does this create or destroy long-term business value? |
| **Cathie Wood (Disruption)** | Innovation curves, structural change | Is this accelerating or decelerating a disruptive trend? |
| **Ray Dalio (All-Weather)** | Economic machine, debt cycles, diversification | Where are we in the long-term debt cycle? |
| **Taiwan Analyst (Local Expert)** | CBC policy, TWSE dynamics, export cycle, geopolitics | How does this specifically impact Taiwan's economy and markets? |

For each lens, generate:
```json
{
  "lens": "Druckenmiller",
  "signal": "bullish | neutral | bearish",
  "confidence": 0-100,
  "reasoning": "...",
  "key_metric": "the single most important indicator for this view",
  "time_horizon": "short | medium | long"
}
```

### Consensus Aggregation
- Count bullish/neutral/bearish signals
- Calculate weighted confidence (weight by relevance to topic)
- Identify convergence points (where 4+ lenses agree)
- Identify divergence points (where lenses strongly disagree)
- **Divergence is information** — don't smooth it away

---

## Phase 5: CROSS-VERIFICATION

### Data Triangulation
For each major finding, verify against **3+ independent sources**:
- Does FRED data support the claim?
- Does Yahoo Finance market data confirm?
- Does TWSE data align (if Taiwan-relevant)?
- Do historical analogs support the pattern?
- Do the YT analysts (游庭皓/張貽程) share similar or opposing views?

### Credibility Assessment
| Tier | Source Type | Weight |
|------|-----------|--------|
| 1 (Highest) | Official statistics (BLS, Fed, DGBAS, CBC), regulatory filings | 1.0 |
| 2 (High) | FRED, Bloomberg, Reuters, established financial data providers | 0.9 |
| 3 (Medium) | Analyst reports, academic research, established financial media | 0.7 |
| 4 (Lower) | YouTube analysts, social media, opinion, blogs | 0.5 |

### Conflict Resolution
When data sources conflict:
1. Identify the specific variable causing disagreement
2. Check data vintage (is one source more recent?)
3. Check methodology differences
4. Default to Tier 1 sources when available
5. Note the conflict explicitly in the output

---

## Phase 6: SCENARIO MODELING (Deep/UltraDeep only)

### Three-Scenario Framework
Define exactly three scenarios. See [economic-models.md](references/economic-models.md) for the framework.

| Scenario | Probability | Description | Trigger Conditions | Key Indicators |
|----------|------------|-------------|-------------------|----------------|
| Base Case | 50-60% | Most likely given current data | {specific} | {measurable} |
| Bull Case | 15-25% | What goes right | {specific} | {measurable} |
| Bear Case | 15-25% | What goes wrong | {specific} | {measurable} |

**Rules:**
- Probabilities must sum to 100% (or note remaining tail risk)
- Each scenario MUST be specific and falsifiable
- Each MUST have identifiable trigger conditions
- Each MUST have measurable outcomes (specific levels, not "goes up")

### Monitoring Framework
For each scenario, define:
1. **Key variable**: The single indicator that most distinguishes scenarios
2. **Threshold**: Specific level that shifts probability
3. **Frequency**: How often to check (daily/weekly/monthly)
4. **MCP source**: Which tool to use for monitoring

---

## Phase 7: CRITIQUE & REFINE (Deep/UltraDeep only)

### Self-Critique Checklist
- [ ] Have I considered the strongest counter-argument to my base case?
- [ ] Am I anchoring on recent data or narrative?
- [ ] Is there survivorship bias in my historical analogs?
- [ ] Am I confusing correlation with causation anywhere?
- [ ] What information would change my conclusion? Can I get it?
- [ ] Have I weighted Tier 1 sources appropriately over Tier 4?
- [ ] Are my scenario probabilities calibrated (not just 60/20/20 by default)?

### Refinement
- Adjust conclusions based on critique
- Update scenario probabilities if warranted
- Add caveats for weak points
- Strengthen citations for strong points

---

## Phase 8: PACKAGE — Output Generation

### Generate Visualizations
Use Chart MCP (AntV) to create:
- Time series of key indicators related to the topic
- Comparison charts (current vs historical episodes)
- Scenario probability visualization
- Cross-market signal dashboard

### Store in SQLite
Use SQLite MCP to insert into `macro_analyses` table:
- timestamp, topic, all four perspectives, convergence/divergence points
- base/bull/bear cases with probabilities
- key monitoring indicators
- confidence level and conclusion

### Output Format
Follow [analysis-template.md](references/analysis-template.md) for the complete template:

```
## 🔬 多角度總經分析

### 📋 主題: {topic}
**分析日期**: {date}
**分析深度**: {lite/standard/deep/ultradeep}

---

### 📊 關鍵數據
{Table of most relevant indicators with current values, trends, and significance}

### 🏛️ 央行/政策視角
{Central bank perspective analysis}

### 📈 市場/交易視角
{Market perspective analysis}

### 🏭 產業/企業視角
{Industry perspective analysis}

### 📚 歷史/週期視角
{Historical perspective analysis}

### 🧠 多視角共識

#### 分析師信號矩陣
| Analyst Lens | Signal | Confidence | Key Metric | Horizon |
|-------------|--------|-----------|------------|---------|
| Druckenmiller | {signal} | {%} | {metric} | {horizon} |
| Damodaran | {signal} | {%} | {metric} | {horizon} |
| ... | ... | ... | ... | ... |

**共識**: {N}/6 Bullish, {N}/6 Neutral, {N}/6 Bearish
**加權信心**: {weighted %}

### 🔀 觀點交匯
**四方共識**: {Where all perspectives + analyst lenses agree}
**分歧之處**: {Where they diverge — this is where the real insight is}

### 🎯 情境分析
| 情境 | 機率 | 描述 | 觸發條件 | 關鍵指標 |
|------|------|------|---------|---------|
| Base | {%} | {desc} | {triggers} | {indicators} |
| Bull | {%} | {desc} | {triggers} | {indicators} |
| Bear | {%} | {desc} | {triggers} | {indicators} |

### ⚠️ 衰退/風險評估
{Recession probability scoring from recession-scoring.md if relevant}

### 🔍 後續追蹤
| 指標 | 目前值 | 閾值 | 觸發情境 | 檢查頻率 | MCP 來源 |
|------|--------|------|---------|---------|---------|
| {indicator} | {current} | {threshold} | {scenario} | {freq} | {mcp} |

### 📝 結論
{2-3 paragraphs in Traditional Chinese synthesizing all perspectives}

╔══════════════════════════════════════════════╗
║              INVESTMENT SIGNAL               ║
╠══════════════════════════════════════════════╣
║ Signal:      BULLISH / NEUTRAL / BEARISH     ║
║ Confidence:  HIGH / MEDIUM / LOW             ║
║ Horizon:     SHORT / MEDIUM / LONG-TERM      ║
║ Score:       X.X / 10                        ║
╠══════════════════════════════════════════════╣
║ Conviction:  STRONG / MODERATE / WEAK        ║
╚══════════════════════════════════════════════╝
```

Score Guide: 8.0–10.0 Strongly Bullish | 6.0–7.9 Moderately Bullish | 4.0–5.9 Neutral | 2.0–3.9 Moderately Bearish | 0.0–1.9 Strongly Bearish

---

## Quality Checklist (Before Delivery)

### Data Accuracy
- [ ] All indicator values verified against MCP source data
- [ ] No stale data (check publication dates)
- [ ] Calculations verified (spreads, changes, growth rates)

### Analysis Completeness
- [ ] All four perspectives addressed with substance
- [ ] Multi-analyst consensus generated with signals
- [ ] Historical analogs identified and scored
- [ ] Scenarios defined with specific triggers and probabilities
- [ ] Monitoring framework established

### Presentation
- [ ] 中英混合 format (Chinese analysis + English indicator names)
- [ ] Charts generated for key data
- [ ] Stored in SQLite for historical tracking
- [ ] Signal block included at end
