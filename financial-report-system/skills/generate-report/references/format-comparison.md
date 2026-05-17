# Report Format Comparison

## When to Use Which Format

| Scenario | Recommended | Why |
|----------|------------|-----|
| Quick sharing via browser/email | **HTML** | Opens anywhere, no special viewer needed |
| Formal distribution, archival | **PDF** | Fixed layout, looks same everywhere |
| Needs editing by others | **DOCX** (use /generate-docx) | Editable in Word/Google Docs |
| Presentation to audience | **PPTX** (use /generate-pptx) | Designed for projection/slides |
| Daily tracking notes | **HTML** | Fast to generate, easy to search |
| Weekly/monthly report | **PDF** or **DOCX** | More formal, print-friendly |
| Research paper | **PDF** | Academic standard |
| Interactive dashboard | **HTML** | Can embed interactive charts |

## Format Capabilities

| Feature | HTML | PDF | DOCX | PPTX |
|---------|------|-----|------|------|
| Charts | ✅ (inline/SVG) | ✅ (embedded) | ✅ (embedded) | ✅ (native) |
| Tables | ✅ (styled) | ✅ (fixed) | ✅ (editable) | ✅ (native) |
| CJK text | ✅ (web fonts) | ✅ (needs CJK font) | ✅ (needs font) | ✅ (needs font) |
| Interactive | ✅ | ❌ | ❌ | ❌ |
| Print quality | Medium | High | High | Medium |
| File size | Small | Medium | Medium | Large |
| Editable | View source | ❌ | ✅ | ✅ |
| Searchable | ✅ | ✅ | ✅ | ✅ |

## Conversion Paths

```
Markdown (source)
├── Pandoc → HTML (standalone, embedded CSS)
├── Pandoc → PDF (via XeLaTeX for CJK)
├── Pandoc → DOCX (basic formatting)
└── HTML → PDF (via Playwright print, fallback)
```

All reports start as Markdown → convert to target format via Pandoc MCP.
