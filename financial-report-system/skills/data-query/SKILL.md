---
name: data-query
description: Use when the user wants to query historical data stored in SQLite, look up past analyses, compare current vs historical indicators, or track trends over time. Triggers on phrases like 'query data', 'historical', '歷史數據', '查詢', '趨勢', 'compare with', 'trend', 'look up past'.
argument-hint: [query description or indicator name] [timeframe]
allowed-tools: Bash, Read, Glob, Grep, Agent
effort: high
user-invocable: true
---

# Data Query — 歷史數據查詢

## Purpose
Query the local SQLite database for previously stored macroeconomic snapshots, market scans, YouTube briefing summaries, research results, and cross-check verdicts. Enable trend analysis and historical comparison.

## Input
- `$ARGUMENTS[0]` = What to query (indicator name, topic, channel, or "all")
- `$ARGUMENTS[1]` = Timeframe (e.g., "1w", "1m", "3m", "6m", "1y", "ytd", or date range "2024-01-01:2024-06-30")

## SQLite Database Schema
See [references/sqlite-schema.md](references/sqlite-schema.md) for complete schema. Tables:

| Table | Content | Written By |
|-------|---------|------------|
| `macro_snapshots` | Economic indicator values over time | /data-snapshot |
| `market_scans` | Market conditions, sector data, fund flows | /market-scan |
| `yt_summaries` | YouTube video summaries and extracted views | /yt-briefing |
| `macro_analyses` | Multi-perspective analysis results | /macro-analysis |
| `deep_research` | Deep research reports | /deep-research |
| `cross_checks` | Claim verification results | /cross-check |
| `web_research` | Scraped government website data | /web-research |

## Process

1. **Parse the query intent**:
   - Determine which table(s) to query
   - Parse timeframe into date range
   - Identify specific indicators, channels, or topics

2. **Execute SQLite queries**:
   - Use SQLite MCP to run appropriate SELECT statements
   - For indicator trends: query `macro_snapshots` with time filter
   - For market history: query `market_scans` with time filter
   - For YT history: query `yt_summaries` filtered by channel/topic
   - For past analyses: query `macro_analyses` or `deep_research` by topic
   - For verification history: query `cross_checks`

3. **Analyze results**:
   - Calculate trend (direction, magnitude, acceleration)
   - Identify inflection points
   - Compare current values vs historical average, min, max
   - For YT data: track stance changes over time, prediction accuracy

4. **Generate visualizations**:
   - Use Chart MCP for time series line charts
   - Use Chart MCP for comparison bar charts
   - Use Chart MCP for heatmaps if comparing multiple indicators

5. **Present results** with context

## Output Format
```
## 📂 歷史數據查詢

### 查詢條件
- **標的**: {indicator/topic}
- **時間範圍**: {start_date} — {end_date}
- **資料筆數**: {count}

### 📊 數據
| 日期 | 數值 | 變動 | 備註 |
|------|------|------|------|
| ... | ... | ... | ... |

### 📈 趨勢分析
- **方向**: {Upward / Downward / Sideways}
- **幅度**: {magnitude}
- **加速度**: {accelerating / decelerating / stable}
- **目前 vs 平均**: {current} vs {average} ({deviation}%)
- **目前 vs 區間**: {min} — {current} — {max}

### 📉 圖表
{Time series chart}

### 📝 觀察
{Key observations in Traditional Chinese}
```

## Additional Resources
- For complete database schema, see [references/sqlite-schema.md](references/sqlite-schema.md)
