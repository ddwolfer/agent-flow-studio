# Phase 2 — Real Eason Run Evidence

**Run date:** 2026-05-19 (Taiwan) · **runId:** `2026-05-18T18-43-23-449Z_eason` · gitSha `e0348e2`
**Duration:** ~13.7 min (820s) · **status:** `succeeded` · exitCode 0

## Produced artifacts (real, on this machine)
- `studio/runs/2026-05-18T18-43-23-449Z_eason/report.html` — 29,392 bytes, zh-TW, title「張貽程 / Eason 視角：台股 AI 戰情室 2026-05-19」, bundled CSS applied.
- `studio/runs/.../report.pdf` — 2,161,152 bytes (Chrome headless, `pdfOk:true`).
- `run.json`: `reportOk:true pdfOk:true`.

## Mechanical self-verification
- **Structure (real):** 9 top sections present — ①影片資訊 ②指標儀表板 ③5層邏輯鏈分析(逐字稿) ④Eason今日語錄 ⑤Fed主席回測 ⑥AI六大族群快掃 ⑦偏誤檢查(Druckenmiller/Damodaran視角) ⑧風險提示 ⑨報告總結+今日關鍵訊號摘要. Mirrors the inherited `samples/eason-sample.html` shape.
- **Real data used:** report references TWSE/TAIEX (10 trading days 2026-05-04…05-15, labelled官方), FRED T10Y2Y, 台積電/費半/那斯達克 (Yahoo), 外資/融資 (TWSE) — i.e. the 5 MCP servers were actually called and their data is in the report.
- **Transcript:** report contains 逐字稿-based 5-layer analysis + Eason 語錄 → a transcript was obtained and used. (Source captions-vs-gemma NOT determinable: `runClaude` does not yet write a claude.log — logging gap, see Issue 3.)
- **Calendar:** title dated 2026-05-19 (run date) — calendar injection worked; TAIEX window is recent (not stale/future).
- **Signal blocks:** emoji signal blocks present (🟡×8 + 🔴/🟢 in headings).

## Honest issues found (NOT papered over)

1. **`qualityOk:false` is a FALSE NEGATIVE.** `mechanicalChecks` (v1) searches for English strings "Overall signal"/"Key levels"/"Picks"; the report is Traditional Chinese (⑨報告總結, ②指標儀表板, 第五層：選股方向). The report DOES contain the equivalent sections. → The advisory quality gate is currently meaningless for this zh-TW pipeline. **Follow-up:** make `mechanicalChecks` match the actual Chinese section markers (or make REQUIRED config-driven).

2. **SQLite persistence wrote 0 rows.** `eason_training`, `eason_daily`, `eason_picks` all have 0 rows after the run — the inherited prompt's `mcp__sqlite__create_record` writes did not land. Report HTML/PDF are fine, but the DB side-effects (training history, daily record, picks tracking) did not happen. **Follow-up:** investigate (prompt not calling sqlite tools? server reachable? schema/path?). This affects historical comparison + picks performance tracking, not the day's report itself.

3. **`runClaude` writes no `claude.log`.** Run dir has only run.json/report.html/report.pdf. Transcript source + per-turn trace not captured → harder to debug. **Follow-up:** have runClaude tee stdout/stderr to `runs/<id>/claude.log`.

## Verdict (first run)
End-to-end pipeline **works**: real multi-source data → genuine richly-structured Eason report (HTML+PDF) in ~14 min, fully automated, local. Three real follow-ups above. The subjective quality judgement is the user's.

---

# Confirming run — 2026-05-19 (after FU-1/2/3 merged)

**runId:** `2026-05-18T21-29-59-957Z_eason` · gitSha `893f731` · status **succeeded** · ~16 min · report.html 24,625 B + report.pdf 1.7 MB.

## THE key question — SQLite persistence: FIXED ✅
| table | before | after |
|---|---|---|
| `eason_training` | 0 | **2** (real rows: videos 4bllC7kheuo 2026-05-18 + 5yncQd1ZSC4 2026-05-15, full titles/urls/month_batch) |
| `eason_daily` | 0 | **1** (date 2026-05-19, 4 pillars filled w/ real TWSE/MU data, overall_signal NEUTRAL) |
| `eason_picks` | 0 | 0 (see new finding below — no picks to extract this run) |

