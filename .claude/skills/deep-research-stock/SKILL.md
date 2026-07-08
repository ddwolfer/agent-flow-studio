---
name: deep-research-stock
description: Use when the user invokes /deep-research-stock with a space- or comma-separated list of stock tickers (e.g. `/deep-research-stock NVDA TSLA IVV NOW LITE`). Runs the deep-stock-research analysis interactively in this Claude Code session — no `claude -p` subprocess, no `run-workflow.py`. The user-supplied ticker list overrides the workflow JSON's hardcoded watchlist. Output HTML goes to `finance-workflows/reports/deep-stock-research/<today>.html`. This is the post-2026-06-15 path for deep stock research to stay on the interactive subscription pool instead of the new credit pool.
---

# deep-research-stock

The user wants deep stock research on a custom watchlist they passed in `args`.

## Parse args

`args` is a string of tickers separated by spaces or commas (e.g. `NVDA TSLA IVV NOW LITE RDDT COIN`). Split it into an ordered list.

If `args` is empty or contains no valid ticker-looking token, ask the user:
> 「請給我今天要做深度研究的 tickers,用空白分隔。例如:NVDA TSLA IVV NOW」
and stop until they answer.

## Tier assignment

Order matters — the user is intentional about which tickers get the deepest treatment.

- **Tier A** = first 3 tickers in the list (full 7-layer analysis, includes SEC EDGAR 10-K reading)
- **Tier B** = 4th onward (compact 4-layer: §1 概覽 / §4 財務快照精簡 / §6 風險精簡 / §7 投資邏輯)
- **ETF override**: tickers like `SPY`, `QQQ`, `IVV`, `VOO`, `VTI`, `GLD`, `SLV`, `EFA`, `EEM`, `XL?`, `ARK?` etc. **skip EDGAR even if they land in Tier A position** (no 10-K filing). They keep the rest of the Tier A treatment (Yahoo metadata, macro overlay, 7-layer write-up) but with "資料來源:Yahoo ETF metadata + FRED 總經背景" framing.

State the tier assignment to the user at the start (e.g. "Tier A: NVDA / TSLA / IVV(ETF,跳過 EDGAR); Tier B: NOW / LITE / RDDT / COIN") so they can correct order if needed.

## Read the spec (binding)

Read these five files and treat them as the literal contract for the work:

1. `finance-workflows/prompts/shared/faithfulness.md` — anti-fabrication rules
2. `finance-workflows/prompts/stock-research/framework.md` — 7-layer structure + 分層策略
3. `finance-workflows/prompts/stock-research/voice.md` — tone
4. `finance-workflows/prompts/stock-research/main.md` — full task flow + HTML output spec
5. `docs/superpowers/specs/2026-07-08-price-zone-design.md` — SMC 結構 & 價格區間 §8 契約(v0.2.1;compute_zones.py 的規格與硬規則)

The prompts reference `${WORKFLOW_NAME}` / `${DATE}` / `${SOURCES_JSON}` / `${OUTPUT_PATH}` placeholders meant for the runner. Substitute mentally:

- `${WORKFLOW_NAME}` → `deep-stock-research`
- `${DATE}` → today's date in Asia/Taipei (`date +%Y-%m-%d`,or 你已知的「今天」)
- `${SOURCES_JSON}` → ignore; use the user-supplied ticker list from `args` instead
- `${OUTPUT_PATH}` → `finance-workflows/reports/deep-stock-research/<today>.html`

## Execute

### Stage 1 — Macro background (once)

Use `mcp__fred__fred_get_series` for: `DGS10`, `T10Y2Y`, `DFF`, `CPIAUCSL`. Record latest value + observation date. Keep them on hand — every ticker's §6 風險/總經連動 references them.

### Stage 2a — Price zones (all tickers, batch)

Before per-ticker LLM analysis, run the deterministic SMC zone computation
for **every** ticker in the list (Tier A / Tier B / ETF alike — the script
is cheap ~3s per ticker and cannot fail LLM budget):

