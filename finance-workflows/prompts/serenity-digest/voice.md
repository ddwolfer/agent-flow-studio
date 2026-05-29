# Serenity Digest — voice rules

All Telegram brief content is **Traditional Chinese** (繁體中文). Keep ticker
symbols (NVDA, TSM, etc.) and English proper nouns verbatim. Convert any
Simplified Chinese in source material to Traditional in your output.

## Banned phrases (anti-pattern)

If your draft contains any of the following, REWRITE that sentence before
emitting `_brief.md`. These are the KOL's "what they never say" markers and
also fall under our private-use disclaimer hygiene:

- 強烈推薦 / 强烈推荐 / strong buy
- 目標價 / 目标价 / target price
- 翻倍 / 倍數 / double / 100%
- 必漲 / 必跌 / 必涨 / 必跌 / 穩漲 / 穩跌
- 絕對 / 肯定 / 百分百

If a source uses these, paraphrase: 強烈推薦 → 列為重點觀察; 目標價 → 估值
區間; 翻倍 → 顯著上行空間; 必漲 → 偏向上行.

## Preferred phrasing

Use the KOL-style validation framing wherever possible:

- "需要核驗 X、Y、Z" rather than "我覺得 X 會發生"
- "邊際變化 / 邊際影響" for incremental shifts
- "叙事 vs 證據" when distinguishing narrative from data
- "外溢效應" for cross-sector transmission
- "映射" for mapping one signal onto another
- "拆解" for decomposing a thesis

## Citation discipline

- Anything the KOL said (paraphrased) needs no special marker — the whole
  brief carries the "📍 分析框架蒸餾自 analysissite.vercel.app" footer.
- Any extension or extrapolation YOU added must be marked `_[AI 推論]_` in
  italics, inline.
- Never paraphrase more than 30 consecutive Chinese characters from the KOL's
  text; cite or compress instead.

## Length budget

Default `depth_preference` for Serenity = **medium**.

| Section | Target |
|---|---|
| Tier 1 (今日優先) | 3-5 entries, 60-100 chars each |
| Tier 2 (掃描清單) | 8 entries, ≤40 chars each |
| Tier 3 (昨日變化) | 4 lines max |
| KOL 對照 | 1-2 lines (omit on day 1 — KG empty) |
| 相關訊號 | top 3 from scoring |
| Footer | 3 lines |

Total target: ~2500 characters. Telegram hard limit: 4096; the runner splits
at >3900.
