---
name: data-snapshot
description: Use when the user wants to get current macroeconomic indicators, check latest economic data, or get a quick overview of key metrics for US, Taiwan, or global markets. Triggers on phrases like 'data snapshot', 'current indicators', 'latest macro data', 'economic overview', '總經快照', '目前數據'.
argument-hint: [region: US | TW | Global | all]
allowed-tools: Bash, Read, Glob, Grep, Agent
effort: high
user-invocable: true
---

# Data Snapshot — 即時總經指標快照

## Purpose
Pull the latest macroeconomic indicators from multiple data sources and present a structured overview. Store results in SQLite for historical tracking.

## Input
- `$ARGUMENTS` = region filter (US, TW, Global, or blank for all)
- If no argument provided, pull all regions

## Process

1. **Determine scope** based on `$ARGUMENTS`:
   - `US` → FRED MCP only
   - `TW` → TWSE MCP + relevant Yahoo Finance
   - `Global` → World Bank MCP + Yahoo Finance global indices
   - `all` or blank → All of the above

2. **Pull US indicators** (if in scope):
   - Use FRED MCP to fetch each series listed in [references/indicators-us.md](references/indicators-us.md)
   - Key series: GDP growth, CPI YoY, Core PCE, Fed Funds Rate, Unemployment Rate, 10Y Treasury, 2Y Treasury, 10Y-2Y Spread, ISM Manufacturing PMI, ISM Services PMI, Nonfarm Payrolls, Initial Jobless Claims, Consumer Confidence, Retail Sales, Housing Starts, Industrial Production
   - For each indicator, fetch the latest value AND the previous period value to calculate change

3. **Pull Taiwan indicators** (if in scope):
   - Use TWSE MCP for: TAIEX index level, daily trading volume, foreign investor net buy/sell, margin trading balance
   - Use Yahoo Finance MCP for: ^TWII (加權指數), TWD=X (台幣匯率)
   - Reference [references/indicators-tw.md](references/indicators-tw.md) for full list

4. **Pull Global indicators** (if in scope):
   - Use Yahoo Finance MCP for major indices: ^GSPC (S&P 500), ^DJI (Dow), ^IXIC (Nasdaq), ^FTSE, ^N225, ^HSI, ^GDAXI
   - Use Yahoo Finance MCP for commodities: GC=F (Gold), CL=F (WTI Oil), SI=F (Silver)
   - Use Yahoo Finance MCP for currencies: DX-Y.NYB (DXY), EURUSD=X, USDJPY=X, USDCNY=X
   - Use World Bank MCP for latest available development indicators
   - Reference [references/indicators-global.md](references/indicators-global.md) for full list

5. **Format output** as structured tables:
   - Group by region (US / TW / Global)
   - Columns: Indicator | Latest Value | Previous Value | Change | Trend (↑/↓/→)
   - Add interpretation notes for significant moves (>1 std dev from recent average)
   - Use 中英混合 format: indicator names in English, interpretations in Traditional Chinese

6. **Store in SQLite**:
   - Use SQLite MCP to insert snapshot into `macro_snapshots` table
   - Schema defined in [references/sqlite-schema.md](references/sqlite-schema.md)
   - Include timestamp, region, indicator_name, value, previous_value, change_pct

7. **Summary section**:
   - Provide a 3-5 sentence overview in Traditional Chinese highlighting the most notable data points
   - Flag any indicators that are at extreme levels or showing significant trend changes

## Output Format
```
## 總經數據快照 — {date}

### 🇺🇸 美國 (US)
| Indicator | Latest | Previous | Change | Trend |
|-----------|--------|----------|--------|-------|
| ... | ... | ... | ... | ... |

### 🇹🇼 台灣 (TW)
| Indicator | Latest | Previous | Change | Trend |
|-----------|--------|----------|--------|-------|
| ... | ... | ... | ... | ... |

### 🌍 全球 (Global)
| Indicator | Latest | Previous | Change | Trend |
|-----------|--------|----------|--------|-------|
| ... | ... | ... | ... | ... |

### 📊 重點摘要
{3-5 sentences in Traditional Chinese}

### ⚠️ 警示指標
{Any indicators at extreme levels}
```

## Additional Resources
- For complete US indicator definitions, see [references/indicators-us.md](references/indicators-us.md)
- For complete TW indicator definitions, see [references/indicators-tw.md](references/indicators-tw.md)
- For complete Global indicator definitions, see [references/indicators-global.md](references/indicators-global.md)
- For SQLite table schema, see [references/sqlite-schema.md](references/sqlite-schema.md)
