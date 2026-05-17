# PDF Conversion Settings

## Method 1: Pandoc (preferred if LaTeX installed)

```bash
pandoc report.md -o report.pdf \
  --pdf-engine=xelatex \
  -V geometry:margin=2.54cm \
  -V mainfont="Noto Sans CJK TC" \
  -V monofont="Noto Sans Mono" \
  -V fontsize=12pt \
  -V lang=zh-TW \
  --toc \
  --toc-depth=2 \
  --highlight-style=tango
```

**Requirements**: texlive-xetex, texlive-fonts-recommended, fonts-noto-cjk

## Method 2: HTML → PDF via Playwright (fallback)

```javascript
const { chromium } = require('playwright');
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(`file://${absolutePath}/report.html`);
await page.pdf({
  path: 'report.pdf',
  format: 'A4',
  margin: { top: '2.54cm', bottom: '2.54cm', left: '2.54cm', right: '2.54cm' },
  printBackground: true
});
await browser.close();
```

## Method 3: Pandoc Markdown → HTML (always works)

```bash
pandoc report.md -o report.html --standalone --embed-resources
```
Then use Method 2 to convert HTML to PDF.

## Page Settings
- **Size**: A4 (210mm × 297mm)
- **Margins**: 2.54cm all sides
- **Font**: 12pt body, CJK-compatible font required
- **Header**: Report title (optional)
- **Footer**: Page number centered
- **TOC**: Auto-generated from headings
