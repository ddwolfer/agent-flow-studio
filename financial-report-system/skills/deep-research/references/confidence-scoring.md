# Confidence Scoring Methodology

---

## Per-Finding Confidence Score

Each finding gets a 0-100 confidence score:

### Component Weights

| Component | Weight | What It Measures |
|-----------|--------|-----------------|
| Data Quality | 30% | Source tier average, data freshness, specificity |
| Convergence | 30% | % of independent sources that agree |
| Completeness | 20% | Can we fully answer the sub-question? |
| Robustness | 20% | Does finding survive critique and counter-arguments? |

### Data Quality Scoring (0-100)

| Factor | Score |
|--------|-------|
| All Tier 1-2 sources, data <1 month old | 90-100 |
| Mix of Tier 1-3, data <3 months | 70-89 |
| Mostly Tier 3, data <6 months | 50-69 |
| Tier 4+ sources, data >6 months | 30-49 |
| No verifiable data | 0-29 |

### Convergence Scoring (0-100)

| Factor | Score |
|--------|-------|
| 5+ independent sources agree, no contradictions | 90-100 |
| 3-4 sources agree, minor contradictions | 70-89 |
| 2-3 sources agree, some contradictions | 50-69 |
| Sources split or mostly contradictory | 30-49 |
| Only 1 source or all contradict | 0-29 |

### Completeness Scoring (0-100)

| Factor | Score |
|--------|-------|
| Sub-question fully answered with rich detail | 90-100 |
| Mostly answered, minor gaps | 70-89 |
| Partially answered, significant gaps | 50-69 |
| Barely answered, major gaps | 30-49 |
| Cannot answer with available data | 0-29 |

### Robustness Scoring (0-100)

| Factor | Score |
|--------|-------|
| Survives strong critique, counter-evidence addressed | 90-100 |
| Survives moderate critique, some counter-evidence | 70-89 |
| Weakened by critique but still defensible | 50-69 |
| Significantly weakened by counter-evidence | 30-49 |
| Does not survive critique | 0-29 |

---

## Overall Report Confidence

Weighted average of all finding confidence scores, adjusted for:
- Finding importance (more important findings weighted higher)
- Finding independence (correlated findings don't count double)

### Confidence Labels

| Score | Label | Meaning |
|-------|-------|---------|
| ≥80 | **High** | Multiple high-tier sources converge, robust to critique |
| 60-79 | **Medium** | Some convergence, gaps exist, defensible but uncertain |
| 40-59 | **Low** | Limited data, conflicting sources, significant gaps |
| <40 | **Speculative** | Insufficient for reliable conclusion, treat as hypothesis |

### Presentation

Always present confidence visually:
```
Finding: "台灣央行將在6月升息半碼"
Confidence: 65/100 (Medium)
├── Data Quality: 75 (Tier 2 sources, recent data)
├── Convergence: 60 (2 of 3 sources agree)
├── Completeness: 70 (missing forward guidance specifics)
└── Robustness: 55 (counter-argument: inflation already cooling)
```