FU-2 **cause A confirmed working** — `persistence.md` made the model actually write training+daily rows. `claude.log` (FU-3, now captured & decisive) shows *"All three records written"* + a written-records table.

## FU-1 quality gate — now a TRUE signal ✅
`qualityOk:false`, missing `邏輯鏈/今日語錄/報告總結`. This is **correct** — this report genuinely IS structurally thinner than the first (see new finding). The gate now meaningfully catches degraded reports instead of false-negatives.

## NEW real finding — transcript downloaded but NOT consumed ⚠️
`claude.log` is decisive: *"兩支影片的逐字稿（94k/131k 字元的單行檔）無法在未授權 Bash 的情況下讀取... 報告中所有「Eason 觀點」均來自影片標題,非逐字稿引用,信心值 4.5/10"*.
The transcript is fetched but the inherited skill flow reads the large saved transcript file via a `python3`/Bash step that is **not in our `allowedTools`** (we allow only the 13 MCP tools + Write + Read, not Bash). So the model fell back to **title-only analysis** (self-confidence 4.5/10) → no concrete Eason picks (`eason_picks` legitimately 0) and a thinner report (no 5-layer chain / quotes / summary).
This means: DB-persistence (the goal of this run) is **fixed & confirmed**, but report *quality* is now gated on a separate upstream issue — **the transcript must actually reach the analysis**. Options: (a) add a scoped Bash/python allowance for transcript reading; (b) make the yt-dlp MCP return transcript text inline so no file-read is needed; (c) chunk/summarise the transcript within the MCP. Recommended next slice.

## Confirming-run verdict
Persistence **fixed and proven** (eason_training 0→2, eason_daily 0→1). FU-1 + FU-3 working and immediately useful. One NEW real upstream issue surfaced (transcript-not-consumed → degraded title-only reports), now precisely diagnosed thanks to FU-3. Not faked, not glossed.

---

# FU-4 confirming run — 2026-05-19 (transcript fix)

**runId:** `2026-05-18T23-05-58-449Z_eason` · gitSha `7149c8b` · status succeeded · ~14 min · report.html 25,416 B + report.pdf.

## Result: PARTIAL improvement, root cause NOT fully eliminated (honest)
- Confidence **4.5/10 → 6.0/10** ("MA 計算完整") — improved because market/MA data is now complete (FU-2 + data servers), NOT because the transcript was used.
- `eason_training`/`eason_daily`/`eason_picks` = **2 / 1 / 0** (unchanged from prior run): training+daily correctly **dedup-skipped** (same videos / same 2026-05-19 daily already inserted last run) — that's correct behaviour, not a regression; persistence was already proven. `eason_picks` STILL **0**.
- `qualityOk:false` — report still missing `今日語錄`/`風險提示`/`報告總結` (the quote-dependent sections). FU-1 gate correctly flags it thin.

## Decisive claude.log line (the real ceiling)
> 「逐字稿｜已下載 **59,128 字元，但超過工具直送上限無法讀取**」

The cleaned transcript was 59,128 chars — OVER `STUDIO_TRANSCRIPT_MAX_CHARS` (default 48,000) → `_bound_transcript` returned head+tail+`[…elided…]` with `truncated:true`. The model treated the truncated/large tool result as effectively **unreadable** and fell back to data-only analysis (no Eason quotes → no `語錄`, no picks). i.e. FU-4's deterministic clean+elide is not enough: even ~48k chars in a single MCP tool result is past what the model will reliably consume, AND head/tail elision loses the contiguous quotes the 5-layer Eason analysis needs.

## Honest conclusion
Option (b) as implemented (return big cleaned text inline) **hit a real ceiling**: MCP tool-result size + the model's unwillingness to analyse a `truncated` blob. Persistence/data/quality-gate/logging are all solid; the remaining gap is purely "deliver the transcript's *substance* in a form small + faithful enough to actually be used". This needs a strategy change (a condense/digest step, i.e. closer to option (c)), not another tweak of the same approach. Surfaced to user for the decision; not faked.
