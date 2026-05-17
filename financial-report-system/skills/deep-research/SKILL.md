---
name: deep-research
description: "Enterprise-grade multi-source research with citation tracking, credibility scoring, and verified conclusions. Use when: user needs thorough investigation on a specific economic/financial topic, '深度研究', '深入分析', 'research report', comprehensive analysis, multi-source verification, compare options, or any topic requiring 10+ sources and structured evidence. Not for simple data lookups (use /data-snapshot) or quick macro views (use /macro-analysis lite mode)."
argument-hint: [research topic or question]
effort: high
user-invocable: true
---

# Deep Research — 深度多源研究

Deliver citation-backed, verified research reports through a structured 8-phase pipeline with source credibility scoring, evidence triangulation, and progressive report generation.

**Autonomy Principle:** Operate independently. Infer assumptions from context. Only stop for critical errors or incomprehensible queries.

## Reference Files

| File | Load When |
|------|-----------|
| [research-pipeline.md](references/research-pipeline.md) | Always — detailed phase instructions |
| [source-credibility.md](references/source-credibility.md) | Phase 4+ — credibility scoring framework |
| [confidence-scoring.md](references/confidence-scoring.md) | Phase 7+ — confidence calculation |

---

## Decision Tree

```
Request Analysis
├── Simple lookup (<3 sources) → STOP: Use WebSearch directly
├── Quick macro view → STOP: Use /macro-analysis lite
├── Verify a claim → STOP: Use /cross-check
├── Complex multi-source research → CONTINUE
│
Mode Selection
├── quick    (3 phases, ~5 min)  → SCOPE → RETRIEVE → PACKAGE
├── standard (6 phases, ~15 min) → + PLAN + TRIANGULATE + SYNTHESIZE [DEFAULT]
├── deep     (8 phases, ~30 min) → + CRITIQUE + REFINE
└── ultradeep (8+ phases, ~45 min) → Maximum rigor, 15k+ words
```

---

## Phase 1: SCOPE — Research Framing

