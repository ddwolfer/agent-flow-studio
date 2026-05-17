# SQLite Database Schema — Financial Analysis System

Database path: `/mnt/c/FINANCIAL/data/financial.db`

## Tables

### macro_snapshots
Stores periodic macroeconomic indicator values from /data-snapshot.

```sql
CREATE TABLE IF NOT EXISTS macro_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    region TEXT NOT NULL CHECK (region IN ('US', 'TW', 'Global')),
    indicator_name TEXT NOT NULL,
    indicator_series TEXT,          -- FRED series ID or Yahoo ticker
    value REAL,
    previous_value REAL,
    change_pct REAL,
    unit TEXT,
    source TEXT NOT NULL,           -- 'fred', 'yahoo-finance', 'twse', 'world-bank'
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_snapshots_date ON macro_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_snapshots_indicator ON macro_snapshots(indicator_name);
CREATE INDEX IF NOT EXISTS idx_snapshots_region ON macro_snapshots(region);
```

### market_scans
Stores market scan results from /market-scan.

```sql
CREATE TABLE IF NOT EXISTS market_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    scope TEXT,                     -- 'indices', 'sectors', 'flows', 'movers', 'all'
    indices_data TEXT,              -- JSON: {index_name: {level, daily_chg, weekly_chg, monthly_chg, ytd_chg}}
    sectors_data TEXT,              -- JSON: {sector: {performance, volume_chg, foreign_flow}}
    flows_data TEXT,                -- JSON: {foreign: {amount, consecutive_days}, trust: {...}, dealer: {...}}
    movers_data TEXT,               -- JSON: [{stock, code, change_pct, volume_ratio, event}]
    commodities_data TEXT,          -- JSON: {commodity: {price, change_pct}}
    currencies_data TEXT,           -- JSON: {pair: {rate, change_pct}}
    summary TEXT                    -- 中文市場摘要
);

CREATE INDEX IF NOT EXISTS idx_scans_date ON market_scans(timestamp);
```

### yt_summaries
Stores YouTube video analysis results from /yt-briefing.

```sql
CREATE TABLE IF NOT EXISTS yt_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    channel TEXT NOT NULL,          -- 'yutinghaofinance' or 'm168'
    channel_name TEXT,              -- Display name
    video_id TEXT NOT NULL,
    video_title TEXT,
    video_date TEXT,
    video_duration TEXT,
    video_views INTEGER,
    core_thesis TEXT,               -- 核心論述 (1-3 sentences)
    data_references TEXT,           -- JSON: [{indicator, cited_value, source, actual_value, discrepancy}]
    market_views TEXT,              -- JSON: {stance, target, timeframe, key_levels, risks}
    key_points TEXT,                -- JSON: [point1, point2, ...]
    full_summary TEXT,              -- Complete structured summary
    stance_vs_previous TEXT,        -- How stance changed from last video
    UNIQUE(video_id)
);

CREATE INDEX IF NOT EXISTS idx_yt_channel ON yt_summaries(channel);
CREATE INDEX IF NOT EXISTS idx_yt_date ON yt_summaries(video_date);
```

### macro_analyses
Stores multi-perspective analysis results from /macro-analysis.

```sql
CREATE TABLE IF NOT EXISTS macro_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    topic TEXT NOT NULL,
    perspective_central_bank TEXT,   -- 央行視角分析
    perspective_market TEXT,         -- 市場視角分析
    perspective_industry TEXT,       -- 產業視角分析
    perspective_historical TEXT,     -- 歷史視角分析
    convergence_points TEXT,         -- JSON: 四方共識
    divergence_points TEXT,          -- JSON: 分歧之處
    base_case TEXT,                  -- 基本情境
    base_case_probability REAL,
    bull_case TEXT,                  -- 樂觀情境
    bull_case_probability REAL,
    bear_case TEXT,                  -- 悲觀情境
    bear_case_probability REAL,
    key_monitors TEXT,               -- JSON: [{indicator, threshold, scenario_trigger}]
    confidence_level TEXT,           -- 'High', 'Medium', 'Low'
    conclusion TEXT,                 -- 結論
    charts_generated TEXT            -- JSON: [file_paths]
);

CREATE INDEX IF NOT EXISTS idx_analyses_topic ON macro_analyses(topic);
CREATE INDEX IF NOT EXISTS idx_analyses_date ON macro_analyses(timestamp);
```

### deep_research
Stores deep research results from /deep-research.

```sql
CREATE TABLE IF NOT EXISTS deep_research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    topic TEXT NOT NULL,
    sub_questions TEXT,              -- JSON: [{question, answer, confidence, sources}]
    key_findings TEXT,               -- JSON: [{finding, confidence, sources}]
    data_evidence TEXT,              -- JSON: [{data_point, value, source, tier, date}]
    supporting_arguments TEXT,       -- JSON: [{argument, evidence}]
    counter_arguments TEXT,          -- JSON: [{argument, evidence}]
    unresolved_questions TEXT,       -- JSON: [question1, question2, ...]
    data_quality_score REAL,
    convergence_score REAL,
    completeness_score REAL,
    overall_confidence REAL,
    confidence_label TEXT,           -- 'High', 'Medium', 'Low', 'Speculative'
    conclusion TEXT,
    sources TEXT                     -- JSON: [{source, tier, url}]
);

CREATE INDEX IF NOT EXISTS idx_research_topic ON deep_research(topic);
CREATE INDEX IF NOT EXISTS idx_research_date ON deep_research(timestamp);
```

### cross_checks
Stores claim verification results from /cross-check.

```sql
CREATE TABLE IF NOT EXISTS cross_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    claim TEXT NOT NULL,
    core_assertion TEXT,
    implied_causality TEXT,
    implied_prediction TEXT,
    hidden_assumptions TEXT,
    fallacies_identified TEXT,       -- JSON: [{type, present, explanation}]
    historical_backtest TEXT,        -- JSON: {total_cases, supporting_cases, base_rate}
    multi_source_verification TEXT,  -- JSON: [{source, supports, data}]
    counter_examples TEXT,           -- JSON: [{date, description}]
    verdict TEXT,                    -- 'Supported', 'Partially Supported', 'Not Supported', 'Misleading', 'Insufficient Data'
    confidence TEXT,                 -- 'High', 'Medium', 'Low'
    base_rate REAL,
    nuanced_statement TEXT,          -- More accurate version of the claim
    evidence_summary TEXT
);

CREATE INDEX IF NOT EXISTS idx_checks_date ON cross_checks(timestamp);
```

### web_research
Stores scraped government/institutional data from /web-research.

```sql
CREATE TABLE IF NOT EXISTS web_research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    source TEXT NOT NULL,            -- 'cbc', 'dgbas', 'fsc', 'fed', 'ecb', 'custom'
    url TEXT,
    topic TEXT,
    publication_date TEXT,
    extracted_data TEXT,             -- JSON: structured data
    raw_text TEXT,                   -- Raw extracted text
    summary TEXT,                    -- Chinese summary
    quality_notes TEXT               -- Any extraction issues
);

CREATE INDEX IF NOT EXISTS idx_webresearch_source ON web_research(source);
CREATE INDEX IF NOT EXISTS idx_webresearch_date ON web_research(timestamp);
```

## Notes
- All timestamps are in ISO 8601 format (UTC)
- JSON fields use TEXT type with JSON content for flexibility
- Tables are created automatically on first use by each skill
- Use `CREATE TABLE IF NOT EXISTS` to ensure idempotent creation
