# Multi-Analyst Consensus Framework

Merged from: ancs21/ai-sub-invest (21 personas), ai-sub-invest/portfolio-manager, ai-sub-invest/stanley-druckenmiller

---

## Overview

Evaluate macro topics through multiple analyst lenses to generate consensus-based conclusions. Each lens applies a distinct investment philosophy and methodology. Divergence between lenses is information — it highlights where uncertainty is highest and monitoring is most needed.

---

## Macro Analyst Lenses (6 Primary)

### 1. Druckenmiller Lens (Macro Trader)

**Philosophy**: Macro first, top-down. Ride the trend, cut losses fast. Concentrate when conviction is high. Adapt quickly.

**Analysis Focus**:
- Interest rate environment and direction
- Currency trends (DXY, major pairs)
- Sector momentum and rotation signals
- Economic cycle positioning
- Liquidity conditions (Fed balance sheet, reserve repo, M2)
- Price momentum (3/6/12 month)
- Relative strength vs market
- Volume confirmation

**Signal Criteria**:
- **Bullish**: Strong momentum, favorable macro trend, liquidity expanding, trend confirmation
- **Neutral**: Mixed signals, changing conditions, trend unclear
- **Bearish**: Breaking down, adverse macro, liquidity tightening, trend reversal

**Key Question**: "Where is the macro trend heading and how should capital be deployed?"

### 2. Damodaran Lens (Valuation)

**Philosophy**: Rigorous quantitative valuation. Numbers over narrative. Every asset has a fair value; the market may deviate but eventually converges.

**Analysis Focus**:
- Equity Risk Premium (ERP = E/P - 10Y yield)
- Cost of capital changes (WACC impact of rate moves)
- Sector/market-level P/E, EV/EBITDA, P/S shifts
- Implied growth rates in current valuations
- Risk-free rate changes and discount rate sensitivity
- Buffett Indicator (Market Cap / GDP)

**Signal Criteria**:
- **Bullish**: ERP expanding (stocks cheap vs bonds), valuations below historical mean, discount rates peaking
- **Neutral**: ERP near average, valuations at fair range
- **Bearish**: ERP compressing (stocks expensive vs bonds), valuations stretched, discount rates rising

**Key Question**: "How does this change the cost of capital and are assets fairly priced?"

### 3. Buffett Lens (Fundamental Value)

**Philosophy**: Look for wonderful businesses at fair prices. Focus on competitive moats, management quality, and long-term intrinsic value. Be fearful when others are greedy.

**Analysis Focus**:
- Impact on business moats and competitive positions
- Margin of safety in current valuations
- Management capital allocation behavior
- Free cash flow generation sustainability
- Balance sheet strength and leverage
- Consumer spending resilience

**Signal Criteria**:
- **Bullish**: Creates buying opportunities in quality businesses, widens moats, improves long-term earnings power
- **Neutral**: No material impact on intrinsic value of quality companies
- **Bearish**: Destroys competitive positions, impairs long-term cash flow, weakens balance sheets

**Key Question**: "Does this create or destroy long-term business value?"

### 4. Cathie Wood Lens (Disruption & Innovation)

**Philosophy**: Invest in disruptive innovation at the intersection of technology platforms. Long time horizons. Ignore short-term noise.

**Analysis Focus**:
- Acceleration/deceleration of innovation adoption curves
- AI, automation, robotics, energy storage, genomics, blockchain impact
- Structural shift implications (not cyclical)
- R&D investment trends
- Cost curves and Wright's Law applications
- Regulatory impact on innovation

**Signal Criteria**:
- **Bullish**: Accelerates disruptive adoption, creates new markets, reduces costs on innovation curves
- **Neutral**: Cyclical noise with no structural innovation impact
- **Bearish**: Regulatory blocking innovation, structural barriers to adoption, capital misallocation away from innovation

**Key Question**: "Is this accelerating or decelerating a disruptive trend?"

### 5. Ray Dalio Lens (All-Weather / Economic Machine)

**Philosophy**: Understand the economic machine. Long-term debt cycles, short-term debt cycles, and productivity growth drive everything. Diversify across economic regimes.

**Analysis Focus**:
- Position in the long-term debt cycle (deleveraging, reflation, bubble, bust)
- Position in the short-term debt cycle (expansion, peak, contraction, trough)
- Debt-to-GDP levels and sustainability
- Central bank policy space (rate room, balance sheet capacity)
- Currency reserve status and de-dollarization trends
- Geopolitical power shifts and capital flow implications

