---
name: generate-pptx
description: "Create professional PowerPoint presentations from analysis results, market data, or custom content. Use when: user wants slides, presentation, deck, PPT, '做簡報', '產生PPT', 'powerpoint', or references a .pptx file. Covers: creating from scratch (PptxGenJS/html2pptx), editing templates (OOXML unpack/edit/pack), and populating data into existing layouts."
argument-hint: [topic] [source: latest-analysis | custom]
effort: high
user-invocable: true
---

# Generate PPTX — PowerPoint 簡報生成

Create professional PowerPoint presentations. Three workflows available depending on context.

## Reference Files

**Read the relevant reference file COMPLETELY before starting work.**

| File | When to Read |
|------|-------------|
| [pptxgenjs-guide.md](references/pptxgenjs-guide.md) | Creating from scratch (no template) |
| [editing-guide.md](references/editing-guide.md) | Editing existing presentations (unpack/edit/pack) |
| [design-principles.md](references/design-principles.md) | Always — color, typography, layout, QA |
| [formatting-standards.md](references/formatting-standards.md) | Always — IB-grade formatting, tables, bullets |

For complete source reference, see also:
- `skill-sources/skills/skills/pptx/` (official Anthropic)
- `skill-sources/claude-office-skills/public/pptx/` (tfriedel)
- `skill-sources/financial-services-plugins/investment-banking/skills/pitch-deck/` (IB deck)

---

## Quick Reference

| Task | Guide |
|------|-------|
| Read/analyze existing | `python -m markitdown presentation.pptx` |
| Create from scratch | Read [pptxgenjs-guide.md](references/pptxgenjs-guide.md) — use PptxGenJS |
| Edit existing/template | Read [editing-guide.md](references/editing-guide.md) — unpack→edit→pack |

---

## Workflow: Create from Scratch

1. **Gather content**: From conversation context or query SQLite for latest analysis
2. **Design**: Choose color palette, fonts, layouts per [design-principles.md](references/design-principles.md)
3. **Create slides**: Using PptxGenJS per [pptxgenjs-guide.md](references/pptxgenjs-guide.md)
4. **Generate charts**: Use Chart MCP → save as PNG → embed
5. **QA**: Convert to images, visual inspect, fix, re-verify
6. **Save**: `/mnt/c/FINANCIAL/reports/{date}_{topic}.pptx`

## Workflow: Edit Template

1. **Analyze template**: `thumbnail.py` + `markitdown`
2. **Plan slide mapping**: Content → layout
3. **Unpack → Edit XML → Clean → Pack**
4. **QA**: Visual inspection loop

## Workflow: Financial Report Slides

For macro analysis / market scan / YT briefing results:

**Typical slide structure:**
1. Title slide (topic, date)
2. Executive Summary (3-5 key points)
3-5. Key Data slides (tables + charts from MCP data)
6-8. Analysis slides (one per perspective if from /macro-analysis)
9. Scenario Analysis (if applicable)
10. Conclusions & Recommendations
11. Risk Factors
12. Appendix (data sources)

---

## Design Principles (Summary)

See [design-principles.md](references/design-principles.md) for full details.

- **Don't create boring slides** — no plain bullets on white
- **Pick content-informed colors** — not default blue
- **Every slide needs a visual element** — chart, icon, shape
- **Commit to one visual motif** — repeat across all slides
- **Typography**: Header 36-44pt, body 14-16pt, never default Arial everywhere
- **Chinese fonts**: 微軟正黑體 or available CJK font
- **中英混合**: Chinese analysis text + English indicator names (GDP, CPI)

---

## QA (Required — from official Anthropic skill)

**Assume there are problems. Your job is to find them.**

### Content QA
```bash
python -m markitdown output.pptx
python -m markitdown output.pptx | grep -iE "xxxx|lorem|ipsum|placeholder"
```

### Visual QA
Convert to images → use subagent with fresh eyes:
```bash
soffice --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
```

Check for: overlapping elements, text overflow, low contrast, uneven spacing, leftover placeholders.

**Do not declare success until at least one fix-and-verify cycle.**

---

## Dependencies
- `pip install "markitdown[pptx]"` — text extraction
- `npm install -g pptxgenjs` — creating from scratch
- LibreOffice (`soffice`) — PDF conversion
- Poppler (`pdftoppm`) — PDF to images

---

## Output
- File: `/mnt/c/FINANCIAL/reports/{date}_{topic_slug}.pptx`
- Disclaimer: "Validated using LibreOffice. Please review in Microsoft PowerPoint before distribution."
