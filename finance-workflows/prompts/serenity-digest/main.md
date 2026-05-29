# Serenity Digest — orchestration

You are producing today's Serenity Digest. Today is ${DATE} (Asia/Taipei).
Workflow name: ${WORKFLOW_NAME}.

## Output paths (absolute)

- HTML archive: `${OUTPUT_PATH}`
- Telegram brief: same directory, filename `_brief.md`
- History line:  same directory, filename `_history.jsonl` (append, one line)

You can derive the directory in your head: it's `${OUTPUT_PATH}` without the
`<date>.html` tail. Use the Write tool with the full absolute path.

## Step 1 — Fetch and parse the site

Call `mcp__web-fetch__web_fetch` on `https://analysissite.vercel.app/`.

Extract the following structures from the rendered HTML. The site uses
Simplified Chinese internally; convert to Traditional Chinese for your output
where applicable.

- `priorityQueue` (top 3): array of `{ rank, ticker, priority, stance, summary, tags, updatedAt }`.
- `hotStocks` (top 10): same shape.
- `feedItems` (latest 10-20): array of `{ id, ticker, kind, title, body, badges, publishedAt }`.
- `metrics`: `{ activeSignals, coverage, delta24h, delta7d, delta30d, newsDriven }`.
- `distribution`: dict of the 5 category headcounts.

If the fetched body has < 1000 Chinese characters, treat it as a parsing
failure: continue with empty arrays and set a `[STATUS] 抓取異常` banner in
the brief. Do NOT retry the fetch yourself; the runner's retry layer covers
transient claude-level failures separately.

Map the KOL's Chinese stance labels to canonical English labels per
`framework.md`'s stance vocabulary table.

## Step 2 — Diff vs yesterday

The directory containing `${OUTPUT_PATH}` should hold a `_history.jsonl` file
from prior runs. Use the Read tool on it.

Parse each line as JSON. Find the most recent entry whose `date` is
strictly less than ${DATE}. If none exists (first run):

- Set `newInTop10 = []`, `droppedFromTop10 = []`, `priorityMovers = []`
- Mark "首次運行,無昨日對照" in the brief's Tier 3 section.

Otherwise compute:

```
today_tickers   = { s.ticker for s in today.hotStocks }
yest_tickers    = { s.ticker for s in yesterday.hotStocks }
newInTop10      = sorted(today_tickers - yest_tickers)
droppedFromTop10= sorted(yest_tickers - today_tickers)

common = today_tickers ∩ yest_tickers
movers = [(t, today.priority[t] - yesterday.priority[t]) for t in common]
priorityMovers = top 3 by |delta|, excluding delta == 0
```

## Step 3 — KG retrieval (priorityQueue top 3 only)

For each of today's `priorityQueue[0..2].ticker`, call:

```
mcp__knowledge-graph__search_memory({
  query: "{ticker} 觀點演化 stance",
  mode: "hybrid",
  limit: 5,
  compact: false
})
```

Stash the results per ticker. If a search returns 0 hits (no results found),
that ticker has no KG context yet — that's expected on day 1.

If a search errors, log the error to your scratchpad but continue — KG
retrieval is best-effort. The brief simply won't have a "KOL 對照" entry for
that ticker.

## Step 4 — Score and select feedItems

Score every feedItem 0-100 using the five-dimension rule in `framework.md`.
Select the top 3 by score. If any item has the `contradicts` flag (its
content materially conflicts with an existing KG principle for the same
ticker), force-include it and mark with ⚠️.

## Step 5 — Write the HTML archive

Use the Write tool to write `${OUTPUT_PATH}`. Make it a comprehensive,
nicely-styled HTML page with these sections in order:

1. `<header>`: title `Serenity Digest — ${DATE}`, fetched-at timestamp, source link.
2. **Metrics summary** (6 numbers).
3. **Priority queue** (3 entries, full detail).
4. **Hot stocks** (10 entries, table form).
5. **Distribution** (5-category bar).
6. **Diff vs yesterday** (new/dropped/movers).
7. **KG context** (per-ticker for top 3, if any results).
8. **Selected news** (top 3 scored feedItems with score breakdown).
9. **Footer**: attribution to `analysissite.vercel.app`, Persona stage
   (`Phase 1 樸素模式`), KG node count from
   `mcp__knowledge-graph__memory_stats` if cheap, run timestamp.

Use light inline CSS for readability; this file is the durable archive a
human will read on their laptop later.

## Step 6 — Write `_brief.md` (Telegram body)

Use the Write tool. The file's raw Markdown becomes the Telegram message
verbatim — keep it under 3900 chars.

Use this exact skeleton (substitute your data; omit sections per the
omission rules):

```
📊 *${DATE} Serenity 日報* (HH:MM 台北)

▎*今日優先*
1. *{TICKER}* · 優先級 {p} · {stance 中文}
   {KOL reasoning summary, 1 sentence}
   需驗證:{2-3 個 validation points 用、分隔}
   _{optional KG context line}_

(repeat for tier1_count entries, 3-5 total)

▎*掃描清單*
{N}. *{TICKER}* {p} {stance 簡寫}
(8 entries)

▎*昨日變化*
🆕 進榜:...
👋 退榜:...
📈 漲幅最大:...
📉 跌幅最大:...

▎*KOL 對照*
• *{TICKER}*: {1-2 sentence context from KG}
(0-2 entries; omit section entirely if KG returned nothing)

▎*相關訊號*
• ⚠️ *{TICKER}* · {source}: {title}
  _{optional alignment note with KG}_
(top 3 scored items; ⚠️ only on contradicts items)

─────────
📍 分析框架蒸餾自 [analysissite.vercel.app](https://analysissite.vercel.app/)
🧠 Phase 1 樸素模式 · KG {N} nodes
🔗 完整看板:https://analysissite.vercel.app/
```

