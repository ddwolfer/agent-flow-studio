# Scraping Patterns by Source

## General Rules
- Use Playwright MCP for all scraping
- Respect rate limits — wait 2-3 seconds between page loads
- Check robots.txt before scraping
- For PDF content: download file, extract text with pdfplumber
- For HTML tables: use accessibility snapshot to extract structured data

## CBC (中央銀行)
**Pattern**: Static HTML pages with tables
- Navigate to target page
- Use `snapshot()` to get accessibility tree
- Extract tables from structured elements
- Interest rate decisions: look for `<table>` elements with rate data
- Press releases: extract from `.news_content` or similar container

## DGBAS (主計總處)
**Pattern**: Mix of HTML and downloadable Excel/PDF files
- Statistics pages often link to Excel/PDF downloads
- For CPI data: navigate to 物價統計, find latest monthly release
- For GDP: navigate to 國民所得, find quarterly release
- Download Excel files when available (more structured than HTML)

## FSC (金管會)
**Pattern**: Static HTML with nested navigation
- Deep navigation required (3-4 levels)
- Statistics often in PDF format
- Use `click()` to navigate through menus

## NDC Indicators (國發會景氣指標)
**Pattern**: JavaScript-rendered dashboard
- Wait for data to load after navigation
- Chart data may be in JavaScript variables
- Alternative: use the API endpoint if available

## Federal Reserve
**Pattern**: Well-structured HTML
- FOMC statements: Clean HTML, easy to extract
- Meeting minutes: Long HTML documents, extract full text
- Beige Book: Structured by district
- H.4.1: Downloadable CSV/XML available

## ECB
**Pattern**: Clean HTML with structured press releases
- Decisions page lists all recent decisions
- Economic Bulletin: well-structured sections

## Common Extraction Steps
1. `navigate(url)` — go to target page
2. `snapshot()` — get accessibility tree
3. Identify target content in the tree
4. Extract text or table data
5. If PDF link found: download, then use pdfplumber to extract
6. Clean extracted data (remove navigation, headers, footers)
7. Structure into JSON for SQLite storage
