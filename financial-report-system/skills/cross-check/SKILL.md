---
name: cross-check
description: Use when the user wants to verify a claim, market narrative, or analyst opinion against actual data. Triggers on phrases like 'cross check', 'verify', '驗證', '查證', 'fact check', 'is it true that', '是不是真的'.
argument-hint: [claim or statement to verify]
allowed-tools: Bash, Read, Glob, Grep, Agent
effort: high
user-invocable: true
---

# Cross-Check — 觀點交叉驗證

## Purpose
Take a specific claim, market narrative, or analyst opinion and systematically verify it against actual data from multiple independent sources. Identify common financial fallacies and cognitive biases.

## Input
- `$ARGUMENTS` = The claim or statement to verify (e.g., "外資連續賣超代表台股要崩盤", "升息一定利空股市", "台灣 CPI 已經見頂")

## Process

1. **Parse the claim**:
   - Use Sequential Thinking MCP to identify:
     - The core assertion (what is being claimed?)
     - The implied causality (what causes what?)
     - The prediction (what's expected to happen?)
     - The timeframe (when?)
     - Hidden assumptions

2. **Steelmanning first** (from critical_thinking + inversion_thinking):
   - Before debunking, construct the STRONGEST possible version of the claim
   - Ask: "What would make this claim TRUE? What's the best evidence for it?"
   - This prevents straw-man debunking and ensures fair evaluation

3. **Source credibility assessment**:
   - Who is making this claim? (analyst, YouTuber, official institution, anonymous)
   - What is their track record on similar claims?
   - Do they have conflicts of interest? (selling products, promoting positions)
   - Assign credibility tier per [references/verification-methods.md](references/verification-methods.md)

4. **Check for known fallacies**:
   - Reference [references/common-fallacies.md](references/common-fallacies.md)
   - Common financial fallacies to check:
     - Survivorship bias
     - Recency bias
     - Correlation ≠ causation
     - Cherry-picking time periods
     - Narrative fallacy
     - Anchoring bias
     - Gambler's fallacy
     - Composition fallacy (what's true for parts isn't true for whole)

5. **Gather verification data**:
   - FRED MCP: Pull relevant historical time series
   - Yahoo Finance MCP: Pull price history and fundamental data
   - TWSE MCP: Pull Taiwan-specific data
   - World Bank MCP: Pull international comparison if relevant
   - SQLite MCP: Pull stored historical analyses

6. **Apply verification methods** from [references/verification-methods.md](references/verification-methods.md):

   **A. Historical Back-Test**
   - Find all past instances of the claimed pattern
   - What actually happened each time?
   - Calculate base rate (how often does the claim hold true?)
   - Statistical significance test if sufficient sample size

   **B. Cross-Source Verification**
   - Does FRED data support the claim?
   - Does Yahoo Finance data support it?
   - Does TWSE data support it?
   - Do they all tell the same story?

   **C. Conditional Analysis**
   - Is the claim only true under certain conditions?
   - What are the boundary conditions?
   - Are those conditions currently met?

   **D. Counter-Example Search**
   - Actively search for instances where the claim was FALSE
   - How many counter-examples exist?
   - Are counter-examples more recent or more numerous?

7. **Inversion Analysis** (Charlie Munger method):
   - **Q1: How to guarantee this claim leads to a bad outcome?** What conditions would make acting on this claim catastrophically wrong?
   - **Q2: When would this advice backfire?** Under what market/economic conditions?
   - **Q3: What risks is the claimant NOT considering?** Missing risk factors, blind spots
   - **Q4: What's reasonable about the OPPOSITE view?** Steelman the counter-position
   - **Pre-Mortem**: Imagine you acted on this claim and lost money — what went wrong?

8. **Assess the claim**:
   - **Verdict**: Supported / Partially Supported / Not Supported / Misleading / Insufficient Data
   - **Confidence**: High / Medium / Low
   - **Nuance**: Under what conditions is it true/false?
   - **Base Rate**: How often has this pattern held historically?

9. **Store in SQLite**:
   - Table: `cross_checks`
   - Fields: timestamp, claim, verdict, confidence, base_rate, evidence_summary, fallacies_identified

## Output Format
```
## ✅ 交叉驗證報告

### 📌 待驗證觀點
> "{original claim}"

### 🔍 拆解分析
- **核心主張**: {what is being claimed}
- **隱含因果**: {implied causality}
- **隱含預測**: {what should happen}
- **時間框架**: {timeframe}
- **隱藏假設**: {hidden assumptions}

### ⚠️ 潛在偏誤
| 偏誤類型 | 是否存在 | 說明 |
|---------|---------|------|
| {bias type} | ✓/✗ | {explanation} |

### 📊 數據驗證

#### 歷史回測
- 過去 {N} 次類似情境中，該觀點成立 {M} 次 (base rate: {M/N}%)
- 統計顯著性: {significant / not significant}
| 日期 | 情境 | 結果 | 與觀點一致？ |
|------|------|------|-------------|
| ... | ... | ... | ✓/✗ |

#### 多源驗證
| 來源 | 支持？ | 數據 |
|------|--------|------|
| FRED | ✓/✗ | {specific data} |
| Yahoo Finance | ✓/✗ | {specific data} |
| TWSE | ✓/✗ | {specific data} |

#### 反例搜尋
- 找到 {N} 個反例
- 最近反例: {description}

### 🎯 結論

**判定**: {Supported / Partially Supported / Not Supported / Misleading / Insufficient Data}
**信心水準**: {High / Medium / Low}
**Base Rate**: {N}%

**精確說法應該是**:
> "{nuanced, more accurate version of the claim}"

### 💡 補充說明
{Additional context, conditions, and caveats in Traditional Chinese}
```

## Additional Resources
- For verification methods, see [references/verification-methods.md](references/verification-methods.md)
- For common financial fallacies, see [references/common-fallacies.md](references/common-fallacies.md)
