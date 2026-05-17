---
name: generate-docx
description: "Create professional Word documents from analysis results. Use when: user wants Word doc, report, memo, '產生Word', '產生文件', '寫報告', .docx output. Covers: creating new documents (docx-js), editing existing (OOXML), and financial report generation."
argument-hint: [topic] [source: latest-analysis | custom]
effort: high
user-invocable: true
---

# Generate DOCX — Word 文件生成

Create professional Word documents. For complete technical reference, see source files in `skill-sources/skills/skills/docx/` and `skill-sources/claude-office-skills/public/docx/`.

## Reference Files

| File | Purpose |
|------|---------|
| [docx-full-reference.md](references/docx-full-reference.md) | Complete DOCX skill reference — docx-js API, OOXML editing, tracked changes, formatting rules, document structure (copied from official anthropics/skills) |

Full original source also available at: `skill-sources/skills/skills/docx/SKILL.md`

---

## Workflow

1. **Gather content**: From conversation or SQLite latest analysis
2. **Plan structure** (see [docx-full-reference.md](references/docx-full-reference.md) for detailed guidance):
   - Cover page → TOC → Executive Summary → Background → Analysis → Scenarios → Conclusions → Risk Disclaimer → Appendix
3. **Generate charts**: Chart MCP → save PNG → embed
4. **Create document**: Using docx-js (npm) or python-docx — see [docx-full-reference.md](references/docx-full-reference.md) for API details
5. **Apply formatting** per the formatting section in [docx-full-reference.md](references/docx-full-reference.md)
6. **Save**: `/mnt/c/FINANCIAL/reports/{date}_{topic}.docx`

## Formatting Quick Reference

- Page: A4, margins 2.54cm
- Title: 22pt bold centered
- H1: 16pt bold dark blue
- H2: 14pt bold
- Body: 12pt, 1.5 line spacing
- Tables: 10pt, alternating rows, bordered
- Chinese: 微軟正黑體 / CJK font
- English: Times New Roman (body) / Arial (headings)
- Page numbers bottom center, header with title

## Dependencies
- `npm install -g docx` — document generation
- `pip install python-docx` — alternative Python approach
- LibreOffice — PDF conversion
- Pandoc — format conversion