```bash
finance-workflows/mcp/.venv/bin/python \
  finance-workflows/scripts/compute_zones.py <TICKER> \
  --out finance-workflows/reports/deep-stock-research/_zones/<today>/<TICKER>.json
```

Batch these via the Bash tool (independent commands — send in parallel). Then
read each resulting JSON. **These JSON files are the ONLY source of §8
numbers.** No zone / invalidation / basis price may appear in the report
that is not in the JSON.

Failure handling: if any ticker's script exits non-zero or writes an `"mode":
"error"` JSON, that ticker's §8 shows「技術數據不可用,本次跳過」and the
rest of the report proceeds unaffected.

### Stage 2 — Per-ticker analysis

Loop over the parsed ticker list in order.

**Tier A flow** (first 3, non-ETF):
1. `mcp__yahoo-finance__get_stock_info(ticker=...)` — snapshot
2. `mcp__edgar__edgar_latest_annual(ticker=...)` → `mcp__edgar__edgar_fetch_text(url=..., max_chars=60000, offset=0)` for Item 1. Business + Item 1A. Risk Factors. Continue-read with `offset=<end>` if needed.
3. Optional: `mcp__web-fetch__web_extract_article` for recent news only if a specific event (earnings, product launch, geopolitical) in past 7 days is worth quoting. Skip if no clear hit — never fabricate news.
4. Write framework §1-§7 fully.
5. Write **§8 SMC 結構視角下的價格區間**(完整版,150–250 字 + 表格):
   - 結構敘述:趨勢方向、最近 BOS/CHoCH、目前 premium/discount
   - 買入參考區 + basis + 流動性風險(若 `buy_zone_pending`,寫 CHoCH trigger price)
   - 賣出/減碼參考區 + basis
   - **失效條件**(獨立一行,加粗)
   - `mode == "degraded"`:改一行「上市未滿 60 個交易日,結構樣本不足,僅提供位置參考,不產出買賣區間」+ 位置百分位

**Tier A flow for ETF** (ETF lands in first 3):
1. `mcp__yahoo-finance__get_stock_info(ticker=...)` — ETF metadata (longBusinessSummary, totalAssets, yield, expenseRatio, navPrice)
2. **Skip EDGAR** — ETFs file N-1A/N-CSR, not 10-K. The prompt's EDGAR step doesn't apply.
3. Write framework §1-§7 from "ETF macro anchor" perspective: §2 = "tracks XYZ index", §3 = sector exposure breakdown if Yahoo provides it, §5 = "ETF 不適用個股估值 — 改評相對指數位置與費用率", §6 = systematic risk + 總經連動, §7 = 大盤錨視角。
4. Make explicit in §1: "本檔為 ETF,以下分析以指數成分 + 總經錨為主,跳過 10-K(ETF 沒有此類年報)。"
5. Write **§8** same shape as Tier A(ETF 適用相同 SMC 邏輯 — index 價量結構清晰,比個股更適合)。

**Tier B flow** (4th onward, including ETFs in that range):
1. `mcp__yahoo-finance__get_stock_info(ticker=...)` only
2. **Strict ban** on `mcp__edgar__*` and `mcp__web-fetch__*` (token control)
3. Write framework §1 (1-2 sentences from `longBusinessSummary`) + §4 slim (6-7 key fields only) + §6 slim (3 bullets: business + macro link) + §7 full (direction + confidence + 3-5 watch points)
4. Write **§8 精簡版**(三行):
   ```
   趨勢:<direction>(<basis>)｜位置:<premium|discount>
   買區:<low>–<high>(<basis 精簡>) 或「暫無(需 daily close > xx 觸發 CHoCH)」
   減碼:<low>–<high>｜失效:收盤 <up-or-down> <invalidation_price>
   ```

### Stage 3 — Overall market view

After all tickers: write market view (bull / neutral / bear + confidence 0-10) + 1-2 cross-ticker common threads.

### Stage 4 — Write HTML

`Write` the complete HTML to `finance-workflows/reports/deep-stock-research/<today>.html`. Follow main.md「產出 HTML 規範」exactly — sticky TOC `<nav class="toc">` linking each section, every ticker wrapped in `<details open><summary>...</summary>...</details>` with summary showing ticker + name + direction + confidence chip.

**§8 rendering**: each ticker's `<details>` block includes §8 after §7. Add a small subheading `<h3>§8 SMC 結構與價格區間</h3>` and a mini-table with 4 rows (趨勢/位置/買區/減碼) for Tier A, or the three-line block for Tier B. Failure/degraded mode:一行說明。Include an HTML footer once (per report, not per ticker):

```html
<p class="smc-footer" style="font-size:0.85em;color:#666;margin-top:20px;border-top:1px solid #eee;padding-top:8px">
  §8 為 SMC(Smart Money Concepts)技術參考區間,非投資建議。所有價位、失效條件均來自
  <code>compute_zones.py</code> 的確定性計算,對應 JSON 存於 <code>_zones/&lt;date&gt;/</code>。
