# Multi-Analyst Extensibility + 游庭皓 Pipeline — Design Spec

**Date:** 2026-05-20 · **Status:** approved (brainstorm, user authorised run-to-completion)
**Topic:** agent-flow-studio — make pipelines analyst-agnostic and add a standalone 游庭皓 macro pipeline

## 1. Goal & background

The inherited tool had two report *types*: Eason 視角晚間報告 (ported) and a 早晨總經 briefing featuring 游庭皓 (never ported). agent-flow-studio v1 was deliberately Eason-only. The runner is already largely config-driven (`loadConfig(channelId)` → `pipelines/<pipeline>.yaml` → that pipeline's prompts), but several spots are hardcoded to Eason / assume stock-picking.

**User-locked decisions (brainstorm):**
- Standalone per-analyst pipeline (游庭皓 = his own pipeline & report, parallel to Eason). A *combined* briefing (游庭皓 + Eason + consensus) is a **separate later FU** — explicitly out of scope here ("先獨立、再做組合").
- Generalise the schema: `picks`, `quality_judge`, `digest` optional; per-pipeline tool allowlist; de-hardcode `pipelineStore`/canvas. Goal: **adding any analyst = add channels.yaml entry + pipelines/<id>.yaml + prompts/<id>/* , zero code change.**
- 游庭皓 v1 = HTML/PDF only, **no DB persistence** (he is macro top-down, no stock picks).
- Canvas RunBar gets an **analyst selector** (dropdown of enabled channels); run the selected one.
- Approach 1 (generalise in place, prove with 游庭皓). Approach 2 (analyst-registry abstraction) rejected as YAGNI — config IS the registry.

## 2. Scope boundary (YAGNI — explicit exclusions)

- No combined/consensus briefing (separate future FU).
- No DB for 游庭皓 (no `post.picks`, no `persistence.md`).
- Canvas keeps the generic fixed 6-node graph. For pipelines without a persistence step the `持久化` node is not meaningful; v1 leaves it as the existing derived behaviour and **documents this as a known cosmetic limitation** (a fully pipeline-driven canvas graph is a future concern, not v1).
- No new MCP server: 游庭皓's US-macro needs (CPI/PCE/NFP/Fed/GDP/PMI/T10Y2Y) are covered by the existing **fred** server + twse + yahoo.

## 3. Extensibility refactor (analyst-agnostic core)

- **`studio/lib/config/schema.ts`** — `PipelineFile`: make `post.picks` optional, `quality_judge` optional (`digest` already optional). Add `allowed_tools: z.array(z.string()).min(1)` (the pipeline declares its own MCP/Write/Read tool ids).
- **`studio/lib/config/load.ts`** — `LoadedConfig.picksPrompt?` / `judgeRubric?` become optional; only read those files when configured. No throw when absent.
- **`studio/lib/runner/allowedTools.ts`** — remove the `EASON_ALLOWED_TOOLS` constant; export `pipelineAllowedTools(pipeline): string[]` returning `pipeline.allowed_tools`. Keep `digestAllowedTools(list)` (filters the given list to `mcp__yt-dlp__*` + `Write` + `Read`). The 13 Eason tool ids move into `eason.yaml`'s `allowed_tools`.
- **`studio/lib/config/pipelineStore.ts`** — `ALLOWED_PIPELINES` no longer the literal `{"eason"}`; derive it by reading `config/channels.yaml` and collecting the distinct `channel.pipeline` values (so any configured pipeline is editable; adding one is config-only).
- **`studio/lib/runner/runPipeline.ts`** — additive conditionals only (no flow restructure): if `cfg.pipeline.post.picks` is absent → skip the postProcess picks claude call; `digest` already conditional. The quality gate is `mechanicalChecks(quality_sections)` (config-driven, unchanged — `quality_judge` is a loaded-only config field, not a runtime stage, so making it optional only means `loadConfig` won't throw when it's absent). `progress` 4-stage emission unchanged (a no-picks pipeline still has digest/analysis/postprocess/quality stages; postprocess = PDF only).
- **`studio/lib/runner/postProcess.ts`** — accept an absent `picks` config: `runPicks` only when a picks prompt+model exist; never throw on missing picks.
- **`studio/app/api/runs/route.ts`** — POST renders `mcp.json` (via existing `renderMcpConfig`) and passes `mcpConfigPath` + the selected pipeline's `allowed_tools` into `runPipeline` (this closes the long-flagged "canvas runs have no MCP" gap and is required for 游庭皓 *and* Eason to produce real reports from the button). Read the channel→pipeline to get its `allowed_tools`.

## 4. 游庭皓 standalone pipeline

- **`studio/config/channels.yaml`** — `yutinghao`: `pipeline: yutinghao`, `enabled: true` (currently `pipeline: eason`, `enabled: false`).
- **`studio/config/pipelines/yutinghao.yaml`** — `name: yutinghao`, `model: claude-sonnet-4-6`, `max_turns: 50`, `allowed_tools:` [yt-dlp search + transcript_page + download_transcript, twse_* (5), yahoo_quote, fred_get_series, Write, Read] (NO sqlite — no persistence), `prompt.template: prompts/yutinghao/main.md`, `prompt.references: [framework.md, voice.md, transcript.md]`, `post: {pdf:true, notify:false}` (no `picks`), `digest: {model: claude-sonnet-4-6, prompt: prompts/yutinghao/digest.md}`, no `quality_judge`, `quality_sections: ["市場快照","總經觀點","關鍵數據","風險","報告總結"]`.
- **`studio/config/pipelines/eason.yaml`** — add `allowed_tools:` with the existing 13 Eason tool ids (moved out of code).
- **`studio/prompts/yutinghao/`** (new, NO picks.md / persistence.md):
  - `main.md` — produce a 總經 top-down briefing HTML to `${HTML_FILE}`; structure = 市場快照表 / 游庭皓今日總經觀點 / 關鍵數據解讀 / 風險與資產配置 / 報告總結; the same strict no-fabrication 寫作原則 as the inherited `daily-briefing.sh` (no invented causation; observation-only; "原因不明，持續觀察"); read the digest via `${TRANSCRIPT_DIGEST}`; title「游庭皓 總經視角：每日財經速解讀 ${DATE}」.
  - `framework.md` — 游庭皓 top-down macro framework (US macro → TW macro → sector → risk; the data points he routinely cites: CPI/PCE/NFP/Fed funds/GDP/ISM PMI/T10Y2Y/外資買賣超/景氣燈號/匯率), distilled from the legacy `yt-briefing` references.
  - `voice.md` — neutral, data-driven, systematic, mid-long-term; explicitly NOT stock-picking and NOT bullish-biased (contrast with Eason).
  - `digest.md` — Pass-1 digest schema for a 游庭皓 video: 影片清單 / 游庭皓總體立場(偏多/中性/偏謹慎 + 理由) / 關鍵總經數據與解讀(逐條，含他引用的數字) / 風險點 / 資產配置與操作傾向 / 關鍵原話逐字引用; strict faithfulness (only extract, verbatim quotes, must `Write` the file even if transcript unavailable — same contract as eason/digest.md).
  - `transcript.md` — Pass-2: `Read` `${TRANSCRIPT_DIGEST}`, forbid yt-dlp; the digest is authoritative; map its sections to the report.

## 5. Canvas analyst selector

- **`studio/components/canvas/RunBar.tsx`** — fetch `/api/channels`; render a `<select>` of `enabled` channels (value = channel id, label = name); local `channelId` state defaulting to the first enabled (or `eason`). Run triggers the selected channel. The existing newest-run polling / live progress is already channel-agnostic (keyed off `/api/runs`), so it works for any pipeline unchanged.
- **`studio/app/page.tsx`** — RunBar no longer receives a hardcoded `channelId="eason"`; RunBar owns the selection. `onActive`/progress wiring unchanged.
- Known v1 limitation (documented, not fixed): the 6 canvas nodes are a fixed Eason-shaped graph; for 游庭皓 the `持久化` node is not meaningful (no DB) — it keeps its current derived display. A pipeline-driven graph is future scope.

## 6. Error handling

- Schema: a pipeline missing `picks`/`quality_judge` is valid (optional); missing `allowed_tools` → zod fails (required) → 400 / ConfigError (a pipeline must declare its tools). Bad YAML/zod on pipeline PUT → 400, no write (existing pipelineStore behaviour).
- runPipeline: absent picks/judge → skipped, not errored; digest failure still → stage `digest` (unchanged). `/api/runs` POST: if `renderMcpConfig` fails (e.g. missing FRED key) → the run is recorded `failed` with the error (fire-and-forget already swallows; surface via run.json) — never crash the route.
- 游庭皓 transcript unavailable → digest.md still writes the file noting unavailability; analysis degrades gracefully (same contract as Eason).

## 7. Testing

- `schema.test`/`load.test`: a pipeline yaml WITHOUT `picks` and WITHOUT `quality_judge` but WITH `allowed_tools` parses & loads (picksPrompt/judgeRubric undefined, no throw); `allowed_tools` required.
- `pipelineStore.test`: `ALLOWED_PIPELINES` derived from a tmp `channels.yaml` containing eason+yutinghao → both readable; an unconfigured name → `PipelineStoreError`.
- `allowedTools.test`: `pipelineAllowedTools` returns the pipeline's list; `digestAllowedTools` filters it to yt-dlp+Write+Read.
- `runPipeline.test` (fake CLI): a config with no `picks` → run succeeds, postProcess issues no picks claude call, progress still `{digest,analysis,postprocess,quality}`.
- `/api/runs` POST: assert it renders mcp.json and passes `mcpConfigPath`+`allowed_tools` (spawner/renderMcpConfig spy).
- Frontend (RunBar selector, prompts): gated by `tsc --noEmit` + `next build` + full vitest staying green; functional correctness via the confirming run.
- **Confirming run (operational):** a real 游庭皓 run (via the now-MCP-wired API or launcher) produces an HTML/PDF macro report with his 5 sections, citing real FRED/TWSE/Yahoo data, transcript-driven (digest consumed); honest evidence appended to `PHASE2-EVIDENCE.md`, including the documented persistence-node limitation. No DB assertions (none expected).

## 8. Delivery definition (v1 done = all hold)

1. PipelineFile accepts pipelines without picks/quality_judge; `allowed_tools` required; existing Eason pipeline still loads & runs unchanged (Eason regression-free).
2. Adding the 游庭皓 analyst was config+prompts only (no code referencing "yutinghao"/"游庭皓" by name in TS).
3. `pipelineStore` allow-list derived from channels.yaml; canvas pipeline-edit works for both.
4. Canvas RunBar lets the user pick eason or 游庭皓 and run it; live progress colours work for both.
5. `/api/runs` button runs now wire MCP (Eason from the button produces a real-data report too).
6. A real 游庭皓 confirming run yields a genuine macro briefing (his sections, real data, transcript-driven); honest evidence recorded.
7. API + pure-logic tests green; tsc clean; next build ok; full vitest green; Eason path unbroken.
