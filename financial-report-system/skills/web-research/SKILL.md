---
name: web-research
description: Use when the user wants to scrape or fetch data from government websites, central bank publications, or official statistics bureaus. Triggers on phrases like 'web research', 'scrape', '爬取', '央行', '主計處', '金管會', 'government data', 'central bank statement'.
argument-hint: [source: cbc | dgbas | fsc | fed | custom-url] [topic]
allowed-tools: Bash, Read, Glob, Grep, Agent
effort: high
user-invocable: true
---

# Web Research — 政府網站資料爬取

## Purpose
Use Playwright browser automation to fetch data from government and institutional websites that don't have MCP integrations, particularly Taiwan's Central Bank, DGBAS, and FSC.

## Input
- `$ARGUMENTS[0]` = source code or custom URL
- `$ARGUMENTS[1]` = topic or specific data to look for

## Supported Sources
See [references/gov-sources.md](references/gov-sources.md) for full URL list and data structures:

| Code | Source | URL | Key Data |
|------|--------|-----|----------|
| `cbc` | 中央銀行 | cbc.gov.tw | 利率決議、貨幣政策、外匯存底、金融穩定報告 |
| `dgbas` | 主計總處 | dgbas.gov.tw | GDP、CPI、失業率、薪資統計、國民所得 |
| `fsc` | 金管會 | fsc.gov.tw | 金融監理、保險統計、證券統計 |
| `fed` | Federal Reserve | federalreserve.gov | FOMC statements, Beige Book, meeting minutes |
| `ecb` | ECB | ecb.europa.eu | Monetary policy decisions, economic bulletin |
| `boj` | Bank of Japan | boj.or.jp | Policy statements, Outlook Report |
| custom | Any URL | {provided URL} | User-specified content |

## Process

1. **Identify target**:
   - Map `$ARGUMENTS[0]` to the appropriate URL pattern from [references/gov-sources.md](references/gov-sources.md)
   - If custom URL provided, use it directly
   - Determine the specific page/section to scrape based on `$ARGUMENTS[1]`

2. **Navigate and extract** using Playwright MCP:
   - Follow the scraping patterns defined in [references/scraping-patterns.md](references/scraping-patterns.md) for each source
   - Handle common challenges: JavaScript-rendered content, PDF downloads, table extraction
   - For PDF content: download and extract text
   - For HTML tables: parse into structured data
   - Respect rate limits and robots.txt

3. **Clean and structure data**:
   - Remove navigation, headers, footers, ads
   - Extract key dates, numbers, and policy statements
   - Convert tables to structured format
   - Identify the publication date and data vintage

4. **Translate if needed**:
   - Government sources in Chinese: keep original + provide English key terms
   - Foreign sources in English: keep original + provide Chinese summary

5. **Store in SQLite**:
   - Table: `web_research`
   - Fields: timestamp, source, url, topic, extracted_data (JSON), raw_text, publication_date

6. **Present results**:
   - Structured summary of extracted data
   - Link to original source
   - Note any data quality issues or extraction limitations

## Output Format
```
## 🔍 Web Research — {source_name}

**來源**: {full URL}
**擷取時間**: {timestamp}
**資料日期**: {publication date if identified}

### 📄 擷取內容
{Structured presentation of extracted data}

### 📊 關鍵數據
| 項目 | 數值 | 備註 |
|------|------|------|
| ... | ... | ... |

### 📝 摘要
{Summary in Traditional Chinese}

### ⚠️ 注意事項
{Any extraction issues, data vintage warnings, or limitations}
```

## Additional Resources
- For complete government source URLs, see [references/gov-sources.md](references/gov-sources.md)
- For scraping patterns per source, see [references/scraping-patterns.md](references/scraping-patterns.md)
