# Deep Research Pipeline — Detailed Phase Instructions

Merged from: 199-biotechnologies/claude-deep-research-skill (methodology.md, quality-gates.md, report-assembly.md)

---

## Phase 3 Detail: Parallel Retrieval Protocol

### Query Decomposition Strategy
Before launching searches, decompose into 5-10 independent angles:
1. **Core topic (semantic)** — Main concept exploration
2. **Technical details (keyword)** — Specific terms, implementations
3. **Recent developments (date-filtered)** — Last 12-18 months
4. **Academic sources** — Papers, research, formal analysis
5. **Alternative perspectives** — Competing approaches, criticisms
6. **Statistical/data sources** — Quantitative evidence, metrics
7. **Industry analysis** — Commercial applications, market trends
8. **Critical analysis** — Known problems, failure modes, edge cases

### Parallel Execution
**Use a single message with multiple tool calls:**
- 5-10 WebSearch calls covering different angles
- 2-3 Agent subagents for deep dives (academic papers, technical docs)
- MCP data pulls (FRED, Yahoo Finance, TWSE, World Bank) in parallel

### Sub-agent Output Format
Require structured evidence from all sub-agents:
```json
{
  "claim": "specific claim text",
  "evidence_quote": "exact quote from source",
  "source_url": "https://...",
  "source_title": "...",
  "confidence": 0.85
}
```

---

## Phase 4 Detail: Triangulation Protocol

### Verification Status per Claim
| Status | Criteria |
|--------|---------|
| ✅ Verified | 3+ independent Tier 1-2 sources agree |
| ⚠️ Partially | 2 sources agree, or mix of Tier 2-3 |
| ❌ Contradicted | Sources directly contradict each other |
| ❓ Unverifiable | Cannot check with available tools |

### Contradiction Resolution
When sources conflict:
1. Check data vintage (newer > older)
2. Check source tier (higher tier > lower)
3. Check methodology (consistent > inconsistent)
4. Present BOTH sides, don't hide the conflict
5. Note which resolution was chosen and why

---

## Phase 8 Detail: Progressive Report Generation

### Anti-Fatigue Protocol
**Apply to EVERY section before moving to next:**
- [ ] ≥3 paragraphs for major sections
- [ ] ≥80% prose (not bullet lists)
- [ ] Zero placeholders ("TBD", "Content continues")
- [ ] Specific data points and statistics included
- [ ] Major claims cited in same sentence

**If ANY fails**: Regenerate section before continuing.

### Bullet Point Policy
- Use bullets SPARINGLY: Only for distinct lists (company names, enumerated steps)
- NEVER as primary content delivery
- Convert: "• Market size: $2.4B" → "The global market reached $2.4 billion in 2023 [1]."

### Bibliography Requirements (ZERO TOLERANCE)
- Every [N] in text has corresponding bibliography entry
- Every entry has: author/org, title, date, URL (if available)
- No fabricated citations
- No placeholder entries
- Run mental verification: Does citation [N] actually support the claim it's attached to?

### Length Targets

| Mode | Words | Findings | Min Sources |
|------|-------|----------|------------|
| Quick | 2,000-4,000 | 2-3 | 10 |
| Standard | 4,000-8,000 | 4-6 | 15 |
| Deep | 8,000-15,000 | 6-8 | 25 |
| UltraDeep | 15,000-20,000 | 8-12 | 30 |

### Report File Output
Save to: `/mnt/c/FINANCIAL/reports/{topic_slug}_Research_{YYYYMMDD}.md`
Optionally convert to HTML/PDF using /generate-report skill.
