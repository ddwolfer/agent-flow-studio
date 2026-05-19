# Multi-Analyst Extensibility + 游庭皓 Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make agent-flow-studio pipelines analyst-agnostic (picks/quality_judge optional, per-pipeline tool allowlist, no Eason-hardcoding) and add a standalone 游庭皓 macro pipeline runnable from the canvas.

**Architecture:** Approach 1 — generalise the existing config-driven runner in place; prove it with a second pipeline. Adding any analyst becomes channels.yaml + pipelines/<id>.yaml + prompts/<id>/* with zero TS change. The proven two-pass digest + runner machinery is reused unchanged in flow; only Eason-specific assumptions become optional/per-pipeline.

**Tech Stack:** TypeScript / Next.js 15 / React 19, zod, `yaml`, Vitest. No new MCP server (existing fred+twse+yahoo cover 游庭皓 macro).

**Spec:** `docs/superpowers/specs/2026-05-20-multi-analyst-yutinghao-design.md`. Combined briefing is OUT of scope (separate future FU). 游庭皓 v1 = HTML/PDF only, no DB.

---

## File Structure

- `studio/lib/config/schema.ts` — `post.picks` optional, `quality_judge` optional, add required `allowed_tools`.
- `studio/lib/config/load.ts` — `picksPrompt?`/`judgeRubric?` optional; conditional reads.
- `studio/lib/runner/allowedTools.ts` — drop `EASON_ALLOWED_TOOLS`; add `pipelineAllowedTools`; `digestAllowedTools` filters a required list.
- `studio/config/pipelines/eason.yaml` — add `allowed_tools` (the 13 ids moved out of code).
- `studio/lib/config/pipelineStore.ts` — allow-list derived from `channels.yaml`.
- `studio/lib/runner/runPipeline.ts` — conditional picks (skip when no picks config); conditional snapshot hash.
- `studio/lib/runner/postProcess.ts` — tolerate absent `post.picks`.
- `studio/app/api/runs/route.ts` — POST renders mcp.json + passes mcpConfigPath + pipeline allowed_tools.
- `studio/config/pipelines/yutinghao.yaml` + `studio/prompts/yutinghao/{main,framework,voice,digest,transcript}.md` + `studio/config/channels.yaml` — the new analyst (config+prompts only).
- `studio/components/canvas/RunBar.tsx` + `studio/app/page.tsx` — analyst selector.
- Test files alongside, per task.

---

### Task 1: Schema + loadConfig — picks/quality_judge optional, allowed_tools required

**Files:**
- Modify: `studio/lib/config/schema.ts`, `studio/lib/config/load.ts`
- Test: `studio/lib/config/schema.test.ts` (create), `studio/lib/config/load.test.ts` (append)

- [ ] **Step 1: Write failing tests.** Create `studio/lib/config/schema.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { PipelineFile } from "./schema";

const base = {
  name: "x", model: "m", max_turns: 10,
  prompt: { template: "p.md", references: [] },
  post: { pdf: true, notify: false },
  allowed_tools: ["Write", "Read"],
};

describe("PipelineFile schema", () => {
  it("accepts a pipeline WITHOUT post.picks and WITHOUT quality_judge", () => {
    const r = PipelineFile.safeParse(base);
    expect(r.success).toBe(true);
  });
  it("still accepts a pipeline WITH post.picks + quality_judge", () => {
    const r = PipelineFile.safeParse({
      ...base,
      post: { ...base.post, picks: { model: "h", prompt: "picks.md" } },
      quality_judge: { model: "m", rubric: "r.md" },
    });
    expect(r.success).toBe(true);
  });
  it("requires allowed_tools (non-empty)", () => {
    expect(PipelineFile.safeParse({ ...base, allowed_tools: undefined }).success).toBe(false);
    expect(PipelineFile.safeParse({ ...base, allowed_tools: [] }).success).toBe(false);
  });
});
```

Append to `studio/lib/config/load.test.ts` (it already has `import { describe,it,expect } from "vitest"`, `mkdtemp/mkdir/writeFile`, `loadConfig`, `ConfigError`; reuse them — add `rm` if not imported):

```ts
it("loadConfig handles a pipeline with no picks / no quality_judge (picksPrompt+judgeRubric undefined)", async () => {
  const root = await mkdtemp(join(tmpdir(), "lc-"));
  await mkdir(join(root, "config/pipelines"), { recursive: true });
  await mkdir(join(root, "prompts/np"), { recursive: true });
  await writeFile(join(root, "config/channels.yaml"),
    "channels:\n  - id: np\n    handle: '@np'\n    name: NP\n    search_query: q\n    pipeline: np\n    enabled: true\n");
  await writeFile(join(root, "config/pipelines/np.yaml"),
    "name: np\nmodel: m\nmax_turns: 10\nallowed_tools: [Write, Read]\nprompt:\n  template: prompts/np/main.md\n  references: []\npost:\n  pdf: true\n  notify: false\n");
  await writeFile(join(root, "prompts/np/main.md"), "hello");
  const cfg = await loadConfig("np", root);
  expect(cfg.picksPrompt).toBeUndefined();
  expect(cfg.judgeRubric).toBeUndefined();
  expect(cfg.pipeline.allowed_tools).toEqual(["Write", "Read"]);
});
```

(If `mkdtemp/mkdir/writeFile/tmpdir/join` aren't already imported at the top of load.test.ts, add: `import { mkdtemp, mkdir, writeFile } from "node:fs/promises"; import { tmpdir } from "node:os"; import { join } from "node:path";` — check first; load.test.ts currently imports them per the file. Reuse the existing imports; only add what's missing.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd studio && npx vitest run lib/config/schema.test.ts lib/config/load.test.ts`
Expected: FAIL (schema rejects missing picks/quality_judge / has no allowed_tools; loadConfig throws on missing picks file).

- [ ] **Step 3: Implement schema.ts.** Replace the `post` and `quality_judge` lines and add `allowed_tools`:

```ts
export const PipelineFile = z.object({
  name: z.string().min(1),
  model: z.string().min(1),
  max_turns: z.number().int().positive(),
  allowed_tools: z.array(z.string().min(1)).min(1),
  prompt: z.object({
    template: z.string().min(1),
    references: z.array(z.string()).default([]),
  }),
  post: z.object({
    pdf: z.boolean(),
    notify: z.boolean(),
    picks: z.object({ model: z.string().min(1), prompt: z.string().min(1) }).optional(),
  }),
  digest: z.object({
    model: z.string().min(1),
    prompt: z.string().min(1),
  }).optional(),
  quality_judge: z.object({ model: z.string().min(1), rubric: z.string().min(1) }).optional(),
  quality_sections: z.array(z.string()).optional(),
});
```

- [ ] **Step 4: Implement load.ts.** Change `LoadedConfig` so `picksPrompt?: string;` and `judgeRubric?: string;` (add `?`). Replace the two unconditional reads:

```ts
  const picksPrompt = pipeline.post.picks
    ? await readText(join(studioRoot, pipeline.post.picks.prompt))
    : undefined;
  const judgeRubric = pipeline.quality_judge
    ? await readText(join(studioRoot, pipeline.quality_judge.rubric))
    : undefined;
```

(The returned object already spreads these names — unchanged.)

- [ ] **Step 5: Run to verify they pass**

Run: `cd studio && npx vitest run lib/config/schema.test.ts lib/config/load.test.ts && npx tsc --noEmit`
Expected: PASS. tsc will now flag downstream uses of `cfg.picksPrompt`/`judgeRubric` as possibly-undefined — those are fixed in Tasks 2/4; if tsc errors ONLY in `runPipeline.ts`/`allowedTools.ts`/`pipelineStore.ts` that is expected at this step. Note them and proceed (do NOT fix them here — later tasks own those files). If tsc errors elsewhere, stop and report.

- [ ] **Step 6: Commit + push** (git from repo root `/Users/pochenkuo/AI/new_financial-report-system`)

```bash
git add studio/lib/config/schema.ts studio/lib/config/schema.test.ts studio/lib/config/load.ts studio/lib/config/load.test.ts
git commit -m "feat(config): pipeline picks/quality_judge optional + required allowed_tools (multi-analyst)"
git push origin main
```

> Context: `judgeRubric` is loaded-only (never consumed by runPipeline — the quality gate is `mechanicalChecks(quality_sections)`), so making it optional is safe. `tsc` red in runPipeline/allowedTools/pipelineStore after this task is expected and resolved by Tasks 2–4; this task's own tests + schema/load are green.

---

### Task 2: allowedTools — per-pipeline list, drop EASON constant; eason.yaml declares its tools

**Files:**
- Modify: `studio/lib/runner/allowedTools.ts`, `studio/lib/runner/allowedTools.test.ts`, `studio/config/pipelines/eason.yaml`
- Modify: `studio/lib/runner/digestPass.ts` (only if it imports the removed constant — verify)

- [ ] **Step 1: Update the test first** — replace `studio/lib/runner/allowedTools.test.ts` entirely with:

```ts
import { describe, it, expect } from "vitest";
import { pipelineAllowedTools, digestAllowedTools } from "./allowedTools";

describe("allowedTools", () => {
  it("pipelineAllowedTools returns the pipeline's declared list", () => {
    expect(pipelineAllowedTools({ allowed_tools: ["mcp__fred__fred_get_series", "Write"] }))
      .toEqual(["mcp__fred__fred_get_series", "Write"]);
  });
  it("digestAllowedTools keeps only yt-dlp tools + Write + Read, order preserved", () => {
    expect(digestAllowedTools([
      "mcp__yt-dlp__ytdlp_transcript_page", "mcp__twse__twse_fmtqik",
      "Write", "Read", "Bash",
    ])).toEqual(["mcp__yt-dlp__ytdlp_transcript_page", "Write", "Read"]);
  });
  it("digestAllowedTools on undefined/empty returns empty (no Eason fallback)", () => {
    expect(digestAllowedTools(undefined)).toEqual([]);
    expect(digestAllowedTools([])).toEqual([]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd studio && npx vitest run lib/runner/allowedTools.test.ts`
Expected: FAIL (`pipelineAllowedTools` not exported; old EASON fallback behaviour differs).

- [ ] **Step 3: Replace `studio/lib/runner/allowedTools.ts` entirely with:**

```ts
// Tool allowlists are declared per-pipeline in pipelines/<name>.yaml (allowed_tools).
// No analyst is hardcoded here.

/** The MCP/Write/Read tool ids a pipeline is allowed to use. */
export function pipelineAllowedTools(pipeline: { allowed_tools: readonly string[] }): string[] {
  return [...pipeline.allowed_tools];
}