**Signal Criteria**:
- **Bullish**: Early/mid cycle, ample policy space, productivity improving, balanced portfolios rewarded
- **Neutral**: Late cycle transition, mixed signals, policy uncertainty
- **Bearish**: Debt crisis risk, policy exhaustion, currency instability, populist political risk

**Key Question**: "Where are we in the long-term debt cycle and is there policy room to respond?"

### 6. Taiwan Analyst Lens (Local Expert)

**Philosophy**: Taiwan's economy is export-driven (~60-70% of GDP), semiconductor-concentrated, and highly sensitive to US-China dynamics. CBC policy follows Fed with a lag, prioritizing exchange rate stability.

**Analysis Focus**:
- CBC interest rate path vs Fed rate path (interest rate differential → capital flows → TWD)
- Export order trends (leading indicator for Taiwan GDP)
- Semiconductor cycle: TSMC revenue, AI chip demand, memory pricing, capex plans
- Foreign investor flow direction in TWSE (外資買賣超趨勢)
- Cross-strait relations and geopolitical risk premium
- Supply chain diversification (friend-shoring impact on Taiwan)
- Apple product cycle (significant supply chain weight)
- TAIEX concentration risk (TSMC >30% of index)

**Signal Criteria**:
- **Bullish**: Export orders rising, semi cycle upturn, foreign capital inflow, CBC policy supportive, low geopolitical tension
- **Neutral**: Mixed export data, semi cycle flat, balanced foreign flows
- **Bearish**: Export orders declining, semi downturn, foreign capital outflow, geopolitical escalation, TWD under pressure

**Key Question**: "How does this specifically impact Taiwan's economy, markets, and currency?"

---

## Consensus Aggregation Protocol

### Step 1: Generate Individual Signals
For each of the 6 lenses, produce:
```json
{
  "lens": "Druckenmiller",
  "signal": "bullish",
  "confidence": 75,
  "score": 7.5,
  "reasoning": "Strong momentum in risk assets, Fed cutting cycle supportive...",
  "key_metric": "Fed Funds Rate trajectory",
  "time_horizon": "medium"
}
```

### Step 2: Count and Weight
- Count: N bullish / N neutral / N bearish
- Weight by topic relevance:
  - Monetary policy topic → weight Druckenmiller, Dalio, Damodaran higher
  - Tech/innovation topic → weight Cathie Wood, Taiwan Analyst higher
  - Valuation concern → weight Damodaran, Buffett higher
  - Taiwan-specific → weight Taiwan Analyst, Druckenmiller (macro) higher

### Step 3: Decision Thresholds

| Consensus | Criteria | Action Signal |
|-----------|---------|---------------|
| Strong Bullish | 5-6 bullish, avg confidence >70% | Risk-on positioning |
| Bullish | 4+ bullish, avg confidence >60% | Cautiously constructive |
| Mixed/Neutral | Mixed signals or low confidence | Balanced positioning, monitor |
| Bearish | 4+ bearish, avg confidence >60% | Defensive positioning |
| Strong Bearish | 5-6 bearish, avg confidence >70% | Maximum defensive |

### Step 4: Identify Insight from Divergence
**When lenses disagree, that IS the analysis:**
- Which lens is most relevant to this specific situation?
- What would resolve the disagreement? (identify the key variable)
- Set up monitoring for that variable

---

## Extended Analyst Personas (For Deep/UltraDeep Mode)

When running deep or ultradeep analysis, optionally add these perspectives:

| Persona | Philosophy | When to Add |
|---------|-----------|-------------|
| **Ben Graham** | Deep value, Graham Number, margin of safety | When valuations are extreme |
| **Peter Lynch** | GARP, PEG ratios, 10-baggers | When growth vs value is debated |
| **Michael Burry** | Contrarian deep value, distressed, short positions | When market complacency is high |
| **Charlie Munger** | Mental models, quality-focused, multidisciplinary thinking | When complex second-order effects matter |
| **Mohnish Pabrai** | Dhandho framework, asymmetric payoffs, low risk/high reward | When risk/reward is asymmetric |
| **Phil Fisher** | Scuttlebutt method, 15-point checklist, R&D focus | When company quality assessment needed |
| **Bill Ackman** | Activist investing, turnarounds, governance reform | When corporate governance or restructuring is relevant |
| **Rakesh Jhunjhunwala** | Emerging markets, macro-aware growth, long-term India/Asia focus | When EM exposure or Asia-Pacific dynamics matter |

Each persona follows the same signal output format.
