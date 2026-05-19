# FU-6: eason_picks persistence + 報告總結 section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Close the two residual FU-5 gaps: (1) the post-process picks step never substitutes `${HTML_FILE}`/`${LOG_FILE}`/`${DATE}` so it can't read the report and writes 0 `eason_picks` rows; (2) the HTML report omits a `報告總結` section so the FU-1 quality gate fails.

**Architecture:** Bug 1 is a one-line wiring fix in `runPipeline.ts`: build the picks prompt through the existing `buildPrompt` substitution (same as the main prompt) instead of passing `cfg.picksPrompt` raw. Bug 2 is a prompt-level fix: `main.md` explicitly mandates a final `報告總結` section in the HTML (our externalized prompt, not the inherited skill).

**Tech Stack:** TypeScript/Next.js runner, Vitest, the existing `buildPrompt` substitution util, Markdown prompts.

**Why (context):** FU-5 proved the transcript substance now reaches the analysis (confidence 4.5→7.5, real picks in the digest+report). But the confirming run showed `eason_picks=0` and `qualityFailures:["missing section: 報告總結"]`. Root causes (verified by reading code):
- `runPipeline.ts:73` passes `picksPrompt: cfg.picksPrompt` (raw). `postProcess.ts` uses it directly as the `claude -p` arg with NO substitution, so `picks.md`'s literal `${HTML_FILE}`/`${LOG_FILE}`/`${DATE}` reach claude unresolved → it cannot locate the report → extracts nothing. Masked until FU-5 because there were never any picks to extract.
- `main.md` delegates report structure to the inherited `/eason-analysis` skill and never itself requires a `報告總結` section; the model put a summary in chat output, not the HTML.

---

## File Structure

- `studio/lib/runner/runPipeline.ts` — **modify**: substitute the picks prompt via `buildPrompt` before handing it to `postProcess`.
- `studio/lib/runner/runPipeline.test.ts` — **modify**: assert the picks `claude` call receives the resolved report path, not literal `${HTML_FILE}`.
- `studio/prompts/eason/main.md` — **modify**: add an explicit mandatory `報告總結` section requirement.
- `studio/lib/config/load.test.ts` — **modify**: assert `main.md` (the prompt template) mandates 報告總結 (cheap regression guard, mirrors the existing transcript.md content test).

---

### Task 1: Substitute the picks prompt (fix eason_picks=0)

**Files:**
- Modify: `studio/lib/runner/runPipeline.ts`
- Test: `studio/lib/runner/runPipeline.test.ts`

- [ ] **Step 1: Write the failing test.** Append inside the existing `describe("runPipeline", ...)` block in `studio/lib/runner/runPipeline.test.ts`:

```ts
  it("substitutes the picks prompt so the picks claude call gets the real report path, not ${HTML_FILE}", async () => {
    let picksPromptArg: string | undefined;
    await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) => {
        if (file.endsWith("fake-claude.sh")) return spawnProc(file, args, opts);
        // the non-fake "claude" call in postProcess is the picks call
        if (file === "claude") {
          const i = args.indexOf("-p");
          if (i >= 0) picksPromptArg = args[i + 1];
        }
        return { code: 0 };
      },
    });
    expect(picksPromptArg).toBeDefined();
    // must be resolved to an absolute report.html path under the run dir
    expect(picksPromptArg).toContain("report.html");
    expect(picksPromptArg).not.toContain("${HTML_FILE}");
    expect(picksPromptArg).not.toContain("${LOG_FILE}");
    expect(picksPromptArg).not.toContain("${DATE}");
  });
```

> Context: the fake-CLI e2e path still runs `postProcess` (digest pass is skipped under fake, but `runClaude` main + `postProcess` still execute; `postProcess` issues a real `"claude"` spawner call for picks — in tests the spawner stub returns `{code:0}`). `picks.md` contains the literal tokens `${HTML_FILE}`, `${LOG_FILE}`, `${DATE}`, so before the fix this test fails on the `.not.toContain("${HTML_FILE}")` assertion.

