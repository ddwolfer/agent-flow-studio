# Economic Models & Frameworks Reference

## Monetary Policy Models

### Taylor Rule
**Purpose**: Estimate appropriate Fed Funds Rate based on economic conditions.

**Formula**:
```
r = r* + π + 0.5(π - π*) + 0.5(y - y*)
```
Where:
- r = recommended Fed Funds Rate
- r* = neutral real rate (~0.5-1.0% currently debated)
- π = current inflation rate (Core PCE YoY)
- π* = target inflation (2%)
- y = real GDP growth
- y* = potential GDP growth (~1.8-2.0%)

**Interpretation**:
- If Taylor Rule rate > actual Fed Funds → policy is too loose
- If Taylor Rule rate < actual Fed Funds → policy is too restrictive
- Gap size indicates magnitude of policy mispricing

**Limitations**: Doesn't account for financial conditions, forward-looking nature of policy, or zero lower bound.

### IS-LM Model
**Purpose**: Show interaction between real economy (IS) and money market (LM).

**IS Curve** (Goods market equilibrium):
- Downward sloping: lower rates → more investment → higher output
- Shifts right with: fiscal stimulus, increased confidence, export boom
- Shifts left with: austerity, trade war, confidence shock

**LM Curve** (Money market equilibrium):
- Upward sloping: higher output → more money demand → higher rates
- Shifts right with: money supply increase, QE
- Shifts left with: money supply decrease, QT

**Application**:
- Fiscal expansion shifts IS right → higher output AND higher rates
- Monetary expansion shifts LM right → higher output AND lower rates
- Both together → higher output, rate direction uncertain

### Phillips Curve
**Purpose**: Relationship between unemployment and inflation.

**Modern expectations-augmented form**:
```
π = π_e + β(u* - u) + supply_shocks
```
Where:
- π = inflation
- π_e = inflation expectations
- u* = NAIRU (natural rate of unemployment, ~4.0-4.5%)
- u = actual unemployment
- β = slope (how much inflation responds to unemployment gap)

**Key insight**:
- When u < u* → inflation pressure rises
- When u > u* → inflation pressure falls
- BUT the relationship has flattened since the 1990s
- Inflation expectations anchor is crucial

### Yield Curve Models

**Term Premium Decomposition**:
```
Long-term yield = Expected future short rates + Term premium
```

**Inverted Yield Curve as Recession Predictor**:
- 10Y-2Y spread < 0: Historically preceded 7 of last 7 US recessions
- Lead time: 6-24 months before recession onset
- False positive rate: Low but not zero
- Current debate: Does QE distort the signal?

**Yield Curve Shapes**:
| Shape | Description | Economic Signal |
|-------|-------------|-----------------|
| Normal (steep) | Short < Long | Healthy growth expectations |
| Flat | Short ≈ Long | Slowing growth, late cycle |
| Inverted | Short > Long | Recession warning |
| Humped | Mid > Short & Long | Policy transition, uncertainty |
| Bear steepening | Long rates rising fast | Inflation fears, loose fiscal |
| Bull steepening | Short rates falling fast | Expected easing, recession near |

## Valuation Models

### Equity Risk Premium (ERP)
```
ERP = E/P ratio (earnings yield) - 10Y Treasury yield
```
- ERP > 3% → Stocks relatively attractive vs bonds
- ERP < 1% → Stocks expensive relative to bonds
- ERP < 0% → Stocks very expensive (only justified if growth is very high)

### Fed Model (simplified)
- Compare S&P 500 forward earnings yield vs 10Y Treasury yield
- When earnings yield > bond yield → stocks cheap
- Limitation: Doesn't account for growth differential or risk premium

### Buffett Indicator
```
Total Market Cap / GDP
```
- <75% → Undervalued
- 75-90% → Fair value
- 90-115% → Moderately overvalued
- >115% → Significantly overvalued
- Current structural level higher due to tech/services economy

## Business Cycle Models

### NBER Business Cycle
Four phases: Expansion → Peak → Contraction → Trough

**Key indicators by phase**:
| Phase | GDP | Employment | Inflation | Policy | Markets |
|-------|-----|-----------|-----------|--------|---------|
| Early Expansion | Accelerating | Recovering | Low/falling | Easing | Strongest returns |
| Mid Expansion | Steady | Full employment | Moderate | Neutral | Good returns |
| Late Expansion | Slowing | Tight market | Rising | Tightening | Lower returns, higher vol |
| Contraction | Negative | Rising jobless | Falling | Emergency ease | Negative returns, then bottoming |

### Credit Cycle
1. **Recovery**: Defaults peak, spreads start narrowing, credit tightening eases
2. **Expansion**: Low defaults, tight spreads, easy credit, leverage builds
3. **Downturn**: Spreads widen, defaults rise, credit tightens, deleveraging begins
4. **Repair**: Balance sheets cleaned up, conservative lending, setting up next cycle

### Profit Margin Cycle
- Margins expand in early/mid cycle (volume leverage, low rates)
- Margins peak in late cycle (wage pressure, rate pressure)
- Margins compress in contraction (volume deleveraging)
- Peak margins are a WARNING signal, not a comfort signal

## Taiwan-Specific Models

### Export Cycle Model
Taiwan's economy is highly export-dependent (~60-70% of GDP):
```
Taiwan GDP ≈ f(Global semiconductor demand, China economic health, USD/TWD, US consumer spending)
```

**Leading indicators for Taiwan exports**:
1. Global PMI new orders component (leads by 1-2 months)
2. US ISM Manufacturing (correlation with Taiwan export orders)
3. China PMI (major trade partner)
4. DRAM/Flash pricing (semiconductor cycle proxy)
5. Apple product cycle (significant supply chain weight)

### CBC Policy Reaction Function
```
CBC rate decision ≈ f(Fed rate, TWD depreciation pressure, CPI, GDP growth, housing market)
```
- CBC typically follows Fed with a lag
- Priority: exchange rate stability > inflation > growth
- Housing market overheating triggers selective credit controls before rate hikes
- Interventions: CBC actively manages TWD via forex market operations

## Scenario Analysis Framework

### Probability-Weighted Scenarios
For any macro topic, define exactly three scenarios:

| Scenario | Typical Probability | Characteristics |
|----------|-------------------|-----------------|
| **Base Case** | 50-60% | Most likely outcome given current data and trends |
| **Bull Case** | 15-25% | Upside scenario — what goes right |
| **Bear Case** | 15-25% | Downside scenario — what goes wrong |

**Rules**:
- Probabilities must sum to 100% (or note remaining tail risk)
- Each scenario must be specific and falsifiable
- Each must have identifiable trigger conditions
- Each must have measurable outcomes (specific levels, not just "goes up")

### Monitoring Framework
For each scenario, define:
1. **Key variable**: The one indicator that most distinguishes between scenarios
2. **Threshold**: Specific level that shifts probability toward that scenario
3. **Frequency**: How often to check (daily, weekly, monthly)
4. **Data source**: Which MCP to use for monitoring
