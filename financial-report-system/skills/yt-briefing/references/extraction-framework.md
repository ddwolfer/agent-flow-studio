# YouTube Transcript Extraction & Analysis Framework

## Overview
This framework defines how to systematically extract actionable insights from financial YouTube video transcripts.

## Step 1: Transcript Pre-Processing

### Clean-Up Rules
1. Remove filler words and verbal tics (嗯、啊、那個、就是說)
2. Fix common auto-caption errors:
   - 飛農 → 非農
   - 聯準 → 聯準會
   - 利率 → 利率（check context）
   - 台幣 → 新台幣
   - Numbers may be garbled — cross-reference with context
3. Identify timestamps for key sections
4. Remove sponsorship/ad segments (already filtered by MCP, but double-check)

### Section Identification
Identify these sections in the transcript:
- **Opening / 開場**: Background context, what prompted this video
- **Data Review / 數據回顧**: Specific economic data discussed
- **Analysis / 分析**: Host's interpretation and reasoning
- **Market Impact / 市場影響**: How this affects markets/investments
- **Recommendation / 建議**: Specific investment suggestions or warnings
- **Closing / 結尾**: Summary and future outlook

## Step 2: Core Argument Extraction

### Main Thesis (核心論述)
Extract in exactly this format:
- **One-sentence summary**: What is the host's central message?
- **Key premise**: What assumption does the argument rest on?
- **Logical chain**: A → B → C → Conclusion
- **Confidence level expressed**: Did the host express certainty or hedging?

### Supporting Arguments (支撐論據)
For each supporting point:
1. The claim made
2. The evidence cited (specific data, historical example, or authority)
3. The logical connection to the main thesis
4. Strength assessment: Strong (data-backed) / Medium (logical but no data) / Weak (opinion only)

### Counter-Arguments Acknowledged
- Did the host address opposing views?
- If yes, how were they dismissed? (Valid rebuttal or hand-waving?)
- If no, what obvious counter-arguments were missing?

## Step 3: Data Reference Extraction

### For Every Number Mentioned
Create a structured record:

| Field | Description |
|-------|-------------|
| Indicator | What economic indicator (e.g., US CPI) |
| Value | The specific value cited (e.g., 3.2%) |
| Period | Time period (e.g., October 2025 YoY) |
| Source | Attributed source (e.g., BLS, 主計處) |
| Context | How it was used in the argument |
| Verifiable | Can we check this against FRED/TWSE/Yahoo? |

### Data Quality Flags
- ⚠️ **Outdated**: Data cited is from >2 months ago without noting it
- ⚠️ **Selective**: Cherry-picked time period or metric
- ⚠️ **Misattributed**: Wrong source or wrong indicator name
- ⚠️ **Approximate**: Rounded number without noting approximation
- ✅ **Accurate**: Matches verifiable source
- ℹ️ **Unverifiable**: Cannot be independently checked with available tools

## Step 4: Market View Extraction

### Stance Classification
| Category | Definition |
|----------|------------|
| Strong Bullish | 明確看多，建議加碼 |
| Mild Bullish | 偏多但有保留，觀望中偏買 |
| Neutral | 不看多也不看空，建議觀望 |
| Mild Bearish | 偏空但有保留，建議減碼或避開 |
| Strong Bearish | 明確看空，建議出場或放空 |

### For Each Market View
- **Target**: What asset/market/sector is the view about?
- **Direction**: Bullish / Bearish / Neutral
- **Time Horizon**:
  - Short-term: 1-2 weeks
  - Medium-term: 1-3 months
  - Long-term: 3+ months
- **Key Levels**: Support/resistance mentioned
- **Catalyst**: What event could change the view
- **Risk Factor**: What could go wrong
- **Position Sizing Hint**: Full position? Partial? Wait for pullback?

## Step 5: Prediction Tracking

### For Any Forward-Looking Statement
- **What was predicted**: Specific, falsifiable statement
- **When**: Target date or condition
- **Confidence expressed**: "I think" vs "I'm sure" vs "It's possible"
- **Verifiable by**: What data point would confirm/deny this
- **Status**: Pending / Confirmed / Denied / Expired

### Prediction Accuracy Database
When processing new videos, check SQLite for previous predictions from the same host:
- Has enough time passed to evaluate?
- Was the prediction correct?
- Update the prediction record if so

## Step 6: Bias & Quality Assessment

### Potential Biases to Check
| Bias | Check For |
|------|-----------|
| Confirmation Bias | Only presenting data that supports the pre-existing view |
| Recency Bias | Overweighting recent events |
| Anchoring | Stuck on a previous price/level/prediction |
| Authority Bias | "因為巴菲特說..." without checking if context applies |
| Narrative Fallacy | Creating a compelling story that doesn't match data |
| Survivorship Bias | Only looking at successful examples |
| Home Bias | Overweighting Taiwan market impact |

### Overall Quality Rating
| Rating | Criteria |
|--------|----------|
| ★★★★★ | Data-rich, balanced, acknowledges uncertainty, specific and falsifiable |
| ★★★★ | Good data, mostly balanced, clear reasoning |
| ★★★ | Some data, reasonable logic, but gaps in evidence |
| ★★ | Opinion-heavy, limited data, one-sided |
| ★ | Speculation, no data, emotional appeal |

## Step 7: Actionable Summary Generation

### Summary Structure (per video)
1. **One-liner**: Most important takeaway (1 sentence)
2. **Key thesis**: What the host believes and why (2-3 sentences)
3. **Data highlights**: Most important numbers cited (bullet list)
4. **Market view**: Bull/bear stance on specific targets (table)
5. **Action items**: Specific suggestions made (bullet list)
6. **Risk factors**: What could invalidate the thesis (bullet list)
7. **Verification needed**: Claims to cross-check with data (bullet list)