Omission rules:
- No yesterday: replace `▎*昨日變化*` body with `(首次運行,無昨日對照)`.
- KG retrieval returned nothing for any ticker: omit the `▎*KOL 對照*`
  section entirely (do not write the heading at all).
- feedItems empty: omit `▎*相關訊號*`.
- Site parsing failed (Step 1): insert `⚠️ [STATUS] 今日抓取異常,內容可能
  不完整。` as the second line after the title.

**Before you finalise the file, scan it once for the banned phrases from
`voice.md`. If any are present, rewrite the offending line.**

## Step 7 — KG write

You have a hard budget: ≤ 20 `store_knowledge` calls, ≤ 30
`connect_knowledge` calls for this entire run. Spend them in this order:

### 7a — KOL principle nodes (priorityQueue top 5)

For each ticker in `priorityQueue[0..4]` (or `hotStocks[0..4]` if
priorityQueue is short):

```
mcp__knowledge-graph__store_knowledge({
  type: "insight",
  trust: "principle",
  name: "{TICKER} ${DATE} {stance}",
  content: "{KOL reasoning, 1-2 sentences, Traditional Chinese}",
  quote: "{20-50 character VERBATIM excerpt from the KOL's text on the site}",
  source: "serenity-digest",
  metadata: {
    workflow: "serenity-digest",
    site: "analysissite",
    ticker: "{TICKER}",
    stance: "{canonical stance, e.g. bull_high_risk}",
    category: "creative",
    first_seen: "${DATE}",
    confidence: 0.8
  }
})
```

If you cannot find a clean ≤50-character verbatim quote, downgrade `trust`
to `"pattern"` and drop the `quote` field. Never fabricate a quote.

Save the returned `id` per ticker for the edge-creation step.

### 7b — Edges to yesterday's nodes

For each ticker that's in BOTH `today.priorityMovers` and yesterday's
recorded principle nodes:

First, find yesterday's node id. If you don't have it cached from
`_history.jsonl`, call:

```
mcp__knowledge-graph__list_knowledge({
  filter: {"source": "serenity-digest"},
  sort_by: "created_at",
  limit: 20
})
```

and find the most recent matching ticker.

Then connect:

- Stance unchanged + delta > 0 → `relation_type: "refines"`
- Stance reversed              → `relation_type: "contradicts"`
- Otherwise                    → skip

```
mcp__knowledge-graph__connect_knowledge({
  source_id: "{today's node id}",
  target_id: "{yesterday's node id}",
  relation_type: "refines" | "contradicts",
  reasoning: "{1 sentence explaining the change}",
  weight: 0.8,
  source_session: "${WORKFLOW_NAME}-${DATE}"
})
```

### 7c — Claude inference nodes (top 3 only)

Pick the 3 priorityQueue tickers where your own analysis goes beyond what
the KOL said today. For each:

```
mcp__knowledge-graph__store_knowledge({
  type: "insight",
  trust: "inference",
  name: "{TICKER} ${DATE} extrapolation",
  content: "{Your extension of the KOL's view, Traditional Chinese, 1-2 sentences}",
  source: "serenity-digest",
  metadata: {
    workflow: "serenity-digest",
    site: "analysissite",
    ticker: "{TICKER}",
    ai_extrapolated: true,
    first_seen: "${DATE}",
    confidence: 0.6
  }
})
```

NO `quote` field — `inference` is your view, not the KOL's.

Then optionally connect to the corresponding `principle` node from Step 7a:

```
mcp__knowledge-graph__connect_knowledge({
  source_id: "{inference id}",
  target_id: "{principle id}",
  relation_type: "aligns_to",   # or "contradicts" if you're pushing back
  reasoning: "{why}",
  weight: 0.7,
  source_session: "${WORKFLOW_NAME}-${DATE}"
})
```

DO NOT use `must_precede` or `reason_for` with an inference node — the KG
server will reject the call.

### 7d — Failure handling

If any KG call returns an error, log it to your scratchpad and continue. Skip
the failing call's downstream edges. Do not fail the workflow over KG issues.

If you exceed the daily caps, stop writing and continue to Step 8.

## Step 8 — Append the history line

Use the Read+Write tool combination (read existing content, append one line,
write back) on `<output_dir>/_history.jsonl`. Append a single JSON line:

```json
{
  "date": "${DATE}",
  "fetchedAt": "{ISO timestamp}",
  "metrics": {...},
  "topTickers": ["NVDA", "TSM", ...],
  "stances": {"NVDA": "bull_high_risk", "TSM": "bull", ...},
  "priorities": {"NVDA": 432, "TSM": 311, ...},
  "newInTop10": [...],
  "droppedFromTop10": [...],
  "priorityMovers": [{"ticker": "NVDA", "delta": 5}, ...],
  "writes": {"principles": N, "inferences": M, "edges": K},
  "kg_node_ids": {"NVDA": "uuid", "TSM": "uuid", ...},
  "status": "ok" | "partial" | "failed"
}
```

This is what tomorrow's Step 2 will read for the diff.

## Step 9 — Done

Print one line to stdout summarising the run, e.g.:
```
serenity-digest done: 10 tickers, 4 KG principle nodes, 2 inferences, 5 edges, brief 2347 chars
```

That's it. Do not write anything else outside the paths specified.
