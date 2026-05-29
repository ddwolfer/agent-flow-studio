# Serenity Digest — analytical framework

You are reading `analysissite.vercel.app`, a US-stock KOL aggregator. The site
exposes:

- **priorityQueue (top 3)**: KOL's most actively-flagged tickers today, each
  with a priority number (higher = stronger flag), a stance label, a 1-2
  sentence reasoning summary, and tags.
- **hotStocks (top 10)**: full priority queue.
- **feedItems (10-20 latest)**: timeline of AI/news/discussion items, each
  linked to a ticker, with a badge (e.g. "GPT xhigh", "看多") and a timestamp.
- **metrics**: activeSignals, coverage, delta24h/7d/30d, newsDriven.
- **distribution**: 5-category headcount (觀察, 積極觀察, 高風險觀察,
  謹慎, 高風險偏多).

## Stance vocabulary

The site uses a Chinese stance taxonomy. Map to canonical labels for KG storage:

| Site phrase | Canonical stance |
|---|---|
| 看多 + 高風險偏多 | `bull_high_risk` |
| 中性 + 高風險觀察 | `watch_high_risk` |
| 看多 | `bull` |
| 看空 | `bear` |
| 謹慎 | `caution` |
| 中性 | `neutral` |

Use these in `metadata.stance` when calling `store_knowledge`.

## Tier rule (adaptive)

Decide today's Tier 1 size (3-5 tickers) by the cluster-cutoff rule:

```
top_priority   = priorityQueue[0].priority
cutoff         = top_priority * 0.95
tier1_count    = count(stocks where priority >= cutoff, capped at 5)
tier1_count    = max(tier1_count, 3)
```

If `priorityQueue` is empty (parsing failure), fall back to `hotStocks[:3]`.

Tier 2 = `hotStocks[tier1_count : tier1_count + 8]` (8 entries, short-form).

Tier 3 = diff vs yesterday (computed in Step 2 of main.md).

## News importance score (0-100)

For each feedItem score on five dimensions:

| Dimension | Max | Rule |
|---|---:|---|
| 標的優先級對應度 | 30 | ticker ∈ today's hotStocks → score = 30 - 2×(rank-1). Not in top 10 → 0. |
| 新聞具體性 | 25 | Contains 數字/百分比/公司名/具體事件/日期 → +5 each, cap 25. |
| 來源權威性 | 15 | Reuters/Bloomberg/CNBC/官方公告/SEC → 15; 一般媒體 → 8; 推文/未署名 → 3. |
| 時效性 | 15 | ≤24h → 15; ≤72h → 8; >72h → 0. |
| 與 KG 關係 | 15 | aligns_to / refines an existing KG node for that ticker → 15. contradicts → 15 AND mark with ⚠️ in 相關訊號 段. Unknown → 5. |

Pick **top 3** for the 相關訊號 section. If any scored item has the
`contradicts` flag, it is forced into the top 3 regardless of rank.

## KG mapping

The Serenity Digest writes knowledge for two purposes:

1. **Record what the KOL said today** — `trust: principle`, `quote` required.
2. **Record Claude's own extrapolation** — `trust: inference`, NEVER claim it's
   the KOL's view.

Edge usage:

- Today's principle ↔ yesterday's principle (same ticker, stance unchanged, priority ↑): `refines`
- Today's principle ↔ yesterday's principle (same ticker, stance reversed): `contradicts`
- Claude inference → an existing principle node it elaborates: `aligns_to`
- Claude inference → an existing principle node it pushes back on: `contradicts`

**Forbidden** (the KG MCP will reject):
- `must_precede` or `reason_for` edges involving any `trust: inference` node.
- `store_knowledge` with `trust: principle` but no `quote`.

If you can't extract a clean ≤50-character verbatim quote for a KOL view,
downgrade `trust` to `pattern` (no quote needed; means you observed it from
the site as a pattern, but not literally).

## Daily caps

- ≤ 20 `store_knowledge` calls across the whole workflow run.
- ≤ 30 `connect_knowledge` calls.

Allocate budget like this:
- 5 principle nodes (priorityQueue top 5) — highest priority
- 5-10 edges connecting today's nodes to yesterday's (refines/contradicts)
- 3 inference nodes (your top 3 extrapolations)
- 3-5 edges from inferences to existing principles (aligns_to / contradicts)
- Reserve the rest for unexpected high-value writes.