1. Decompose the question into 3-7 sub-questions using Sequential Thinking MCP
2. Identify stakeholder perspectives (who cares about this?)
3. Define scope boundaries (what's in/out)
4. Map sub-questions to data sources:
   - FRED MCP → US macro data
   - Yahoo Finance MCP → Market data
   - TWSE MCP → Taiwan data
   - World Bank MCP → International comparison
   - Playwright MCP → Government websites, central bank publications
   - SQLite MCP → Historical analyses, YT summaries
   - WebSearch → Current news, analysis, academic sources
5. List key assumptions to validate

---

## Phase 2: PLAN — Strategy (Standard+ modes)

1. Identify primary and secondary sources
2. Map knowledge dependencies (what must be understood first)
3. Create search query strategy with variants
4. Plan triangulation approach
5. Define quality gates (how many sources needed per claim)

---

## Phase 3: RETRIEVE — Parallel Information Gathering

**CRITICAL: Execute ALL data pulls in parallel**

### Quantitative Data (MCP servers)
Pull all relevant indicators simultaneously:
- FRED: Series relevant to topic
- Yahoo Finance: Market data, prices, fundamentals
- TWSE: Taiwan-specific data
- World Bank: Cross-country data
- SQLite: Historical snapshots, prior analyses, YT summaries

### Qualitative Data (Web + Playwright)
- WebSearch: 5-10 parallel searches covering different angles
- Playwright MCP: Central bank statements, government publications
- SQLite: Check if YT analysts (游庭皓/張貽程) covered this topic

### Source Quality Thresholds (First Finish Search)

| Mode | Min Sources | Min Avg Credibility |
|------|-----------|-------------------|
| Quick | 10+ | >60/100 |
| Standard | 15+ | >60/100 |
| Deep | 25+ | >70/100 |
| UltraDeep | 30+ | >75/100 |

**Source diversity requirements:**
- Minimum 3 source types (official data, financial data, analysis/commentary)
- Temporal diversity (recent + historical)
- Perspective diversity (bulls + bears + neutral)

---

## Phase 4: TRIANGULATE — Cross-Verification (Standard+)

For each major claim:
1. Identify the claim clearly
2. Find 3+ independent sources supporting or contradicting
3. Score each source using [source-credibility.md](references/source-credibility.md):

| Tier | Source Type | Score | Weight |
|------|-----------|-------|--------|
| 1 | Official statistics (BLS, Fed, DGBAS, CBC), regulatory filings | 90-100 | 1.0 |
| 2 | FRED, Bloomberg, Reuters, established financial data providers | 80-90 | 0.9 |
| 3 | Analyst reports, academic research, established financial media | 60-80 | 0.7 |
| 4 | YouTube analysts, social media, blogs, opinion | 40-60 | 0.5 |
| 5 | Anonymous, no citation, unverifiable | 0-40 | 0.2 |

4. Flag contradictions between sources
5. Note consensus areas vs debate areas
6. Document verification status: ✅ Verified / ⚠️ Partially verified / ❌ Contradicted / ❓ Unverifiable

---

## Phase 4.5: OUTLINE REFINEMENT (Standard+)

After triangulation, dynamically adapt the research outline based on evidence discovered:

1. **Compare initial scope vs actual findings**: Do the sub-questions still make sense?
2. **Evaluate adaptation need**:
   - Evidence confirms initial framing → Proceed with original outline
   - Evidence reveals unexpected angles → Add new sub-questions
   - Evidence contradicts initial assumptions → Revise thesis direction
3. **Targeted gap filling**: For any sub-question with <2 sources, run additional searches
4. **Anti-pattern**: Do NOT lock into original outline if evidence points elsewhere. The research should follow the evidence, not the plan.

---

## Phase 5: SYNTHESIZE (Standard+)

1. Organize findings by sub-question
2. For each finding:
   - State the claim
   - Present supporting evidence with citations [N]
   - Present counter-evidence if any
   - Assess confidence level
3. Identify emergent patterns across sub-questions
4. Generate novel insights (what does the combination of findings suggest?)
5. Connect to existing knowledge in SQLite (prior analyses)

---

## Phase 6: CRITIQUE (Deep+)

Self-adversarial review:
- What's the strongest argument AGAINST my conclusions?
- Where is my evidence weakest?
- Am I confusing correlation with causation?
- What information is missing that could change everything?
- Am I biased by the order I encountered sources?
- Would an expert in this field disagree? Why?

---

### Critical Gap Loop-Back
If critique reveals a critical blind spot:
1. Define 1-3 targeted "delta queries" to fill the gap
2. Return to Phase 3 RETRIEVE for those specific queries only (time-box: 3-5 min)
3. Re-run Phase 4 TRIANGULATE on new evidence
4. Maximum 1 loop-back per analysis (prevent infinite cycles)

---

## Phase 7: REFINE (Deep+)

1. Adjust conclusions based on critique
2. Calculate confidence scores using [confidence-scoring.md](references/confidence-scoring.md):

| Component | Weight | Calculation |
|-----------|--------|------------|
| Data Quality | 30% | Avg source tier score, data freshness |
| Convergence | 30% | % of independent sources agreeing |
| Completeness | 20% | % of sub-questions fully answered |
| Robustness | 20% | Survives critique? Counter-evidence addressed? |

**Overall Confidence Thresholds:**
- ≥80: High — multiple Tier 1-2 sources converge
- 60-79: Medium — some convergence, gaps exist
- 40-59: Low — limited data, conflicting sources
- <40: Speculative — insufficient for reliable conclusion

3. Update scenario probabilities if applicable
4. Strengthen citations, remove unsupported claims

---

## Phase 8: PACKAGE — Report Generation

### Store in SQLite
`deep_research` table with all fields from sqlite-schema.md

### Generate Report
Progressive section generation:

1. **Executive Summary** (200-400 words)
2. **Introduction** (scope, methodology, assumptions)
3. **Findings 1-N** (600-2000 words each, fully cited)
4. **Synthesis & Insights** (patterns, implications)
5. **Limitations & Caveats** (what we couldn't determine)
6. **Recommendations** (actionable, specific)
7. **Bibliography** (COMPLETE — every citation, no placeholders)

### Report Length by Mode

| Mode | Target Words | Findings |
|------|-------------|----------|
| Quick | 2,000-4,000 | 2-3 findings |
| Standard | 4,000-8,000 | 4-6 findings |
| Deep | 8,000-15,000 | 6-8 findings |
| UltraDeep | 15,000-20,000 | 8-12 findings |

### Output Token Safeguard
- Claude Code default limit: ~32,000 output tokens (~24,000 words)
- Target ≤20,000 words total output per execution
- Reports >20,000 words: split into sections, generate progressively using Write/Edit
- Track citations in a persistent `sources.json` file in the report folder (survives context compaction)

### Quality Standards
- **Prose-first**: ≥80% flowing prose, ≤20% bullet lists
- **Citation density**: Every major claim cited in same sentence [N]
- **No placeholders**: Zero "TBD", "Content continues", "[Section X]"
- **Evidence-rich**: Specific data points, statistics, quotes
- **Complete bibliography**: Every [N] has corresponding entry

### Output Format

```markdown
## 🔬 深度研究報告

### 📋 研究主題: {topic}
**研究日期**: {date}
**研究深度**: {mode}
**整體信心**: {score}/100 — {High/Medium/Low/Speculative}
**來源數量**: {N} sources across {M} source types

---

### 🔑 核心發現
1. {Finding 1} [信心: {score}] [來源: Tier {N}]
2. {Finding 2} [信心: {score}] [來源: Tier {N}]
...

### 📊 數據證據
| 數據點 | 數值 | 來源 | 可信度 | 時效 |
|--------|------|------|--------|------|

### 🔍 詳細分析
#### Finding 1: {title}
{600-2000 words of prose with inline citations [N]}

#### Finding 2: {title}
...

### ⚖️ 正反論點
**支持**: {arguments with evidence}
**反對**: {counter-arguments with evidence}

### ❓ 未解之處
- {What we couldn't determine and why}
- {What additional data would help}

### 🎯 建議
1. {Specific, actionable recommendation}
2. ...

### 📚 來源清單
| # | 來源 | 類型 | 可信度 | URL |
|---|------|------|--------|-----|
| [1] | {source} | Tier {N} | {score}/100 | {url} |
```

---

## Quality Checklist
- [ ] All sub-questions addressed
- [ ] 10+ sources cited (15+ for standard, 25+ for deep)
- [ ] Every claim has inline citation [N]
- [ ] Bibliography complete (no missing entries)
- [ ] No fabricated data or unsupported assertions
- [ ] Confidence scores calculated per finding
- [ ] Counter-arguments presented
- [ ] Limitations acknowledged
- [ ] Stored in SQLite
- [ ] Prose-first (≥80%), no bullet-list padding