</p>
```

**Add at the top, right under `<h1>`** (to mark this as a custom-watchlist run, not the launchd-scheduled one):

```html
<p class="custom-note" style="background:#fffae0;padding:8px 12px;border-left:3px solid #d4a017;font-size:0.92em;">
  本次為自訂 watchlist 互動執行(skill: deep-research-stock):
  <strong>NVDA / TSLA / IVV / NOW / LITE / RDDT / COIN</strong>
  ｜ 觸發時間:<time><!-- ISO timestamp --></time>
</p>
```

(Replace the ticker list with the actual one. Replace the timestamp with the current Asia/Taipei timestamp.)

### Stage 5 — Wrap up

Tell the user:

1. HTML path written to.
2. Tickers + tier assignment (recap).
3. Optional manual Telegram push command (do **not** auto-run):
   ```bash
   finance-workflows/mcp/.venv/bin/python finance-workflows/scripts/notify_telegram.py deep-stock-research <today>
   ```
4. Reminder: if today already had a launchd-scheduled run, this Write **overwrites** the same `<today>.html`. If preservation matters, rename the prior file before re-running, or invoke this skill with `--keep` semantics in a future version (not implemented yet).

## Hard rules

- **NEVER** spawn `claude -p`, **NEVER** run `run-workflow.py`, **NEVER** call any subprocess that re-enters claude. Everything stays inline in this interactive session — this is the whole point of the skill (post-2026-06-15 billing: interactive subscription vs. `claude -p` credit pool).
- `faithfulness.md` rules dominate everything else. Inference labelled as inference; no fabricated numbers; cite EDGAR Item references when quoting risk factors.
- If a ticker's Yahoo lookup fails, mark its section 「資料不可用,本次跳過」 and continue with the rest of the list — do not abort the whole report.
- Stay within the MCPs configured in root `.mcp.json` (`yahoo-finance` / `fred` / `edgar` / `web-fetch` / `knowledge-graph`) plus the local `compute_zones.py` script (yfinance-based, no MCP). Do not invent new tool calls.
- **§8 faithfulness delta**: every price / basis / invalidation number in §8 MUST exist in the ticker's `_zones/<today>/<TICKER>.json`. LLM may **only** round/format for display, not derive or fabricate. Any price in §8 not present in the JSON is a spec violation.
- **§8 language禁令**: forbid 「建議買入 / 必漲 / 強力支撐」; equal lows 一律稱「流動性池」並附掃損說明。
- **§7 vs §8 分歧強制揭露**: if §7's direction disagrees with §8's `trend.direction` (e.g. §7 建設性偏多 + §8 趨勢 down),DO NOT hide it. Write in the ticker's summary: 「基本面(§7)與 SMC 結構(§8)目前分歧,傾向等待 §8 失效條件解除」— 分歧本身是重要訊號,隱藏是 spec 違規。
- Knowledge-graph: after writing the report, optionally record a single `pattern/observation` per Tier A ticker if a non-obvious finding emerged (e.g. unusual debt structure, surprising margin trend, novel risk language in 10-K, §7/§8 分歧持續數週). Do not flood the graph with routine snapshots.
