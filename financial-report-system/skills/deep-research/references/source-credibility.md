# Source Credibility Scoring Framework

---

## Five-Tier Source Classification

| Tier | Score Range | Source Types | Examples |
|------|-----------|-------------|---------|
| 1 (Highest) | 90-100 | Official government statistics, central bank data, regulatory filings | BLS (CPI, NFP), Fed (FOMC), DGBAS (台灣GDP), CBC (央行), SEC filings |
| 2 (High) | 80-90 | Established financial data providers, wire services | FRED, Bloomberg, Reuters, Yahoo Finance, TWSE official |
| 3 (Medium) | 60-80 | Analyst reports, academic research, established financial media | IMF/World Bank reports, NBER papers, WSJ, FT, Economist |
| 4 (Lower) | 40-60 | YouTube analysts, established blogs, opinion columns | 游庭皓, 張貽程, Seeking Alpha, ZeroHedge |
| 5 (Lowest) | 0-40 | Anonymous sources, social media, unverifiable claims | Reddit posts, Twitter threads, anonymous blogs |

## Scoring Adjustments

### Positive Adjustments (+5 to +15)
- Source has track record of accuracy on this specific topic
- Data is very recent (published within last week)
- Multiple independent verification available
- Source has no commercial interest in the outcome

### Negative Adjustments (-5 to -15)
- Source has commercial interest (selling a product/service)
- Data is stale (>6 months old without noting vintage)
- Source has history of inaccuracy
- Methodology is opaque or unstated
- Source is primarily opinion without data backing

## Application Rules

1. **Core claims require Tier 1-2 sources**
2. **Supporting context can use Tier 3 sources**
3. **Tier 4 sources are SUPPLEMENTARY only** — never the sole basis for a conclusion
4. **Tier 5 sources should be FLAGGED** and used only when no better source exists
5. **Always note the tier when citing**: "According to BLS data (Tier 1)..." or "YouTube analyst 游庭皓 suggests (Tier 4, cross-check recommended)..."

## Financial Data Source Reliability

| Data Type | Most Reliable Source | Fallback |
|-----------|---------------------|----------|
| US GDP | BEA (via FRED) | Bloomberg |
| US CPI/Inflation | BLS (via FRED) | Bloomberg |
| US Employment | BLS (via FRED) | ADP (private) |
| Fed Policy | Federal Reserve (FRED, federalreserve.gov) | CME FedWatch |
| Taiwan GDP/CPI | 主計總處 (DGBAS) | CBC |
| Taiwan Stock Market | TWSE (official) | Yahoo Finance |
| Global Indices | Exchange official feeds | Yahoo Finance |
| Company Financials | SEC filings (10-K, 10-Q) | Yahoo Finance |