/** Reduce an allowlist to what the digest pass may use: yt-dlp tools + Write + Read.
 *  No fallback — the pipeline must declare its tools (schema enforces non-empty). */
export function digestAllowedTools(all?: readonly string[]): string[] {
  if (!all) return [];
  const keep = (t: string) =>
    t.startsWith("mcp__yt-dlp__") || t === "Write" || t === "Read";
  return all.filter(keep);
}
```

- [ ] **Step 4: Add `allowed_tools` to `studio/config/pipelines/eason.yaml`.** Insert this block right after the `max_turns: 50` line (top-level key, sibling of `prompt:`):

```yaml
allowed_tools:
  - mcp__yt-dlp__ytdlp_search_videos
  - mcp__yt-dlp__ytdlp_download_transcript
  - mcp__yt-dlp__ytdlp_transcript_page
  - mcp__twse__twse_fmtqik
  - mcp__twse__twse_mi_index
  - mcp__twse__twse_mi_margn
  - mcp__twse__twse_stock_day_all
  - mcp__twse__twse_mi_qfiis_cat
  - mcp__yahoo-finance__yahoo_quote
  - mcp__fred__fred_get_series
  - mcp__sqlite__query
  - mcp__sqlite__create_record
  - mcp__sqlite__update_records
  - Write
  - Read
