# HTML Report Template

## Standalone HTML Template with Embedded CSS

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {
    --primary: #1a365d;
    --secondary: #2d3748;
    --accent: #3182ce;
    --bg: #ffffff;
    --bg-alt: #f7fafc;
    --text: #2d3748;
    --text-muted: #718096;
    --border: #e2e8f0;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --primary: #90cdf4;
      --secondary: #e2e8f0;
      --accent: #63b3ed;
      --bg: #1a202c;
      --bg-alt: #2d3748;
      --text: #e2e8f0;
      --text-muted: #a0aec0;
      --border: #4a5568;
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: "Noto Sans CJK TC", "微軟正黑體", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.8;
    color: var(--text);
    background: var(--bg);
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
  }
  h1 { font-size: 1.8rem; color: var(--primary); border-bottom: 3px solid var(--accent); padding-bottom: 0.5rem; margin: 2rem 0 1rem; }
  h2 { font-size: 1.4rem; color: var(--primary); margin: 1.5rem 0 0.8rem; }
  h3 { font-size: 1.1rem; color: var(--secondary); margin: 1.2rem 0 0.6rem; }
  p { margin: 0.6rem 0; }
  table { width: 100%; border-collapse: collapse; margin: 1rem 0; font-size: 0.9rem; }
  th { background: var(--primary); color: white; padding: 0.6rem; text-align: left; }
  td { padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); }
  tr:nth-child(even) { background: var(--bg-alt); }
  tr:hover { background: #edf2f7; }
  blockquote { border-left: 4px solid var(--accent); padding: 0.5rem 1rem; margin: 1rem 0; background: var(--bg-alt); }
  code { background: var(--bg-alt); padding: 0.2rem 0.4rem; border-radius: 3px; font-size: 0.85rem; }
  pre { background: var(--bg-alt); padding: 1rem; border-radius: 6px; overflow-x: auto; }
  img { max-width: 100%; height: auto; margin: 1rem 0; }
  .signal-box { border: 2px solid var(--accent); padding: 1rem; margin: 1.5rem 0; font-family: monospace; background: var(--bg-alt); }
  .meta { color: var(--text-muted); font-size: 0.85rem; margin-bottom: 2rem; }
  @media print {
    body { max-width: 100%; padding: 1cm; }
    .no-print { display: none; }
  }
</style>
</head>
<body>
{content}
</body>
</html>
```

## Usage Notes
- Replace `{title}` and `{content}` with actual report content
- Charts: embed as `<img src="assets/chart-name.png">` or inline SVG
- Tables: use standard HTML `<table>` (CSS handles styling)
- Signal box: wrap in `<div class="signal-box"><pre>...</pre></div>`
- Print: use browser print or Playwright `page.pdf()` for PDF output
- CJK fonts: falls back through multiple options for cross-platform compatibility
