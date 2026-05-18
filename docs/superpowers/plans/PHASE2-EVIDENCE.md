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

## Verdict
End-to-end pipeline **works**: real multi-source data → genuine richly-structured Eason report (HTML+PDF) in ~14 min, fully automated, local. Three real follow-ups above (none block report production; #1 and #2 matter for quality-gating and the persistence/tracking feature). The subjective "is the analysis genuinely good / in Eason's style" judgement is the user's.