- [ ] **Step 2: Run it to verify it fails**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts -t "substitutes the picks prompt"`
Expected: FAIL — `picksPromptArg` still contains `${HTML_FILE}` (raw `cfg.picksPrompt`).

- [ ] **Step 3: Implement the fix** in `studio/lib/runner/runPipeline.ts`. Replace the `postProcess({...})` call's `picksPrompt: cfg.picksPrompt,` line by first building a substituted picks prompt. Concretely, immediately after `failStage = "postProcess";` (line 69) and before `const pp = await postProcess({`, insert:

```ts
    const picksPrompt = buildPrompt({
      promptTemplate: cfg.picksPrompt, references: [],
      channel: cfg.channel, calendarText: cal.text,
      htmlPath: cr.htmlPath, logPath: claudeLogPath, dateIso: cal.iso,
    });
```

then change the `postProcess` argument `picksPrompt: cfg.picksPrompt,` to `picksPrompt,`.

> Rationale: `buildPrompt` already does `.replaceAll("${HTML_FILE}", a.htmlPath ?? "")`, `${LOG_FILE}`, `${DATE}`. `picks.md` has none of the `{{channel.*}}`/`{{calendar}}` tokens so those replacements are harmless no-ops, and `references: []` means nothing is appended. This is DRY (same substitution path as the main prompt) and minimal.

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Run the full suite**

Run: `cd studio && npx vitest run`
Expected: all pass (existing e2e/fake tests unaffected — the picks prompt is still passed, just substituted).

- [ ] **Step 6: Commit + push**

```bash
git add studio/lib/runner/runPipeline.ts studio/lib/runner/runPipeline.test.ts
git commit -m "fix(runner): substitute picks prompt (\${HTML_FILE}/\${LOG_FILE}/\${DATE}) so eason_picks actually writes (FU-6)"
git push origin main
```

---

### Task 2: Mandate a 報告總結 section in main.md

**Files:**
- Modify: `studio/prompts/eason/main.md`
- Test: `studio/lib/config/load.test.ts`

- [ ] **Step 1: Write the failing test.** Append inside `describe("loadConfig", ...)` in `studio/lib/config/load.test.ts`:

```ts
  it("eason main.md mandates a 報告總結 section in the HTML report", async () => {
    const c = await loadConfig("eason", ROOT);
    expect(c.promptTemplate).toContain("報告總結");
  });
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd studio && npx vitest run lib/config/load.test.ts -t "報告總結"`
Expected: FAIL — current `main.md` does not contain the string `報告總結`.

- [ ] **Step 3: Implement.** Append this block to the END of `studio/prompts/eason/main.md` (after the existing 寫作原則 list, as a new section). Use exactly this text:

```markdown

報告結構強制要求（缺一即不合格）：
- HTML 報告**必須**依序包含這些段落標題：指標儀表板、五層邏輯鏈分析、今日語錄、風險提示、**報告總結**。
- **報告總結**為報告的最後一段，必須實際寫進 HTML（不是只在對話輸出），內容包含：今日整體訊號（看多/看空/中性）、信心值、3–5 條今日關鍵訊號摘要、以及對隔日的觀察重點。
- 不可把總結只放在你的回覆訊息裡而漏寫進 ${HTML_FILE}；報告檔案本身必須自成完整。
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd studio && npx vitest run lib/config/load.test.ts`
Expected: PASS (the new test + all existing load tests).

- [ ] **Step 5: Commit + push**

```bash
git add studio/prompts/eason/main.md studio/lib/config/load.test.ts
git commit -m "feat(prompts): main.md mandates a 報告總結 section written into the HTML (FU-6)"
git push origin main
```

---

### Task 3: FU-6 confirming real run + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

Operational task (run by the controller, like prior FU confirming runs).

- [ ] **Step 1:** Launch a real `eason` run (ad-hoc launcher importing `EASON_ALLOWED_TOOLS` + `STUDIO_ROOT`/`RUNS_ROOT`, `mcpConfigPath = studio/mcp/mcp.json`, `claudeBin:"claude"`, `spawner: spawnProc`). Background, long-lived; wait on `run.json` reaching `succeeded`/`failed`.

- [ ] **Step 2:** Verify against ground truth (no glossing):
  - `eason_picks` row count **> 0** with sane rows (ticker/name/pick_date/source) — THE Bug-1 success signal. Compare before/after.
  - `report.html` contains a real `報告總結` section (grep + eyeball) — Bug-2 signal.
  - `run.json` `qualityOk` — should now be `true` (or `qualityFailures` no longer lists `報告總結`).
  - Confirm FU-5 gains held (digest produced, 今日語錄/邏輯鏈 still present, confidence not regressed).
  - Skim the picks rows for faithfulness (no fabricated tickers; picks.md "寧可漏" rule respected).

- [ ] **Step 3:** Append a dated **"FU-6 confirming run"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md`: runId, gitSha, before/after table (eason_picks count, qualityOk, 報告總結 present), honest verdict (succeeded / partial / failed — no varnish). Commit + push. Record a KG `record_experience` (success/lesson) on the outcome. Remove any ad-hoc launcher file so the tree stays clean.

---

## Self-Review

**1. Spec coverage:** Bug 1 (eason_picks=0) → Task 1 substitutes the picks prompt via `buildPrompt` (root cause was raw `cfg.picksPrompt` at `runPipeline.ts:73`). Bug 2 (報告總結 missing) → Task 2 mandates it in `main.md`. Verification → Task 3. Covered.

**2. Placeholder scan:** No TBD/TODO; the runPipeline insertion point is exact (after `failStage="postProcess"`, before `postProcess({`); prompt text is given verbatim; test code is complete.

**3. Type consistency:** `buildPrompt` is already imported in `runPipeline.ts` (line 5) and its `BuildPromptArgs` accepts `promptTemplate/references/channel/calendarText/htmlPath/logPath/dateIso` — all in scope at the call site (`cfg.picksPrompt`, `cfg.channel`, `cal.text`, `cr.htmlPath`, `claudeLogPath`, `cal.iso`). `postProcess`'s `picksPrompt: string` arg type is unchanged (still a string, now substituted). No signature changes, so no ripple.

**Open risk (flagged, not blocking):** Task 2 is prompt-level; a model could still under-emit the section. The confirming run (Task 3) is the gate; if it still fails, the next step is tightening main.md or making `report.css`/template scaffold the section — not a design change. Task 1's fix is deterministic (substitution) and the real lever for the user-visible `eason_picks` outcome.
