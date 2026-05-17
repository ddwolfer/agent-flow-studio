# Cross-Verification Methods

Merged from: InvestSkill/fundamental-analysis (data verification), financial-services-plugins/comps-analysis (data source hierarchy), deep-research-skill/methodology (triangulation)

---

## Data Source Priority Hierarchy

**ALWAYS follow this hierarchy** (from comps-analysis):
1. **Tier 1**: Official statistics (BLS, Fed/FRED, DGBAS, CBC, SEC filings) — highest reliability
2. **Tier 2**: Established data providers (Yahoo Finance, TWSE official, Bloomberg, Reuters)
3. **Tier 3**: Analyst reports, academic research, established media (IMF, World Bank, WSJ, FT)
4. **Tier 4**: YouTube analysts, blogs, opinion (游庭皓, 張貽程, Seeking Alpha)
5. **Never**: Anonymous, unverifiable, social media as sole source

---

## Method A: Historical Back-Test

**Purpose**: Check if a claimed pattern actually holds historically.

### Process
1. Define the pattern precisely (e.g., "外資連續賣超 5 日後台股必跌")
2. Query SQLite `macro_snapshots` or use FRED/Yahoo Finance for historical data
3. Find ALL past instances of the pattern
4. Record what actually happened each time
5. Calculate base rate: successes / total instances

### Base Rate Interpretation
| Base Rate | Conclusion |
|-----------|-----------|
| >80% | Pattern is historically reliable (but sample size matters) |
| 60-80% | Pattern has some predictive value but exceptions exist |
| 40-60% | Pattern is essentially random — no predictive value |
| <40% | Pattern is actually INVERSE of claimed direction |

### Sample Size Warning
| Instances | Reliability |
|-----------|-----------|
| 1-3 | Anecdotal — cannot draw conclusions |
| 4-10 | Suggestive but not statistically significant |
| 11-30 | Moderate confidence |
| 30+ | High confidence (if conditions are comparable) |

---

## Method B: Cross-Source Verification

**Purpose**: Check if multiple independent sources agree.

### Process
1. Identify the specific claim to verify
2. Check against FRED MCP data
3. Check against Yahoo Finance MCP data
4. Check against TWSE MCP data (if Taiwan-relevant)
5. Check against World Bank MCP data (if international)
6. Check SQLite for past analyses on same topic

### Agreement Matrix
| Sources Agree | Sources Disagree | Verdict |
|--------------|-----------------|---------|
| All 3+ agree | None | Strongly supported |
| 2 agree | 1 disagrees | Partially supported — investigate disagreement |
| 1 supports | 2 disagree | Likely not supported |
| All disagree | N/A | Contradicted |

---

## Method C: Conditional Analysis

**Purpose**: Check if a claim is only true under specific conditions.

### Process
1. State the claim as: "If [condition], then [outcome]"
2. List all conditions that might affect the outcome
3. For each condition, check: Is it currently met?
4. Are there conditions the claimant didn't mention?

### Common Missing Conditions in Financial Claims
- Interest rate environment (rising vs falling)
- Liquidity conditions (ample vs tight)
- Market cycle phase (early vs late)
- Geopolitical context
- Valuation starting point
- Time horizon assumed

---

## Method D: Counter-Example Search

**Purpose**: Actively seek disconfirming evidence (hardest but most valuable).

### Process
1. Assume the claim is FALSE
2. Search for instances where the pattern DIDN'T hold
3. Search for experts who DISAGREE
4. Look for structural changes that might invalidate historical patterns

### Why This Matters
- Humans naturally seek confirming evidence (confirmation bias)
- Counter-examples are more informative than confirmations
- One strong counter-example can invalidate a rule; many confirmations cannot prove it

---

## Method E: Comparative Analysis (from comps-analysis)

**Purpose**: Verify claims by comparing with similar situations/entities.

### Process
1. Identify comparable situations (same type of event, similar conditions)
2. Check if claimed outcomes occurred in comparables
3. Identify what was different in cases where outcome diverged
4. Assess whether current situation is more similar to successes or failures

### Financial Application
- Compare current rate hiking cycle with past cycles
- Compare current TAIEX valuation with historical valuation at similar economic conditions
- Compare current export order trends with past turning points
- Compare current sector rotation with historical cycle transitions

---

## Verdict Classification

| Verdict | Criteria |
|---------|---------|
| **Supported** | 3+ Tier 1-2 sources agree, historical base rate >70%, no strong counter-evidence |
| **Partially Supported** | Some evidence supports, but significant caveats or conditions apply |
| **Not Supported** | Evidence does not support the claim, or base rate <50% |
| **Misleading** | Claim contains a kernel of truth but is presented in a way that leads to wrong conclusions |
| **Insufficient Data** | Cannot verify with available tools — note what additional data would help |