```

- [ ] **Step 5: Check for the removed constant's consumers.**

Run: `cd studio && grep -rn "EASON_ALLOWED_TOOLS" . --include=*.ts --include=*.tsx | grep -v node_modules | grep -v .next`
Expected: NO matches. (`digestPass.ts` uses `digestAllowedTools(a.allowedTools)` — unaffected.) If any non-test file still imports `EASON_ALLOWED_TOOLS`, that's an error to fix in this task (replace with `pipelineAllowedTools` fed from config). Report what you found.

- [ ] **Step 6: Run tests + types**

Run: `cd studio && npx vitest run lib/runner/allowedTools.test.ts && npx tsc --noEmit`
Expected: allowedTools tests PASS. `tsc` may still be red in runPipeline.ts / pipelineStore.ts (Tasks 3,4) — expected; not elsewhere.

- [ ] **Step 7: Commit + push**

```bash
git add studio/lib/runner/allowedTools.ts studio/lib/runner/allowedTools.test.ts studio/config/pipelines/eason.yaml
git commit -m "feat(runner): per-pipeline allowed_tools; drop hardcoded EASON list (multi-analyst)"
git push origin main
```

---

### Task 3: pipelineStore allow-list derived from channels.yaml

**Files:**
- Modify: `studio/lib/config/pipelineStore.ts`, `studio/lib/config/pipelineStore.test.ts`

- [ ] **Step 1: Rewrite the test** `studio/lib/config/pipelineStore.test.ts` entirely:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, mkdir, copyFile, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readPipeline, writePipeline, PipelineStoreError } from "./pipelineStore";

const REAL_EASON = new URL("../../config/pipelines/eason.yaml", import.meta.url).pathname;
let root: string;
beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "pl-"));
  await mkdir(join(root, "config/pipelines"), { recursive: true });
  await copyFile(REAL_EASON, join(root, "config/pipelines/eason.yaml"));
  // allow-list is derived from channels.yaml
  await writeFile(join(root, "config/channels.yaml"),
    "channels:\n" +
    "  - id: eason\n    handle: '@m168'\n    name: E\n    search_query: q\n    pipeline: eason\n    enabled: true\n" +
    "  - id: yt\n    handle: '@yt'\n    name: Y\n    search_query: q\n    pipeline: yutinghao\n    enabled: false\n");
});

describe("pipelineStore", () => {
  it("reads a pipeline whose name is referenced by some channel", async () => {
    const p = await readPipeline(root, "eason");
    expect(p.name).toBe("eason");
  });
  it("rejects a pipeline name not referenced by any channel", async () => {
    await expect(readPipeline(root, "../secret")).rejects.toBeInstanceOf(PipelineStoreError);
    await expect(readPipeline(root, "ghost")).rejects.toBeInstanceOf(PipelineStoreError);
  });
  it("allows a pipeline referenced by a (even disabled) channel — e.g. yutinghao", async () => {
    // yutinghao.yaml not present in tmp → read fails on file, but the NAME is allowed
    // (proves the allow-list comes from channels.yaml, not a hardcoded set)
    await expect(readPipeline(root, "yutinghao"))
      .rejects.toThrow(/not readable/);
  });
  it("rejects a schema-invalid write without touching the file", async () => {
    const before = await readFile(join(root, "config/pipelines/eason.yaml"), "utf8");
    await expect(writePipeline(root, "eason", { name: "eason" } as never))
      .rejects.toBeInstanceOf(PipelineStoreError);
    expect(await readFile(join(root, "config/pipelines/eason.yaml"), "utf8")).toBe(before);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd studio && npx vitest run lib/config/pipelineStore.test.ts`
Expected: FAIL (current hardcoded `{"eason"}` rejects `yutinghao`; "not readable" expectation differs).

- [ ] **Step 3: Rewrite `studio/lib/config/pipelineStore.ts`:**

```ts
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { PipelineFile, ChannelsFile, type PipelineConfig } from "./schema";

export class PipelineStoreError extends Error {
  constructor(m: string) { super(m); this.name = "PipelineStoreError"; }
}

/** Pipeline names allowed = the distinct `pipeline` values referenced in channels.yaml. */
async function allowedPipelines(root: string): Promise<Set<string>> {
  let raw: string;
  try { raw = await readFile(join(root, "config/channels.yaml"), "utf8"); }
  catch { throw new PipelineStoreError("channels.yaml not readable"); }
  let parsed;
  try { parsed = ChannelsFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid channels.yaml: ${e instanceof Error ? e.message : String(e)}`); }
  return new Set(parsed.channels.map((c) => c.pipeline));
}

async function pathFor(root: string, name: string): Promise<string> {
  const allowed = await allowedPipelines(root);
  if (!allowed.has(name)) throw new PipelineStoreError(`unknown pipeline: ${name}`);
  return join(root, `config/pipelines/${name}.yaml`);
}

