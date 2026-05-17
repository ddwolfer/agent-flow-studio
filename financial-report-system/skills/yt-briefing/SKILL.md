---
name: yt-briefing
description: "Extract, analyze, and summarize financial YouTube videos from tracked channels. Use when: user wants YouTube video summaries, channel updates, transcript analysis, '最新影片', '游庭皓', '張貽程', '外資超錢線', '財經皓角', video briefing, or wants to know what financial YouTubers are saying. Uses yt-dlp for video search + YouTube Transcript for caption extraction + structured analysis framework."
argument-hint: [channel: yutinghao | m168 | all] [count: number of videos, default 1]
effort: high
user-invocable: true
---

# YT Briefing — 財經 YouTube 頻道追蹤摘要

Extract transcripts from tracked financial YouTube channels, apply structured analysis frameworks to produce investment-grade summaries with data verification and bias detection.

## Reference Files

| File | Purpose |
|------|---------|
| [channels.md](references/channels.md) | Channel details, content patterns, common data points referenced |
| [extraction-framework.md](references/extraction-framework.md) | Transcript analysis methodology, data extraction, bias detection |
| [summary-template.md](references/summary-template.md) | Output templates for single and multi-channel summaries |
| [thinking-frameworks.md](references/thinking-frameworks.md) | SCQA, critical thinking, inversion frameworks for content analysis |

---

## Tracked Channels

| Handle | Name | Style | Focus |
|--------|------|-------|-------|
| `@yutinghaofinance` | 游庭皓的財經皓角 | 總經由上而下，數據導向 | GDP, CPI, Fed, 央行, 出口 |
| `@m168` | 張貽程（摩爾證券投顧·外資超錢線） | 籌碼由下而上，技術分析 | 外資動態, 法人籌碼, 個股 |

See [channels.md](references/channels.md) for full profiles.

---

## Workflow

### Phase 1: Video Discovery

1. Use **yt-dlp MCP** to search each target channel for recent uploads:
   - `@yutinghaofinance` → Get latest `$ARGUMENTS[1]` videos (default 1)
   - `@m168` → Get latest `$ARGUMENTS[1]` videos (default 1)
   - If `$ARGUMENTS[0]` specifies one channel, only search that channel

2. For each video, retrieve:
   - Video URL, title, upload date, duration, view count
   - Thumbnail URL (for visual reference)

### Phase 2: Transcript Extraction

1. Use **YouTube Transcript MCP** for each video:
   - Request language: `zh-TW` first → fallback `zh-Hant` → `zh` → auto-generated
   - Enable ad/sponsorship filtering
   - If transcript unavailable, note this limitation

2. **Semantic chapter detection** (adapted from Youtube-clipper-skill):
   - Read full transcript, identify natural topic transitions
   - Segment into 2-5 minute chapters based on semantic shifts (not fixed time)
   - For each chapter: title (10-20 chars), time range, core summary (50-100 chars), keywords (3-5)
   - Ensure ALL video content is covered with no gaps
   - This provides structured navigation for the analysis phases below

3. **Transcript cleanup** (see [extraction-framework.md](references/extraction-framework.md)):
   - Remove filler words (嗯、啊、那個、就是說)
   - Fix common auto-caption errors:
     - 飛農 → 非農, 聯準 → 聯準會, numbers may be garbled
   - Identify section boundaries: 開場 → 數據回顧 → 分析 → 市場影響 → 建議 → 結尾

### Phase 3: Content Analysis

Apply the 8-part analysis framework from [extraction-framework.md](references/extraction-framework.md):

#### 3A. Core Thesis Extraction (核心論述)
- **One-sentence summary**: Central message
- **Key premise**: What assumption underlies the argument
- **Logical chain**: A → B → C → Conclusion
- **Confidence expressed**: Certainty vs hedging language

#### 3B. Data Reference Extraction (數據引用)
For every number mentioned, create structured record:

| Indicator | Cited Value | Period | Source | Verifiable? |
|-----------|------------|--------|--------|-------------|