export async function readPipeline(root: string, name: string): Promise<PipelineConfig> {
  const p = await pathFor(root, name);
  let raw: string;
  try { raw = await readFile(p, "utf8"); }
  catch { throw new PipelineStoreError(`pipeline file not readable: ${name}`); }
  try { return PipelineFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid pipeline ${name}: ${e instanceof Error ? e.message : String(e)}`); }
}

export async function writePipeline(root: string, name: string, obj: unknown): Promise<void> {
  const p = await pathFor(root, name);
  let valid: PipelineConfig;
  try { valid = PipelineFile.parse(obj); }
  catch (e) { throw new PipelineStoreError(`schema validation failed: ${e instanceof Error ? e.message : String(e)}`); }
  await writeFile(p, YAML.stringify(valid), "utf8");
}
```

(`ChannelsFile` is already exported from `schema.ts` — confirm the import.)

- [ ] **Step 4: Run to verify it passes**

Run: `cd studio && npx vitest run lib/config/pipelineStore.test.ts && npx tsc --noEmit`
Expected: pipelineStore tests PASS. The `/api/pipeline/[name]` route awaits these async fns already (it `await`s the store calls) — no route change needed; confirm by reading `studio/app/api/pipeline/[name]/route.ts` (it already `await`s readPipeline/writePipeline). tsc may still be red only in runPipeline.ts (Task 4).

- [ ] **Step 5: Commit + push**

```bash
git add studio/lib/config/pipelineStore.ts studio/lib/config/pipelineStore.test.ts
git commit -m "feat(config): pipelineStore allow-list derived from channels.yaml (multi-analyst)"
git push origin main
```

---

### Task 4: runPipeline + postProcess — skip picks when not configured

**Files:**
- Modify: `studio/lib/runner/runPipeline.ts`, `studio/lib/runner/postProcess.ts`
- Test: `studio/lib/runner/runPipeline.test.ts` (append)

- [ ] **Step 1: Write the failing test** — append inside the existing `describe("runPipeline", …)` in `studio/lib/runner/runPipeline.test.ts`:

```ts
  it("runs a no-picks pipeline (fake CLI): succeeds, issues no picks claude call, progress emitted", async () => {
    // Build a tmp studio root with a picks-less pipeline reusing eason's prompts.
    const { mkdtemp, mkdir, writeFile, cp } = await import("node:fs/promises");
    const sroot = await mkdtemp(join(tmpdir(), "nps-"));
    await mkdir(join(sroot, "config/pipelines"), { recursive: true });
    await cp(join(STUDIO, "prompts"), join(sroot, "prompts"), { recursive: true });
    await writeFile(join(sroot, "config/channels.yaml"),
      "channels:\n  - id: np\n    handle: '@np'\n    name: NP\n    search_query: q\n    pipeline: np\n    enabled: true\n");
    await writeFile(join(sroot, "config/pipelines/np.yaml"),
      "name: np\nmodel: m\nmax_turns: 5\nallowed_tools: [Write, Read]\n" +
      "prompt:\n  template: prompts/eason/main.md\n  references: []\n" +
      "post:\n  pdf: false\n  notify: false\n");
    let picksClaude = 0;
    const r = await runPipeline("np", {
      studioRoot: sroot, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) => {
        if (file.endsWith("fake-claude.sh")) return spawnProc(file, args, opts);
        if (file === "claude") picksClaude++;
        return { code: 0 };
      },
    });
    expect(r.status).toBe("succeeded");
    expect(picksClaude).toBe(0);                       // no picks step
    expect(r.progress).toEqual({
      digest: "skipped", analysis: "done", postprocess: "done", quality: "done",
    });
  });
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts -t "no-picks"`
Expected: FAIL (current code unconditionally reads `cfg.picksPrompt` / runs picks → throws or issues a claude call).

- [ ] **Step 3: Patch `studio/lib/runner/runPipeline.ts`.**

(a) Snapshot hash (line ~26-27) — make picks conditional:

```ts
  const snap = { gitSha: gitSha(o.studioRoot),
    promptHashes: hashAll(cfg.picksPrompt
      ? { main: cfg.promptTemplate, picks: cfg.picksPrompt }
      : { main: cfg.promptTemplate }) };
```

(b) The postProcess block (lines ~83-95) — build picks prompt only when configured and tell postProcess whether to run picks:

```ts
    await setProgress({ postprocess: "running" });
    const hasPicks = !!(cfg.pipeline.post.picks && cfg.picksPrompt);
    const picksPrompt = hasPicks
      ? buildPrompt({
          promptTemplate: cfg.picksPrompt!, references: [],
          channel: cfg.channel, calendarText: cal.text,
          htmlPath: cr.htmlPath, logPath: claudeLogPath, dateIso: cal.iso,
        })
      : "";
    const pp = await postProcess({
      htmlPath: cr.htmlPath, financeRoot,
      post: { ...cfg.pipeline.post, notify: o.notify ?? cfg.pipeline.post.notify },
      runPicks: hasPicks, picksPrompt, spawner: o.spawner,
      mcpConfigPath: o.mcpConfigPath,
      allowedTools: o.allowedTools,
    });
```

- [ ] **Step 4: Patch `studio/lib/runner/postProcess.ts`** so an absent `post.picks` cannot crash. Change the picks block:

```ts
  if (a.runPicks && a.post.picks && a.picksPrompt) {
    const picksArgs = [
      "-p", a.picksPrompt,
      "--model", a.post.picks.model,
      ...(a.mcpConfigPath ? ["--mcp-config", a.mcpConfigPath, "--strict-mcp-config"] : []),
      ...(a.allowedTools && a.allowedTools.length
        ? ["--allowedTools", a.allowedTools.join(",")] : []),
    ];
    const { code } = await a.spawner("claude", picksArgs, { cwd: a.financeRoot });
    res.picksOk = code === 0;
  }
```

(`a.post.picks` is now optionally typed via the schema change — `a.post.picks.model` is guarded by the `&& a.post.picks` above.)

- [ ] **Step 5: Run tests + full suite + types**

Run: `cd studio && npx vitest run && npx tsc --noEmit`
Expected: ALL pass (the new no-picks test + every existing test incl Eason fake-CLI runs). tsc fully clean now (Tasks 1-4 resolved all the optional-picks fallout). If anything else is red, stop and report.

- [ ] **Step 6: Commit + push**

```bash
git add studio/lib/runner/runPipeline.ts studio/lib/runner/postProcess.ts studio/lib/runner/runPipeline.test.ts
git commit -m "feat(runner): skip picks stage when pipeline declares no post.picks (multi-analyst)"
git push origin main
```

---

### Task 5: /api/runs POST wires MCP + per-pipeline allowed_tools

**Files:**
- Modify: `studio/app/api/runs/route.ts`

No unit test (thin route; existing store/render logic is tested). Gated by tsc + next build + the Task 8 real run.

- [ ] **Step 1: Replace the POST handler** in `studio/app/api/runs/route.ts` (keep imports for GET; add the new ones). New file contents:

```ts
import { NextRequest, NextResponse } from "next/server";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { runPipeline } from "@/lib/runner/runPipeline";
import { spawnProc } from "@/lib/runner/spawnProc";
import { RUNS_ROOT, STUDIO_ROOT } from "@/lib/runner/paths";
import { isRunId } from "@/lib/runner/runRecord";
import { loadConfig } from "@/lib/config/load";
import { renderMcpConfig } from "@/lib/runner/mcpConfig";
import { pipelineAllowedTools } from "@/lib/runner/allowedTools";

export async function POST(req: NextRequest) {
  const { channelId, notify } = await req.json();

  // Resolve the channel's pipeline tool allow-list + render mcp.json (best-effort:
  // if either fails the run still starts and the failure is recorded in run.json).
  let allowedTools: string[] | undefined;
  let mcpConfigPath: string | undefined;
  try {
    const cfg = await loadConfig(channelId, STUDIO_ROOT);
    allowedTools = pipelineAllowedTools(cfg.pipeline);
  } catch { /* loadConfig will throw again inside runPipeline and be recorded */ }
  try {
    mcpConfigPath = await renderMcpConfig({
      mcpDir: join(STUDIO_ROOT, "mcp"),
      envFile: join(STUDIO_ROOT, "../financial-report-system/scripts/.env"),
      dbPath: join(STUDIO_ROOT, "../financial-report-system/data/financial.db"),
      pythonBin: join(STUDIO_ROOT, "mcp/.venv/bin/python"),
      outPath: join(STUDIO_ROOT, "mcp/mcp.json"),
    });
  } catch { /* no MCP config → degraded run, still recorded */ }

  void runPipeline(channelId, {
    studioRoot: STUDIO_ROOT, runsRoot: RUNS_ROOT, notify,
    spawner: spawnProc, mcpConfigPath, allowedTools,
  }).catch(() => {});
  return NextResponse.json({ started: true });
}

export async function GET() {
  let ids: string[] = [];
  try { ids = await readdir(RUNS_ROOT); } catch { /* none yet */ }
  return NextResponse.json({ runs: ids.filter(isRunId).sort().reverse() });
}
```

- [ ] **Step 2: Verify build + types**

Run: `cd studio && npx tsc --noEmit && npx next build`
Expected: tsc clean; `next build` succeeds (all routes compile).

- [ ] **Step 3: Functional smoke (no full run).** Free port + fresh build + start, then assert the POST is accepted and a run dir with progress appears within ~90s (digest pass running), then stop. (This proves MCP wiring doesn't break the route; full quality is Task 8.)

```bash
cd /Users/pochenkuo/AI/new_financial-report-system/studio
lsof -ti tcp:3100 | xargs kill -9 2>/dev/null; pkill -9 -f next-server 2>/dev/null; sleep 1
npx next build >/dev/null 2>&1 && (npx next start -p 3100 >/tmp/t5.log 2>&1 &) ; sleep 9
curl -s -X POST http://localhost:3100/api/runs -H 'content-type: application/json' -d '{"channelId":"eason"}'
sleep 75
RID=$(curl -s http://localhost:3100/api/runs | python3 -c "import sys,json;print(json.load(sys.stdin)['runs'][0])")
curl -s "http://localhost:3100/api/runs/$RID" | python3 -c "import sys,json;d=json.load(sys.stdin);print('status',d.get('status'),'progress',d.get('progress'))"
lsof -ti tcp:3100 | xargs kill -9 2>/dev/null; pkill -9 -f next-server 2>/dev/null
```

Expected: `{"started":true}`; then a real run dir whose `progress.digest` is `running` or `done` (proves the route now drives an MCP-wired run). Record the output. (Leave the spawned run to finish/clean on its own; do not wait.)

- [ ] **Step 4: Commit + push**

```bash
git add studio/app/api/runs/route.ts
git commit -m "fix(api): /api/runs POST renders mcp.json + passes per-pipeline allowed_tools (multi-analyst)"
git push origin main
```

---

### Task 6: 游庭皓 pipeline (config + prompts only — proves zero-code extensibility)

**Files:**
- Create: `studio/config/pipelines/yutinghao.yaml`
- Create: `studio/prompts/yutinghao/{main,framework,voice,digest,transcript}.md`
- Modify: `studio/config/channels.yaml`
- Test: `studio/lib/config/load.test.ts` (append a load test for the real yutinghao pipeline)

- [ ] **Step 1: Create `studio/config/pipelines/yutinghao.yaml`:**

```yaml
name: yutinghao
model: claude-sonnet-4-6
max_turns: 50
allowed_tools:
  - mcp__yt-dlp__ytdlp_search_videos
  - mcp__yt-dlp__ytdlp_download_transcript
  - mcp__yt-dlp__ytdlp_transcript_page
  - mcp__twse__twse_fmtqik
  - mcp__twse__twse_mi_index
  - mcp__yahoo-finance__yahoo_quote
  - mcp__fred__fred_get_series
  - Write
  - Read
prompt:
  template: prompts/yutinghao/main.md
  references:
    - prompts/yutinghao/framework.md
    - prompts/yutinghao/voice.md
    - prompts/yutinghao/transcript.md
post:
  pdf: true
  notify: false
digest:
  model: claude-sonnet-4-6
  prompt: prompts/yutinghao/digest.md
quality_sections:
  - "市場快照"
  - "總經觀點"
  - "關鍵數據"
  - "風險"
  - "報告總結"
```

- [ ] **Step 2: Create the five prompt files** under `studio/prompts/yutinghao/`.

`main.md`:

```markdown
/eason-analysis

{{calendar}}

你要產出的是「游庭皓 總經視角」報告（**不是** Eason 台股實戰報告）。完成分析後產出一份完整 HTML 報告，使用以下 CSS：
{{report_css}}
儲存到 ${HTML_FILE}。報告標題為「游庭皓 總經視角：每日財經速解讀 ${DATE}」。

逐字稿精華已由前置步驟產生，依 `prompts/yutinghao/transcript.md` 的規則用 `Read` 讀取 ${TRANSCRIPT_DIGEST}。

報告結構強制要求（缺一即不合格，依序）：
- **市場快照**：用即時數據（TWSE 加權/主要指數、Yahoo ^TWII/^SOX/^IXIC、FRED T10Y2Y）列觀察事實，不加因果。
- **總經觀點**：游庭皓今日對美國/台灣/全球總經的判斷（由上而下），僅依逐字稿。
- **關鍵數據**：他實際引用或點評的總經數據（CPI/PCE/NFP/Fed/GDP/PMI/殖利率/外資/景氣燈號…），逐條列出+他的解讀。
- **風險**：他提到的總經與市場風險、資產配置傾向。
- **報告總結**：今日整體基調（偏多/中性/偏謹慎）、信心、3–5 條關鍵訊號、對隔日觀察重點。**必須實際寫進 HTML，不可只放在對話輸出。**

寫作原則（嚴格遵守）：
- **禁止編造因果**：不可寫「因為X所以Y」「主戰場」這類未經證實因果；只寫觀察事實（例「T10Y2Y 從 +0.15 升至 +0.22」）。
- **只引用游庭皓實際說過的話**：立場、數據解讀、配置建議都從逐字稿萃取，不要腦補。
- 原因不明 → 明確寫「**原因不明，持續觀察**」。
- 游庭皓**不做個股選股**；不要產生選股清單或推薦個股，那不是他的風格。
```

`framework.md`:

```markdown
# 游庭皓 分析框架（總經由上而下）

游庭皓（財經皓角）的方法是 **top-down 總經結構分析、數據導向、中性偏謹慎、偏中長期**。報告的邏輯鏈依此展開：

1. **美國總經**：Fed 利率路徑與前瞻指引、CPI/PCE 通膨、NFP 就業、GDP、ISM PMI、長短天期殖利率（T10Y2Y）、美債/資金流向。
2. **台灣總經**：台灣央行政策、出口/外銷訂單、景氣燈號、GDP、CPI。
3. **全球與供應鏈**：地緣政治、半導體景氣循環、匯率與資金流向。
4. **市場與類股**：台股大盤與類股趨勢、外資買賣超、ETF 與資產配置含意。
5. **風險與配置**：把上面推導成「整體偏多/中性/偏謹慎」與資產配置傾向。

常引用數據：US — CPI, PCE, Nonfarm, Fed Funds Rate, GDP, ISM PMI, T10Y2Y；TW — TAIEX, 外資買賣超, GDP, CPI, 外銷訂單, 景氣燈號。

每一層只寫「他實際說了什麼 + 他引用的數字」，不要替他延伸或編因果。
```

`voice.md`:

```markdown
# 游庭皓 語氣與立場規範

- 語氣：理性、數據導向、系統化、**中性偏謹慎**；不喊單、不情緒化。
- 視角：總經由上而下、偏中長期；關注風險與資產配置，**不做個股選股、不偏多**（這點與 Eason 相反，不可混用 Eason 的偏多選股口吻）。
- 立場分數/基調只能反映他逐字稿中的實際傾向；模稜兩可就寫「中性」。
- 不製造「今日語錄」式金句包裝；用「他指出 / 他認為 / 他提醒」客觀轉述。
- 嚴禁腦補因果或把總經觀點翻譯成個股操作建議。
```

`digest.md`:

```markdown
# 逐字稿濃縮任務（前置步驟，務必完成並寫檔）

唯一任務：把游庭皓今日影片的完整逐字稿，濃縮成忠實、結構化的摘要，用 `Write` 寫入：
```
${TRANSCRIPT_DIGEST}
```

## 步驟
1. `mcp__yt-dlp__ytdlp_search_videos(query="{{channel.search_query}}", maxResults=2, uploadDateFilter="today")` 找今日影片；無新片用最近一支。
2. 每支影片從 `page=0` 起呼叫 `mcp__yt-dlp__ytdlp_transcript_page(video_url="<url>", page=<n>, page_size=12000)`，讀 `total_pages`，**逐頁讀到 `page==total_pages-1`**，心中串接完整逐字稿。
3. 依下方 schema 寫入 ${TRANSCRIPT_DIGEST}。

## 摘要 schema（嚴格照寫）
```
# 逐字稿摘要（{{calendar}}）

## 影片清單
- 標題 ｜ video_id ｜ url ｜ 逐字稿來源(captions/gemma4:e4b/none) ｜ 完整字元數

## 游庭皓總體立場
（偏多／中性／偏謹慎 + 1–2 句理由，僅依逐字稿）

## 關鍵總經數據與解讀
- <數據名>：<他引用的數字/變化> → <他的解讀>（逐條，只列他實際講的）

## 風險點
- （他實際提到的總經/市場風險，逐條）

## 資產配置與操作傾向
- （他對資產類別/大盤/類股的傾向；不是個股選股）

## 關鍵原話逐字引用
> 「（從逐字稿原文逐字複製，不可改寫、不可翻譯、不可潤飾）」
（5–10 句）
```

## 忠實度鐵則（違反即失敗）
- 只能萃取逐字稿真實出現的內容；嚴禁臆測、補充、合理推論他沒講的數字或結論。
- 不確定 → 省略。原話必須逐字。
- 即使逐字稿 source=none 或抓不到，**仍要 Write 出檔案**：影片清單標「逐字稿不可用」，其餘節寫「（逐字稿不可用）」。

## 限制
- 本輪只允許 `mcp__yt-dlp__*` 與 `Write`、`Read`。禁止其他工具、禁止產生報告/HTML。完成 Write 即結束。
```

`transcript.md`:

```markdown
# 逐字稿取得規則（嚴格遵守）

逐字稿精華已由前置步驟產生並存檔。**禁止**自己下載逐字稿。

## 唯一正確做法
用 `Read` 讀取：
```
${TRANSCRIPT_DIGEST}
```
該檔即本次分析的逐字稿依據：

| 摘要區塊 | 用途 |
|----------|------|
| 游庭皓總體立場 | 報告整體基調（偏多/中性/偏謹慎） |
| 關鍵總經數據與解讀 | 「關鍵數據」段落 |
| 風險點 | 「風險」段落 |
| 資產配置與操作傾向 | 「總經觀點」「風險」段落（不是個股選股） |
| 關鍵原話逐字引用 | 報告中客觀轉述其觀點時的依據 |

## 絕對禁止
- 禁止呼叫任何 `mcp__yt-dlp__*` 或自行下載逐字稿。
- 禁止用 Bash/python/shell 讀任何 .vtt/.srt/.txt。
- 禁止因「逐字稿無法讀取」而降低信心值——摘要檔案即全部所需。

## 摘要不可用時
只有當 ${TRANSCRIPT_DIGEST} 的「影片清單」標註「逐字稿不可用」時，才退回「僅依即時數據＋影片標題」分析並於報告標明信心降低；否則必須充分使用摘要。
```

- [ ] **Step 3: Enable the channel** — in `studio/config/channels.yaml` change the `yutinghao` entry's `pipeline: eason` → `pipeline: yutinghao` and `enabled: false` → `enabled: true`. Leave the `eason` entry untouched.

- [ ] **Step 4: Append a load test** to `studio/lib/config/load.test.ts`:

```ts
it("loads the real yutinghao pipeline (no picks, has digest, declares allowed_tools)", async () => {
  const c = await loadConfig("yutinghao", ROOT);
  expect(c.pipeline.name).toBe("yutinghao");
  expect(c.pipeline.post.picks).toBeUndefined();
  expect(c.picksPrompt).toBeUndefined();
  expect(c.pipeline.allowed_tools.length).toBeGreaterThan(0);
  expect(typeof c.digestPrompt).toBe("string");
  expect(c.promptTemplate).toContain("游庭皓");
});
```

(Uses the existing `ROOT` constant = `new URL("../../", import.meta.url).pathname` already defined in load.test.ts.)

- [ ] **Step 5: Run tests + types + build**

Run: `cd studio && npx vitest run && npx tsc --noEmit && npx next build`
Expected: ALL green (the new yutinghao load test + every existing test, incl Eason). next build ok. No `.ts`/`.tsx` file should reference "yutinghao"/"游庭皓" (extensibility proof — config+prompts only).

Verify the zero-code claim:
Run: `cd studio && grep -rn "yutinghao\|游庭皓" lib app components --include=*.ts --include=*.tsx | grep -v node_modules | grep -v .next | grep -vi test`
Expected: NO matches (only config/prompts + tests mention it).

- [ ] **Step 6: Commit + push**

```bash
git add studio/config/pipelines/yutinghao.yaml studio/prompts/yutinghao studio/config/channels.yaml studio/lib/config/load.test.ts
git commit -m "feat(config): add 游庭皓 standalone macro pipeline (config+prompts only, zero TS) (multi-analyst)"
git push origin main
```

---

### Task 7: Canvas analyst selector

**Files:**
- Modify: `studio/components/canvas/RunBar.tsx`, `studio/app/page.tsx`

No unit test (React); gated by tsc + next build + full vitest staying green + Task 8.

- [ ] **Step 1: Replace `studio/components/canvas/RunBar.tsx`** with (adds a `<select>` of enabled channels; RunBar owns the selection; drops the required `channelId` prop):

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import type { RunProgress } from "@/app/canvas/nodes";

interface RunStatus { id: string; status?: string; qualityOk?: boolean; progress?: RunProgress; }
interface Ch { id: string; name: string; enabled: boolean; }

export function RunBar({ onActive }:
  { onActive?: (s: { status?: string; progress?: RunProgress }) => void }) {
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [busy, setBusy] = useState(false);
  const [channels, setChannels] = useState<Ch[]>([]);
  const [sel, setSel] = useState<string>("");

  useEffect(() => {
    fetch("/api/channels").then((r) => r.json()).then((j) => {
      const enabled: Ch[] = (j.channels ?? []).filter((c: Ch) => c.enabled);
      setChannels(enabled);
      setSel((s) => s || enabled[0]?.id || "");
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    const ids: string[] = (await (await fetch("/api/runs")).json()).runs ?? [];
    const top = ids.slice(0, 5);
    const detailed = await Promise.all(top.map(async (id) => {
      try {
        const r = await (await fetch(`/api/runs/${encodeURIComponent(id)}`)).json();
        return { id, status: r.status, qualityOk: r.qualityOk, progress: r.progress } as RunStatus;
      } catch { return { id } as RunStatus; }
    }));
    setRuns(detailed);
    const newest = detailed.find((d) => d.status) ?? detailed[0];
    if (newest && onActive) onActive({ status: newest.status, progress: newest.progress });
  }, [onActive]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => {
      if (runs[0]?.status === "running" || runs[0]?.status === "pending") void load();
    }, 4000);
    return () => clearInterval(t);
  }, [runs, load]);

  const trigger = async () => {
    if (!sel) return;
    setBusy(true);
    try {
      await fetch("/api/runs", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ channelId: sel }),
      });
      setTimeout(() => { void load(); setBusy(false); }, 2000);
    } catch { setBusy(false); }
  };

  const color = (s?: string, q?: boolean) =>
    s === "succeeded" ? (q ? "#15803d" : "#b45309")
    : s === "failed" ? "#b91c1c" : s === "running" ? "#2563eb" : "#6b7280";

  const newest = runs.find((d) => d.status) ?? runs[0];
  const inFlight = newest?.status === "running" || newest?.status === "pending";
  const disabled = busy || inFlight || !sel;

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 12px",
      borderBottom: "1px solid #30363d", fontSize: 13, color: "#cbd5e1" }}>
      <select value={sel} onChange={(e) => setSel(e.target.value)}
        disabled={busy || inFlight}
        style={{ background: "#0d1117", color: "#e5e7eb", border: "1px solid #374151",
          borderRadius: 6, padding: "5px 8px", fontSize: 13 }}>
        {channels.length === 0 && <option value="">（無啟用頻道）</option>}
        {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <button onClick={() => void trigger()} disabled={disabled}
        style={{ background: disabled ? "#374151" : "#2563eb", color: "#fff", border: 0,
          borderRadius: 6, padding: "6px 14px", cursor: disabled ? "default" : "pointer" }}>
        {busy ? "啟動中…" : inFlight ? "● 跑中…" : `▶ Run ${sel || "?"}`}
      </button>
      <button onClick={() => void load()} style={{ background: "transparent",
        color: "#9ca3af", border: "1px solid #374151", borderRadius: 6, padding: "5px 10px" }}>
        ⟳
      </button>
      <span style={{ color: "#9ca3af" }}>最近：</span>
      {runs.length === 0 && <span style={{ color: "#6b7280" }}>（無）</span>}
      {runs.map((r) => (
        <span key={r.id} title={r.id} style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: color(r.status, r.qualityOk) }} />
          <code style={{ fontSize: 11 }}>{r.id.slice(11, 19)}</code>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {r.status ?? "?"}{r.status === "succeeded" ? (r.qualityOk ? " · qOK" : " · q✗") : ""}
          </span>
        </span>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Update `studio/app/page.tsx`** — change the RunBar usage line from `<RunBar channelId="eason" onActive={onActive} />` to `<RunBar onActive={onActive} />` (remove the hardcoded prop; everything else in page.tsx unchanged).

- [ ] **Step 3: Verify build + types + full suite**

Run: `cd studio && npx tsc --noEmit && npx next build && npx vitest run`
Expected: tsc clean; next build ok (the `/` page compiles); full vitest still green (no lib/test changed).

- [ ] **Step 4: Commit + push**

```bash
git add studio/components/canvas/RunBar.tsx studio/app/page.tsx
git commit -m "feat(canvas): analyst selector — run any enabled channel (multi-analyst)"
git push origin main
```

---

### Task 8: 游庭皓 confirming run + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

Operational (controller-run). Goal: prove (a) a real 游庭皓 run produces a genuine macro briefing, (b) Eason still works (regression), (c) extensibility claim held.

- [ ] **Step 1:** Free port 3100, fresh `npx next build`, `npx next start -p 3100`.

- [ ] **Step 2:** `POST /api/runs {channelId:"yutinghao"}`. Poll `/api/runs/<newest>` for progress transitions (digest→analysis…). The run takes ~15 min; you must wait for terminal (succeeded/failed) to inspect the report — use a long-lived background waiter (same pattern as prior FU confirming runs), not inline polling.

- [ ] **Step 3:** On terminal, verify against ground truth (no glossing):
  - `studio/runs/<id>/report.html` exists, title contains 游庭皓, has the 5 sections (市場快照/總經觀點/關鍵數據/風險/報告總結), and the macro content cites real data (FRED/TWSE/Yahoo) and is transcript-driven (digest consumed; `transcript-digest.md` non-trivial with his stance/data/quotes).
  - NO eason_picks/DB writes attempted (none expected — assert the run did not error on missing picks; `progress.postprocess` = done; status succeeded; qualityOk reflects his quality_sections).
  - Then trigger one `eason` run the same way and confirm it still succeeds with its normal sections (regression check) — capturing at least the live progress + a succeeded status is sufficient (the Eason quality path is already proven in FU-1..6; here we only need "not regressed by the refactor").
- [ ] **Step 4:** Append a dated **"Multi-analyst + 游庭皓 (v1)"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md`: what was verified for 游庭皓 (sections, real data, transcript-driven), the Eason regression check, the extensibility proof (the grep showing zero TS references to the analyst), and honest limitations (canvas 持久化 node not meaningful for 游庭皓; visual selector needs a human eyeball; combined briefing still future). Restore any test mutations; clean tree. Commit + push. KG `record_experience`. Remove any temp launcher/log files.

---

## Self-Review

**1. Spec coverage:** §3 schema generalisation → Task 1 (picks/judge optional, allowed_tools) + Task 2 (per-pipeline tools) + Task 3 (pipelineStore from channels) + Task 4 (runPipeline/postProcess skip picks); §3 `/api/runs` MCP wiring → Task 5; §4 游庭皓 pipeline/prompts/channels → Task 6; §5 canvas selector → Task 7; §7 testing spread across tasks; §8 delivery + confirming run → Task 8. All covered. Eason regression guarded by "full vitest green" gates in Tasks 4/6/7 + Task 8 explicit Eason re-run.

**2. Placeholder scan:** No TBD/TODO; every code/step is complete; prompt files given verbatim; exact commands + expected results.

**3. Type consistency:** `allowed_tools` added to `PipelineFile` (Task 1) and consumed as `cfg.pipeline.allowed_tools` (Tasks 2,5,6 tests). `pipelineAllowedTools(pipeline)` signature consistent (Task 2 def + Task 5 use). `digestAllowedTools(all?)` unchanged signature; `digestPass` already calls it with `a.allowedTools` — unaffected. `picksPrompt?`/`judgeRubric?` optional in `LoadedConfig` (Task 1) and guarded in runPipeline (Task 4 `cfg.picksPrompt!` under `hasPicks`) + postProcess (`a.post.picks &&`). `pipelineStore` fns become async-returning (already awaited by the `[name]` route — Task 3 Step 4 verifies). RunBar's `channelId` prop removed (Task 7) and the sole caller `page.tsx` updated in the same task — no dangling prop. Cross-task ordering: Tasks 1→2→3→4 leave tsc transiently red (documented as expected per task); Task 4 Step 5 requires fully-clean tsc + full green suite, catching any inconsistency before the feature tasks.

**Open risks (flagged):** (a) `/api/runs` renderMcpConfig path assumptions (`../financial-report-system/scripts/.env`, `mcp/.venv/bin/python`) match what the proven ad-hoc launcher used; if `.env`/venv move, the route degrades gracefully (best-effort try/catch) rather than crashing — Task 5 smoke + Task 8 real run validate it. (b) 游庭皓 prompt quality is judged by the Task 8 confirming run; if his report is thin, that's a prompt-tightening follow-up, not a design flaw — the extensibility machinery (the actual deliverable) is proven by Tasks 1–7 + the zero-TS grep. (c) Eason regression: the schema/runner changes are additive/optional; every code task ends on a full green vitest incl the Eason fake-CLI e2e, and Task 8 re-runs Eason for real.