**Quality flags**:
- ⚠️ Outdated: Data >2 months old without noting
- ⚠️ Selective: Cherry-picked time period
- ⚠️ Misattributed: Wrong source
- ✅ Accurate: Matches verifiable source
- ℹ️ Unverifiable: Cannot check with available tools

#### 3C. Market View Extraction (市場觀點)

| Stance | Definition |
|--------|-----------|
| Strong Bullish | 明確看多，建議加碼 |
| Mild Bullish | 偏多但有保留 |
| Neutral | 不看多不看空，觀望 |
| Mild Bearish | 偏空，建議減碼 |
| Strong Bearish | 明確看空，建議出場 |

For each view: target asset, direction, time horizon, key levels, catalyst, risk factor.

#### 3D. Management/Host Tone Assessment (語氣評估)
Adapted from earnings-call-analysis:

**Confidence indicators**: Definitive language, specific numbers, proactive discussion
**Caution indicators**: Hedging ("可能", "也許"), wide ranges, deflection
**Red flags**: Evasive, blame-shifting, reduced detail vs prior videos

#### 3E. Key Themes (主題分類)
Categorize into:
- 總經趨勢 (Macro trends)
- 政策解讀 (Policy interpretation)
- 產業分析 (Sector analysis)
- 個股觀點 (Stock-specific views)
- 風險警示 (Risk warnings)
- 投資建議 (Investment recommendations)

#### 3F. Prediction Tracking (預測追蹤)
For any forward-looking statement:
- What was predicted (specific, falsifiable)
- When (target date/condition)
- Confidence expressed
- Status: Pending / Confirmed / Denied / Expired

Check SQLite `yt_summaries` for prior predictions from same host → evaluate accuracy.

#### 3G. Bias & Quality Check (偏誤檢查)
Check for (from deep-reading-analyst/critical_thinking + inversion_thinking):
- Confirmation bias (只看支持觀點的數據)
- Recency bias (過度依賴近期事件)
- Anchoring (stuck on previous prediction)
- Narrative fallacy (故事比數據有說服力)
- Authority bias ("巴菲特說..." without context check)
- Survivorship bias (只看成功案例)
- Home bias (過度強調台灣市場影響)

Quality rating: ★★★★★ (data-rich, balanced) to ★ (speculation, no data)

#### 3H. Cross-Reference with Live Data (數據交叉驗證)
Optional but recommended:
- If specific indicators mentioned → verify via FRED/Yahoo Finance/TWSE MCP
- Note discrepancies between cited data and actual current values
- Add "actual value" column to data reference table

### Phase 4: Store in SQLite

Use SQLite MCP → `yt_summaries` table:
```
timestamp, channel, channel_name, video_id, video_title, video_date,
video_duration, video_views, core_thesis, data_references (JSON),
market_views (JSON), key_points (JSON), full_summary, stance_vs_previous
```

### Phase 5: Output

Follow [summary-template.md](references/summary-template.md).

**Per-video output includes:**
1. Video metadata (title, date, duration, URL)
2. Core thesis (1-3 sentences)
3. Data reference table (with verification column)
4. Market views table (stance, target, horizon)
5. Key points (5-10 bullet points)
6. Prediction tracking table
7. Stance comparison vs previous videos
8. Bias check results
9. Quality rating

**Multi-channel comparative output (when processing both channels):**
1. Cross-channel opinion matrix
2. Consensus points (where both agree)
3. Divergence points (where they disagree — THIS is the insight)
4. Synthesized reading combining macro (游庭皓) + market structure (張貽程)

---

## Integration with Other Skills

| Downstream Skill | How |
|-----------------|-----|
| `/cross-check` | Verify specific claims from YT against data |
| `/macro-analysis` | YT summaries as qualitative input (Tier 4 source) |
| `/generate-report` | Export briefing as HTML/PDF |
| `/data-query` | Query historical YT summaries for trend tracking |

---

## Quality Checklist
- [ ] Transcript extracted successfully (language correct, ads filtered)
- [ ] All data references extracted with source attribution
- [ ] Market views classified with stance/horizon/target
- [ ] Bias check performed (at least 3 bias types evaluated)
- [ ] Prior predictions checked against SQLite history
- [ ] Stored in SQLite with all fields populated
- [ ] Output follows template structure
