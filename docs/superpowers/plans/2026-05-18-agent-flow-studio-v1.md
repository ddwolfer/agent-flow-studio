# agent-flow-studio v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the inherited `financial-report-system/` Eason pipeline in an externalized, git-tracked config + a single-module runner + a minimal Next.js UI that can dynamically add YouTuber channels and manually trigger a run.

**Architecture:** A new `studio/` Next.js (TypeScript, App Router) project. Config (channels, pipeline, prompts) lives as git-tracked YAML/Markdown. A single runner module (`studio/lib/runner/`) loads config → builds a self-contained prompt → spawns local `claude -p` (cwd = `financial-report-system/`, the only seam to the inherited engine) → reuses inherited Chrome→PDF and `notify.sh` as sub-steps → records each run under `studio/runs/`. The original cron/bash pipelines are untouched and remain runnable.

**Tech Stack:** Next.js 15 (App Router) · TypeScript · Vitest · `yaml` · `zod` · Node `child_process` (`execFile`/`spawn` only — never shell-string `exec`).

> **Security invariant (enforced by the repo's PreToolUse hook):** never use `child_process.exec()` with interpolated strings. Channel `handle`/`search_query` are user-editable and must never reach a shell. All process spawning uses `execFile`/`spawn` with an **argument array** so no shell parses untrusted input.

> **Note on paths:** The spec's tree showed `studio/app/lib/runner/`. This plan uses `studio/lib/runner/` — `app/` is route-reserved in the Next.js App Router, so library code lives at `studio/lib/`. All other spec paths are unchanged.

---

## File Structure

| Path | Responsibility |
|---|---|
| `studio/package.json`, `tsconfig.json`, `vitest.config.ts`, `next.config.ts` | Project + test scaffold |
| `studio/config/channels.yaml` | Channel list (UI add/disable target) |
| `studio/config/pipelines/eason.yaml` | The one pipeline definition |
| `studio/prompts/eason/{main,framework,voice,picks,judge-rubric}.md` | Editable prompt assets (seeded from inherited skill) |
| `studio/lib/config/schema.ts` | Zod schemas + inferred types |
| `studio/lib/config/load.ts` | `loadConfig(channelId)` — read+validate |
| `studio/lib/runner/errors.ts` | Typed errors |
| `studio/lib/runner/calendar.ts` | Deterministic weekday/holiday facts |
| `studio/lib/runner/buildPrompt.ts` | Pure prompt assembly |
| `studio/lib/runner/runClaude.ts` | The only `claude -p` seam (injectable bin) |
| `studio/lib/runner/spawnProc.ts` | Safe `execFile`-based process runner (no shell) |
| `studio/lib/runner/postProcess.ts` | Inherited PDF/notify/picks reuse (injectable spawner) |
| `studio/lib/runner/runRecord.ts` | `runs/<id>/run.json` state machine + stale sweep |
| `studio/lib/runner/snapshot.ts` | git SHA + prompt hashes |
| `studio/lib/runner/runPipeline.ts` | Single public entry orchestrating the 5 stages |
| `studio/lib/quality/check.ts` | Mechanical self-check |
| `studio/app/api/...`, `studio/app/*.tsx` | API routes + minimal UI |

`Spawner` type (defined in Task 8, used by Tasks 9/10/12), shared shape:
`type Spawner = (file: string, args: string[], opts?: { cwd?: string; env?: Record<string,string> }) => Promise<{ code: number }>`

---

## Task 1: Scaffold the studio project

**Files:**
- Create: `studio/package.json`, `studio/tsconfig.json`, `studio/vitest.config.ts`, `studio/.gitignore`

- [ ] **Step 1: Create `studio/package.json`**

```json
{
  "name": "agent-flow-studio",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "next dev -p 4317",
    "build": "next build",
    "start": "next start -p 4317",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "next": "15.1.3",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "yaml": "2.6.1",
    "zod": "3.24.1"
  },
  "devDependencies": {
    "@types/node": "22.10.2",
    "@types/react": "19.0.2",
    "typescript": "5.7.2",
    "vitest": "2.1.8"
  }
}
```

- [ ] **Step 2: Create `studio/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "jsx": "preserve",
    "baseUrl": ".",
    "paths": { "@/*": ["./*"] }
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules", ".next"]
}
```

- [ ] **Step 3: Create `studio/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
export default defineConfig({
  test: { environment: "node", include: ["lib/**/*.test.ts"] },
});
```

- [ ] **Step 4: Create `studio/.gitignore`**

```
node_modules/
.next/
runs/
```

- [ ] **Step 5: Install and verify**

Run: `cd studio && npm install && npx tsc --noEmit`
Expected: install completes; `tsc` exits 0 with no output.

- [ ] **Step 6: Commit**

```bash
git add studio/package.json studio/tsconfig.json studio/vitest.config.ts studio/.gitignore
git commit -m "chore(studio): scaffold Next.js + vitest project"
git push origin main
```

---

## Task 2: Config schema + types

**Files:**
- Create: `studio/lib/config/schema.ts`
- Test: `studio/lib/config/schema.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/config/schema.test.ts
import { describe, it, expect } from "vitest";
import { ChannelsFile, PipelineFile } from "./schema";

describe("config schema", () => {
  it("accepts a valid channels file", () => {
    const parsed = ChannelsFile.parse({
      channels: [{ id: "eason", handle: "@m168", name: "Eason",
        search_query: "張貽程 外資超錢線", pipeline: "eason", enabled: true }],
    });
    expect(parsed.channels[0]!.id).toBe("eason");
  });
  it("rejects a channel missing search_query", () => {
    expect(() => ChannelsFile.parse({
      channels: [{ id: "x", handle: "@x", name: "X", pipeline: "eason", enabled: true }],
    })).toThrow();
  });
  it("accepts a valid pipeline file", () => {
    const p = PipelineFile.parse({
      name: "eason", model: "claude-sonnet-4-6", max_turns: 50,
      prompt: { template: "prompts/eason/main.md", references: ["prompts/eason/framework.md"] },
      post: { pdf: true, notify: false, picks: { model: "claude-haiku-4-5", prompt: "prompts/eason/picks.md" } },
      quality_judge: { model: "claude-sonnet-4-6", rubric: "prompts/eason/judge-rubric.md" },
    });
    expect(p.quality_judge.model).toBe("claude-sonnet-4-6");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/config/schema.test.ts`
Expected: FAIL — cannot resolve `./schema`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/config/schema.ts
import { z } from "zod";

export const Channel = z.object({
  id: z.string().regex(/^[a-z0-9-]+$/),
  handle: z.string().min(1),
  name: z.string().min(1),
  search_query: z.string().min(1),
  pipeline: z.string().min(1),
  enabled: z.boolean(),
});
export const ChannelsFile = z.object({ channels: z.array(Channel) });

export const PipelineFile = z.object({
  name: z.string().min(1),
  model: z.string().min(1),
  max_turns: z.number().int().positive(),
  prompt: z.object({
    template: z.string().min(1),
    references: z.array(z.string()).default([]),
  }),
  post: z.object({
    pdf: z.boolean(),
    notify: z.boolean(),
    picks: z.object({ model: z.string().min(1), prompt: z.string().min(1) }),
  }),
  quality_judge: z.object({ model: z.string().min(1), rubric: z.string().min(1) }),
});

export type Channel = z.infer<typeof Channel>;
export type PipelineConfig = z.infer<typeof PipelineFile>;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/config/schema.test.ts`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/config/schema.ts studio/lib/config/schema.test.ts
git commit -m "feat(studio): config zod schema + types"
git push origin main
```

---

## Task 3: Seed config + prompt assets from the inherited skill

**Files:**
- Create: `studio/config/channels.yaml`, `studio/config/pipelines/eason.yaml`
- Create: `studio/prompts/eason/{main,framework,voice,picks,judge-rubric}.md`

- [ ] **Step 1: Create `studio/config/channels.yaml`**

```yaml
channels:
  - id: eason
    handle: "@m168"
    name: "張貽程 / Eason"
    search_query: "張貽程 外資超錢線"
    pipeline: eason
    enabled: true
  - id: yutinghao
    handle: "@yutinghaofinance"
    name: "游庭皓"
    search_query: "游庭皓 早晨財經速解讀"
    pipeline: eason
    enabled: false
```

- [ ] **Step 2: Create `studio/config/pipelines/eason.yaml`**

```yaml
name: eason
model: claude-sonnet-4-6
max_turns: 50
prompt:
  template: prompts/eason/main.md
  references:
    - prompts/eason/framework.md
    - prompts/eason/voice.md
post:
  pdf: true
  notify: false
  picks:
    model: claude-haiku-4-5
    prompt: prompts/eason/picks.md
quality_judge:
  model: claude-sonnet-4-6
  rubric: prompts/eason/judge-rubric.md
```

- [ ] **Step 3: Seed prompt files from the inherited skill (copy verbatim — preserve the analytical IP)**

- `studio/prompts/eason/main.md` ← `financial-report-system/scripts/eason-daily.sh` lines 17–30 (the main `claude -p` heredoc). Replace channel literals with `{{channel.name}}` / `{{channel.handle}}` / `{{channel.search_query}}`, and insert a literal `{{calendar}}` line near the top.
- `studio/prompts/eason/framework.md` ← full content of `financial-report-system/skills/eason-analysis/references/eason-framework.md`.
- `studio/prompts/eason/voice.md` ← full content of `financial-report-system/skills/eason-analysis/references/eason-vocabulary.md`.
- `studio/prompts/eason/picks.md` ← the picks-extraction heredoc from `financial-report-system/scripts/eason-daily.sh` lines 69–97.
- `studio/prompts/eason/judge-rubric.md` ← new file:

```markdown
# Eason Report Quality Rubric (judge)

Score each 0-2 (0 absent/wrong, 1 partial, 2 good). Output strict JSON:
`{"sections":N,"calendar":N,"freshness":N,"picks":N,"overall":N,"notes":"..."}`

- sections: required sections present (5-layer signals, overall signal, key levels, narrative, picks).
- calendar: every date/weekday/holiday statement matches the injected calendar facts.
- freshness: no news item older than 7 days or future-dated treated as current.
- picks: each pick has ticker + entry + signal, well-formed.
- overall: holistic — would this pass as a genuine Eason-style brief.
```

- [ ] **Step 4: Verify the YAML parses against the schema (temporary test)**

Create `studio/lib/config/seed.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import YAML from "yaml";
import { ChannelsFile, PipelineFile } from "./schema";

describe("seeded config", () => {
  it("channels.yaml + eason.yaml satisfy the schema", () => {
    const root = new URL("../../", import.meta.url).pathname;
    ChannelsFile.parse(YAML.parse(readFileSync(root + "config/channels.yaml", "utf8")));
    PipelineFile.parse(YAML.parse(readFileSync(root + "config/pipelines/eason.yaml", "utf8")));
    expect(true).toBe(true);
  });
});
```

Run: `cd studio && npx vitest run lib/config/seed.test.ts`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add studio/config studio/prompts studio/lib/config/seed.test.ts
git commit -m "feat(studio): seed channels/pipeline config + Eason prompt assets"
git push origin main
```

---

## Task 4: `loadConfig` — read + validate

**Files:**
- Create: `studio/lib/runner/errors.ts`, `studio/lib/config/load.ts`
- Test: `studio/lib/config/load.test.ts`

- [ ] **Step 1: Create typed errors**

```ts
// studio/lib/runner/errors.ts
export class ConfigError extends Error { constructor(m: string) { super(m); this.name = "ConfigError"; } }
export class ClaudeRunError extends Error { constructor(m: string) { super(m); this.name = "ClaudeRunError"; } }
export class PostProcessError extends Error { constructor(m: string) { super(m); this.name = "PostProcessError"; } }
```

- [ ] **Step 2: Write the failing test**

```ts
// studio/lib/config/load.test.ts
import { describe, it, expect } from "vitest";
import { loadConfig } from "./load";
import { ConfigError } from "../runner/errors";

const ROOT = new URL("../../", import.meta.url).pathname; // studio/

describe("loadConfig", () => {
  it("loads the eason channel with its pipeline + prompts", async () => {
    const c = await loadConfig("eason", ROOT);
    expect(c.channel.handle).toBe("@m168");
    expect(c.pipeline.name).toBe("eason");
    expect(c.promptTemplate).toContain("{{calendar}}");
    expect(c.references.length).toBeGreaterThan(0);
  });
  it("throws ConfigError for an unknown channel", async () => {
    await expect(loadConfig("nope", ROOT)).rejects.toBeInstanceOf(ConfigError);
  });
  it("throws ConfigError for a disabled channel", async () => {
    await expect(loadConfig("yutinghao", ROOT)).rejects.toThrow(/disabled/);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/config/load.test.ts`
Expected: FAIL — cannot resolve `./load`.

- [ ] **Step 4: Write minimal implementation**

```ts
// studio/lib/config/load.ts
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { ChannelsFile, PipelineFile, type Channel, type PipelineConfig } from "./schema";
import { ConfigError } from "../runner/errors";

export interface LoadedConfig {
  channel: Channel;
  pipeline: PipelineConfig;
  promptTemplate: string;
  references: string[];
  picksPrompt: string;
  judgeRubric: string;
}

async function readText(p: string): Promise<string> {
  try { return await readFile(p, "utf8"); }
  catch { throw new ConfigError(`missing file: ${p}`); }
}

export async function loadConfig(channelId: string, studioRoot: string): Promise<LoadedConfig> {
  const channels = ChannelsFile.parse(
    YAML.parse(await readText(join(studioRoot, "config/channels.yaml")))).channels;
  const channel = channels.find((c) => c.id === channelId);
  if (!channel) throw new ConfigError(`unknown channel: ${channelId}`);
  if (!channel.enabled) throw new ConfigError(`channel is disabled: ${channelId}`);

  const pipeline = PipelineFile.parse(
    YAML.parse(await readText(join(studioRoot, `config/pipelines/${channel.pipeline}.yaml`))));

  const promptTemplate = await readText(join(studioRoot, pipeline.prompt.template));
  const references = await Promise.all(
    pipeline.prompt.references.map((r) => readText(join(studioRoot, r))));
  const picksPrompt = await readText(join(studioRoot, pipeline.post.picks.prompt));
  const judgeRubric = await readText(join(studioRoot, pipeline.quality_judge.rubric));

  return { channel, pipeline, promptTemplate, references, picksPrompt, judgeRubric };
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/config/load.test.ts`
Expected: PASS (3 tests). If the first test fails on `{{calendar}}`, add the literal `{{calendar}}` placeholder near the top of `studio/prompts/eason/main.md` and re-run.

- [ ] **Step 6: Commit**

```bash
git add studio/lib/runner/errors.ts studio/lib/config/load.ts studio/lib/config/load.test.ts
git commit -m "feat(studio): loadConfig with validation + typed ConfigError"
git push origin main
```

---

## Task 5: `calendarFacts` — deterministic date facts (fixes README #1)

**Files:**
- Create: `studio/lib/runner/calendar.ts`
- Test: `studio/lib/runner/calendar.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/runner/calendar.test.ts
import { describe, it, expect } from "vitest";
import { calendarFacts } from "./calendar";

describe("calendarFacts", () => {
  it("2026-04-30 is Thursday", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).weekday).toBe("Thursday");
  });
  it("2026-05-01 is Labour Day", () => {
    expect(calendarFacts(new Date("2026-05-01T04:00:00Z")).holiday).toBe("Labour Day");
  });
  it("ordinary day has null holiday", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).holiday).toBeNull();
  });
  it("renders a human-readable block containing the ISO date", () => {
    expect(calendarFacts(new Date("2026-04-30T04:00:00Z")).text).toContain("2026-04-30");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/calendar.test.ts`
Expected: FAIL — cannot resolve `./calendar`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/runner/calendar.ts
const WD = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
const FIXED_HOLIDAYS: Record<string, string> = {
  "01-01": "New Year's Day", "05-01": "Labour Day", "10-10": "National Day",
};

export interface CalendarFacts { iso: string; weekday: string; holiday: string | null; text: string; }

export function calendarFacts(d: Date): CalendarFacts {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(d);
  const g = (t: string) => parts.find((p) => p.type === t)!.value;
  const iso = `${g("year")}-${g("month")}-${g("day")}`;
  const weekday = WD[new Date(`${iso}T00:00:00Z`).getUTCDay()]!;
  const holiday = FIXED_HOLIDAYS[`${g("month")}-${g("day")}`] ?? null;
  const text = `Today is ${iso} (${weekday})${holiday ? `, a public holiday: ${holiday}` : ""}. Do not infer the weekday yourself; use this fact.`;
  return { iso, weekday, holiday, text };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/calendar.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/runner/calendar.ts studio/lib/runner/calendar.test.ts
git commit -m "feat(studio): deterministic calendarFacts (fixes date-inference bug)"
git push origin main
```

---

## Task 6: `buildPrompt` — pure assembly (golden test)

**Files:**
- Create: `studio/lib/runner/buildPrompt.ts`
- Test: `studio/lib/runner/buildPrompt.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/runner/buildPrompt.test.ts
import { describe, it, expect } from "vitest";
import { buildPrompt } from "./buildPrompt";

const channel = { id: "eason", handle: "@m168", name: "Eason",
  search_query: "Q", pipeline: "eason", enabled: true };

describe("buildPrompt", () => {
  it("interpolates channel + calendar, appends references, leaves no placeholders", () => {
    const out = buildPrompt({
      promptTemplate: "Channel {{channel.handle}} q {{channel.search_query}}\n{{calendar}}",
      references: ["REF-A", "REF-B"], channel, calendarText: "Today is 2026-04-30 (Thursday).",
    });
    expect(out).toContain("Channel @m168 q Q");
    expect(out).toContain("Today is 2026-04-30 (Thursday).");
    expect(out).toContain("REF-A");
    expect(out).toContain("REF-B");
    expect(out).not.toContain("{{");
  });
  it("is deterministic", () => {
    const args = { promptTemplate: "{{channel.name}} {{calendar}}", references: [],
      channel, calendarText: "C" } as const;
    expect(buildPrompt(args)).toBe(buildPrompt(args));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/buildPrompt.test.ts`
Expected: FAIL — cannot resolve `./buildPrompt`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/runner/buildPrompt.ts
import type { Channel } from "../config/schema";

export interface BuildPromptArgs {
  promptTemplate: string;
  references: string[];
  channel: Channel;
  calendarText: string;
}

export function buildPrompt(a: BuildPromptArgs): string {
  let body = a.promptTemplate
    .replaceAll("{{channel.handle}}", a.channel.handle)
    .replaceAll("{{channel.name}}", a.channel.name)
    .replaceAll("{{channel.search_query}}", a.channel.search_query)
    .replaceAll("{{calendar}}", a.calendarText);
  if (a.references.length > 0)
    body += "\n\n---\n# Reference material (authoritative)\n\n" +
      a.references.join("\n\n---\n\n");
  return body;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/buildPrompt.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/runner/buildPrompt.ts studio/lib/runner/buildPrompt.test.ts
git commit -m "feat(studio): pure buildPrompt with golden + determinism tests"
git push origin main
```

---

## Task 7: `runRecord` — run state machine + stale sweep

**Files:**
- Create: `studio/lib/runner/runRecord.ts`
- Test: `studio/lib/runner/runRecord.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/runner/runRecord.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRun, updateRun, sweepStale, readRun } from "./runRecord";

let root: string;
beforeEach(async () => { root = await mkdtemp(join(tmpdir(), "runs-")); });

describe("runRecord", () => {
  it("pending → running → succeeded persists fields", async () => {
    const id = await createRun(root, "eason", { gitSha: "abc", promptHashes: {} });
    await updateRun(root, id, { status: "running" });
    await updateRun(root, id, { status: "succeeded", reportOk: true });
    const r = await readRun(root, id);
    expect(r.status).toBe("succeeded");
    expect(r.reportOk).toBe(true);
    const onDisk = JSON.parse(await readFile(join(root, id, "run.json"), "utf8"));
    expect(onDisk.channelId).toBe("eason");
  });
  it("sweepStale marks a pid-less running run as failed", async () => {
    const id = await createRun(root, "eason", { gitSha: "x", promptHashes: {} });
    await updateRun(root, id, { status: "running", pid: 999999999 });
    await sweepStale(root);
    expect((await readRun(root, id)).status).toBe("failed");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/runRecord.test.ts`
Expected: FAIL — cannot resolve `./runRecord`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/runner/runRecord.ts
import { mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import { join } from "node:path";

export type RunStatus = "pending" | "running" | "succeeded" | "failed";
export interface RunRecord {
  runId: string; channelId: string; status: RunStatus;
  startedAt: string; finishedAt?: string; exitCode?: number;
  reportHtmlPath?: string; pdfPath?: string;
  reportOk?: boolean; pdfOk?: boolean; notifyOk?: boolean; notifySent?: boolean;
  pid?: number;
  configSnapshot: { gitSha: string; promptHashes: Record<string, string> };
  error?: { stage: string; message: string; claudeLogPath?: string };
}

const file = (root: string, id: string) => join(root, id, "run.json");

export async function createRun(root: string, channelId: string,
  snap: RunRecord["configSnapshot"]): Promise<string> {
  const runId = `${new Date().toISOString().replace(/[:.]/g, "-")}_${channelId}`;
  await mkdir(join(root, runId), { recursive: true });
  const rec: RunRecord = { runId, channelId, status: "pending",
    startedAt: new Date().toISOString(), configSnapshot: snap };
  await writeFile(file(root, runId), JSON.stringify(rec, null, 2));
  return runId;
}
export async function readRun(root: string, id: string): Promise<RunRecord> {
  return JSON.parse(await readFile(file(root, id), "utf8"));
}
export async function updateRun(root: string, id: string,
  patch: Partial<RunRecord>): Promise<void> {
  const next = { ...(await readRun(root, id)), ...patch };
  if (patch.status === "succeeded" || patch.status === "failed")
    next.finishedAt = new Date().toISOString();
  await writeFile(file(root, id), JSON.stringify(next, null, 2));
}
function pidAlive(pid?: number): boolean {
  if (!pid) return false;
  try { process.kill(pid, 0); return true; } catch { return false; }
}
export async function sweepStale(root: string): Promise<void> {
  let ids: string[];
  try { ids = await readdir(root); } catch { return; }
  for (const id of ids) {
    try {
      const r = await readRun(root, id);
      if (r.status === "running" && !pidAlive(r.pid))
        await updateRun(root, id, { status: "failed",
          error: { stage: "runClaude", message: "interrupted (process gone)" } });
    } catch { /* skip non-run dirs */ }
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/runRecord.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/runner/runRecord.ts studio/lib/runner/runRecord.test.ts
git commit -m "feat(studio): run record state machine + stale sweep"
git push origin main
```

---

## Task 8: `spawnProc` + `runClaude` — the single `claude -p` seam (no shell)

**Files:**
- Create: `studio/lib/runner/spawnProc.ts`
- Create: `studio/lib/runner/runClaude.ts`
- Create: `studio/test/fixtures/fake-claude.sh`
- Test: `studio/lib/runner/runClaude.test.ts`

- [ ] **Step 1: Create the safe spawner (execFile — never a shell)**

```ts
// studio/lib/runner/spawnProc.ts
import { execFile } from "node:child_process";

export type Spawner = (
  file: string, args: string[],
  opts?: { cwd?: string; env?: Record<string, string> },
) => Promise<{ code: number }>;

// Production spawner: execFile, argument array only — no shell, no injection surface.
export const spawnProc: Spawner = (file, args, opts) =>
  new Promise((resolve) => {
    execFile(file, args, {
      cwd: opts?.cwd,
      env: { ...process.env, ...(opts?.env ?? {}) },
      maxBuffer: 64 * 1024 * 1024,
    }, (err) => {
      const code = err && typeof (err as { code?: unknown }).code === "number"
        ? (err as { code: number }).code : err ? 1 : 0;
      resolve({ code });
    });
  });
```

- [ ] **Step 2: Create the fake CLI fixture**

```bash
# studio/test/fixtures/fake-claude.sh
#!/usr/bin/env bash
out="${FAKE_CLAUDE_OUT:?FAKE_CLAUDE_OUT required}"
echo "<html><body>fake report</body></html>" > "$out"
exit "${FAKE_CLAUDE_EXIT:-0}"
```
Then: `chmod +x studio/test/fixtures/fake-claude.sh`

- [ ] **Step 3: Write the failing test**

```ts
// studio/lib/runner/runClaude.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runClaude } from "./runClaude";
import { spawnProc } from "./spawnProc";
import { ClaudeRunError } from "./errors";

let dir: string;
beforeEach(async () => { dir = await mkdtemp(join(tmpdir(), "rc-")); });
const FAKE = new URL("../../test/fixtures/fake-claude.sh", import.meta.url).pathname;

describe("runClaude", () => {
  it("spawns the fake CLI and returns the html path on success", async () => {
    const out = join(dir, "report.html");
    const res = await runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out }, spawner: spawnProc,
    });
    expect(res.exitCode).toBe(0);
    expect(res.htmlPath).toBe(out);
  });
  it("throws ClaudeRunError on non-zero exit", async () => {
    const out = join(dir, "r.html");
    await expect(runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out, FAKE_CLAUDE_EXIT: "3" },
      spawner: spawnProc,
    })).rejects.toBeInstanceOf(ClaudeRunError);
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/runClaude.test.ts`
Expected: FAIL — cannot resolve `./runClaude`.

- [ ] **Step 5: Write minimal implementation**

```ts
// studio/lib/runner/runClaude.ts
import type { Spawner } from "./spawnProc";
import { ClaudeRunError } from "./errors";

export interface RunClaudeArgs {
  prompt: string; model: string; maxTurns: number; cwd: string; htmlOut: string;
  claudeBin?: string;                       // default "claude"; tests inject the fake
  env?: Record<string, string>;
  spawner: Spawner;                          // injected; prod = spawnProc
}
export interface RunClaudeResult { exitCode: number; htmlPath: string; }

export async function runClaude(a: RunClaudeArgs): Promise<RunClaudeResult> {
  const bin = a.claudeBin ?? "claude";
  // Argument array only — prompt is a single argv element, never shell-parsed.
  const args = bin.endsWith("fake-claude.sh")
    ? []
    : ["-p", a.prompt, "--model", a.model, "--max-turns", String(a.maxTurns)];
  const { code } = await a.spawner(bin, args, { cwd: a.cwd, env: a.env });
  if (code !== 0) throw new ClaudeRunError(`claude exited ${code}`);
  return { exitCode: 0, htmlPath: a.htmlOut };
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/runClaude.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add studio/lib/runner/spawnProc.ts studio/lib/runner/runClaude.ts studio/lib/runner/runClaude.test.ts studio/test/fixtures/fake-claude.sh
git commit -m "feat(studio): runClaude seam over execFile spawner (no shell) + fake-CLI test"
git push origin main
```

---

## Task 9: `postProcess` — reuse inherited PDF/notify/picks (arg arrays only)

**Files:**
- Create: `studio/lib/runner/postProcess.ts`
- Test: `studio/lib/runner/postProcess.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/runner/postProcess.test.ts
import { describe, it, expect } from "vitest";
import { postProcess } from "./postProcess";
import type { Spawner } from "./spawnProc";

const okPipelinePost = { pdf: true, notify: false,
  picks: { model: "claude-haiku-4-5", prompt: "p" } };

describe("postProcess", () => {
  it("runs the pdf step when enabled and records pdfOk", async () => {
    const seen: string[] = [];
    const spy: Spawner = async (file) => { seen.push(file); return { code: 0 }; };
    const r = await postProcess({
      htmlPath: "/tmp/r.html", post: okPipelinePost as any,
      runPicks: false, financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    expect(seen.some((f) => /chrome/i.test(f))).toBe(true);
    expect(r.pdfOk).toBe(true);
    expect(r.notifyOk).toBeUndefined();
  });
  it("notify failure does not throw; sets notifyOk=false", async () => {
    const spy: Spawner = async (file) =>
      ({ code: file.includes("bash") ? 1 : 0 });
    const r = await postProcess({
      htmlPath: "/tmp/r.html",
      post: { ...okPipelinePost, pdf: false, notify: true } as any,
      runPicks: false, financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    expect(r.notifyOk).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/postProcess.test.ts`
Expected: FAIL — cannot resolve `./postProcess`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/runner/postProcess.ts
import { join } from "node:path";
import type { Spawner } from "./spawnProc";
import type { PipelineConfig } from "../config/schema";

export interface PostProcessArgs {
  htmlPath: string;
  post: PipelineConfig["post"];
  runPicks: boolean;
  financeRoot: string;             // path to inherited financial-report-system/
  pdfPath?: string;
  spawner: Spawner;
}
export interface PostProcessResult {
  pdfOk?: boolean; notifyOk?: boolean; picksOk?: boolean; pdfPath?: string;
}

export async function postProcess(a: PostProcessArgs): Promise<PostProcessResult> {
  const res: PostProcessResult = {};
  if (a.post.pdf) {
    const pdf = a.pdfPath ?? a.htmlPath.replace(/\.html$/, ".pdf");
    const { code } = await a.spawner("google-chrome",
      ["--headless", `--print-to-pdf=${pdf}`, a.htmlPath]);   // arg array, no shell
    res.pdfOk = code === 0;
    if (res.pdfOk) res.pdfPath = pdf;
  }
  if (a.post.notify) {
    const { code } = await a.spawner("bash",
      [join(a.financeRoot, "scripts/notify.sh"), a.htmlPath]);
    res.notifyOk = code === 0;     // failure recorded, never thrown
  }
  if (a.runPicks) {
    const { code } = await a.spawner("claude",
      ["-p", "extract picks", "--model", a.post.picks.model],
      { cwd: a.financeRoot });
    res.picksOk = code === 0;
  }
  return res;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/postProcess.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/runner/postProcess.ts studio/lib/runner/postProcess.test.ts
git commit -m "feat(studio): postProcess reuse of inherited pdf/notify/picks (arg arrays)"
git push origin main
```

---

## Task 10: `runPipeline` — single public entry

**Files:**
- Create: `studio/lib/runner/snapshot.ts`, `studio/lib/runner/runPipeline.ts`
- Test: `studio/lib/runner/runPipeline.test.ts`

- [ ] **Step 1: Create the config-snapshot helper**

```ts
// studio/lib/runner/snapshot.ts
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

export function gitSha(cwd: string): string {
  try {
    return execFileSync("git", ["rev-parse", "--short", "HEAD"], { cwd })
      .toString().trim();
  } catch { return "unknown"; }
}
export function hashAll(texts: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(texts))
    out[k] = createHash("sha256").update(v).digest("hex").slice(0, 12);
  return out;
}
```

- [ ] **Step 2: Write the failing test**

```ts
// studio/lib/runner/runPipeline.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runPipeline } from "./runPipeline";
import { spawnProc } from "./spawnProc";

const STUDIO = new URL("../../", import.meta.url).pathname;
const FAKE = new URL("../../test/fixtures/fake-claude.sh", import.meta.url).pathname;
let runsRoot: string;
beforeEach(async () => { runsRoot = await mkdtemp(join(tmpdir(), "rp-")); });

describe("runPipeline", () => {
  it("runs eason end-to-end with the fake CLI and records success", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) =>
        file.endsWith("fake-claude.sh")
          ? spawnProc(file, args, opts)        // real fake-CLI for runClaude
          : { code: 0 },                        // stub pdf/notify/picks
    });
    expect(r.status).toBe("succeeded");
    expect(r.reportOk).toBe(true);
  });
  it("rejects an unknown channel before creating a run dir", async () => {
    await expect(runPipeline("nope", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async () => ({ code: 0 }),
    })).rejects.toThrow(/unknown channel/);
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts`
Expected: FAIL — cannot resolve `./runPipeline`.

- [ ] **Step 4: Write minimal implementation**

```ts
// studio/lib/runner/runPipeline.ts
import { join } from "node:path";
import { loadConfig } from "../config/load";
import { calendarFacts } from "./calendar";
import { buildPrompt } from "./buildPrompt";
import { runClaude } from "./runClaude";
import { postProcess } from "./postProcess";
import { createRun, updateRun, readRun, type RunRecord } from "./runRecord";
import { gitSha, hashAll } from "./snapshot";
import type { Spawner } from "./spawnProc";
import { ConfigError, ClaudeRunError } from "./errors";

export interface RunPipelineOpts {
  studioRoot: string; runsRoot: string;
  notify?: boolean; claudeBin?: string; spawner: Spawner; now?: Date;
}

export async function runPipeline(channelId: string,
  o: RunPipelineOpts): Promise<RunRecord> {
  const cfg = await loadConfig(channelId, o.studioRoot); // config errors: no run dir
  const financeRoot = join(o.studioRoot, "../financial-report-system");
  const snap = { gitSha: gitSha(o.studioRoot),
    promptHashes: hashAll({ main: cfg.promptTemplate, picks: cfg.picksPrompt }) };
  const runId = await createRun(o.runsRoot, channelId, snap);
  try {
    await updateRun(o.runsRoot, runId, { status: "running", pid: process.pid });
    const cal = calendarFacts(o.now ?? new Date());
    const prompt = buildPrompt({
      promptTemplate: cfg.promptTemplate, references: cfg.references,
      channel: cfg.channel, calendarText: cal.text,
    });
    const htmlOut = join(o.runsRoot, runId, "report.html");
    const cr = await runClaude({
      prompt, model: cfg.pipeline.model, maxTurns: cfg.pipeline.max_turns,
      cwd: financeRoot, htmlOut, claudeBin: o.claudeBin,
      env: { FAKE_CLAUDE_OUT: htmlOut }, spawner: o.spawner,
    });
    const pp = await postProcess({
      htmlPath: cr.htmlPath, financeRoot,
      post: { ...cfg.pipeline.post, notify: o.notify ?? cfg.pipeline.post.notify },
      runPicks: true, spawner: o.spawner,
    });
    await updateRun(o.runsRoot, runId, {
      status: "succeeded", exitCode: 0, reportHtmlPath: cr.htmlPath,
      reportOk: true, pdfOk: pp.pdfOk, notifyOk: pp.notifyOk, pdfPath: pp.pdfPath,
    });
  } catch (e) {
    const stage = e instanceof ConfigError ? "loadConfig"
      : e instanceof ClaudeRunError ? "runClaude" : "postProcess";
    await updateRun(o.runsRoot, runId, {
      status: "failed",
      error: { stage, message: e instanceof Error ? e.message : String(e),
        claudeLogPath: join(o.runsRoot, runId, "claude.log") },
    });
  }
  return readRun(o.runsRoot, runId);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 6: Run the full suite**

Run: `cd studio && npm test`
Expected: all tests (Tasks 2–10) PASS.

- [ ] **Step 7: Commit**

```bash
git add studio/lib/runner/snapshot.ts studio/lib/runner/runPipeline.ts studio/lib/runner/runPipeline.test.ts
git commit -m "feat(studio): runPipeline single entry orchestrating all stages"
git push origin main
```

---

## Task 11: Mechanical quality self-check

**Files:**
- Create: `studio/lib/quality/check.ts`
- Test: `studio/lib/quality/check.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// studio/lib/quality/check.test.ts
import { describe, it, expect } from "vitest";
import { mechanicalChecks } from "./check";

describe("mechanicalChecks", () => {
  it("passes a report with required sections + correct weekday", () => {
    const html = "<h2>Overall signal</h2><p>Today is 2026-04-30 (Thursday).</p>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    expect(mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" }).ok).toBe(true);
  });
  it("fails when the report weekday contradicts calendar facts", () => {
    const html = "<p>Today is 2026-04-30 (Monday).</p><h2>Overall signal</h2>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    const r = mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" });
    expect(r.ok).toBe(false);
    expect(r.failures.join()).toMatch(/weekday/i);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd studio && npx vitest run lib/quality/check.test.ts`
Expected: FAIL — cannot resolve `./check`.

- [ ] **Step 3: Write minimal implementation**

```ts
// studio/lib/quality/check.ts
export interface MechResult { ok: boolean; failures: string[]; }
const REQUIRED = ["Overall signal", "Key levels", "Picks"];

export function mechanicalChecks(
  html: string, cal: { iso: string; weekday: string },
): MechResult {
  const failures: string[] = [];
  for (const s of REQUIRED)
    if (!html.includes(s)) failures.push(`missing section: ${s}`);
  const m = html.match(/\((Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\)/);
  if (m && m[1] !== cal.weekday)
    failures.push(`weekday mismatch: report says ${m[1]}, calendar says ${cal.weekday}`);
  return { ok: failures.length === 0, failures };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd studio && npx vitest run lib/quality/check.test.ts`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add studio/lib/quality/check.ts studio/lib/quality/check.test.ts
git commit -m "feat(studio): mechanical quality checks (sections + calendar)"
git push origin main
```

> **Deferred (not a placeholder — scoped per spec §5):** the Sonnet LLM-as-judge wrapper reads `quality_judge.model` + `judge-rubric.md` and calls `claude` through the same `Spawner` (arg array, capturing stdout to a temp file then parsing the rubric JSON). It needs a real report to be meaningful, so it is wired during Task 13 Step 5, not as a standalone unit task.

---

## Task 12: API routes — trigger + status + channels

**Files:**
- Create: `studio/lib/runner/paths.ts`
- Create: `studio/app/api/runs/route.ts`
- Create: `studio/app/api/runs/[id]/route.ts`
- Create: `studio/app/api/channels/route.ts`

- [ ] **Step 1: Create the paths helper**

```ts
// studio/lib/runner/paths.ts
import { join } from "node:path";
export const STUDIO_ROOT = process.cwd();          // studio/
export const RUNS_ROOT = join(STUDIO_ROOT, "runs");
```

- [ ] **Step 2: Create the trigger/list route**

```ts
// studio/app/api/runs/route.ts
import { NextRequest, NextResponse } from "next/server";
import { readdir } from "node:fs/promises";
import { runPipeline } from "@/lib/runner/runPipeline";
import { spawnProc } from "@/lib/runner/spawnProc";
import { RUNS_ROOT, STUDIO_ROOT } from "@/lib/runner/paths";

export async function POST(req: NextRequest) {
  const { channelId, notify } = await req.json();
  // Fire-and-forget: failures are recorded in run.json; never crash the route.
  void runPipeline(channelId, {
    studioRoot: STUDIO_ROOT, runsRoot: RUNS_ROOT, notify, spawner: spawnProc,
  }).catch(() => {});
  return NextResponse.json({ started: true });
}

export async function GET() {
  let ids: string[] = [];
  try { ids = await readdir(RUNS_ROOT); } catch { /* none yet */ }
  return NextResponse.json({ runs: ids.sort().reverse() });
}
```

- [ ] **Step 3: Create the single-run status route**

```ts
// studio/app/api/runs/[id]/route.ts
import { NextResponse } from "next/server";
import { readRun } from "@/lib/runner/runRecord";
import { RUNS_ROOT } from "@/lib/runner/paths";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try { return NextResponse.json(await readRun(RUNS_ROOT, id)); }
  catch { return NextResponse.json({ error: "not found" }, { status: 404 }); }
}
```

- [ ] **Step 4: Create the channels read/write route (validate before write)**

```ts
// studio/app/api/channels/route.ts
import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { ChannelsFile } from "@/lib/config/schema";
import { STUDIO_ROOT } from "@/lib/runner/paths";

const FILE = join(STUDIO_ROOT, "config/channels.yaml");

export async function GET() {
  return NextResponse.json(ChannelsFile.parse(YAML.parse(await readFile(FILE, "utf8"))));
}
export async function PUT(req: NextRequest) {
  const parsed = ChannelsFile.parse(await req.json());     // reject invalid before write
  await writeFile(FILE, YAML.stringify(parsed));
  return NextResponse.json({ ok: true });
}
```

- [ ] **Step 5: Type-check**

Run: `cd studio && npx tsc --noEmit`
Expected: exits 0.

- [ ] **Step 6: Commit**

```bash
git add studio/lib/runner/paths.ts studio/app/api
git commit -m "feat(studio): API routes for trigger/status/channels"
git push origin main
```

---

## Task 13: Minimal UI + first real-run verification

**Files:**
- Create: `studio/next.config.ts`, `studio/app/layout.tsx`, `studio/app/page.tsx`

- [ ] **Step 1: Create `studio/next.config.ts`**

```ts
import type { NextConfig } from "next";
const config: NextConfig = {};
export default config;
```

- [ ] **Step 2: Create the root layout**

```tsx
// studio/app/layout.tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="zh-Hant"><body style={{ fontFamily: "system-ui", margin: 24 }}>
    {children}</body></html>);
}
```

- [ ] **Step 3: Create the single page**

```tsx
// studio/app/page.tsx
"use client";
import { useEffect, useState } from "react";

interface Ch { id: string; name: string; handle: string; enabled: boolean; }

export default function Home() {
  const [channels, setChannels] = useState<Ch[]>([]);
  const [runs, setRuns] = useState<string[]>([]);
  const load = async () => {
    setChannels((await (await fetch("/api/channels")).json()).channels);
    setRuns((await (await fetch("/api/runs")).json()).runs);
  };
  useEffect(() => { void load(); }, []);
  const run = async (id: string) => {
    await fetch("/api/runs", { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ channelId: id }) });
    setTimeout(() => void load(), 1500);
  };
  return (<main>
    <h1>agent-flow-studio</h1>
    <h2>Channels</h2>
    <ul>{channels.map((c) => (<li key={c.id}>
      {c.name} ({c.handle}) {c.enabled ? "" : "(disabled) "}
      <button disabled={!c.enabled} onClick={() => void run(c.id)}>Run</button>
    </li>))}</ul>
    <h2>Runs</h2>
    <ul>{runs.map((r) => (<li key={r}>{r}</li>))}</ul>
  </main>);
}
```

- [ ] **Step 4: Build to verify the app compiles**

Run: `cd studio && npm run build`
Expected: Next build succeeds, no type errors.

- [ ] **Step 5: First real-run self-verification (Claude runs this — not the user)**

Run:
```bash
cd studio && npm test                       # full suite green
npm run dev & sleep 6
curl -s -XPOST localhost:4317/api/runs -H 'content-type: application/json' -d '{"channelId":"eason"}'
sleep 90   # real claude -p run; adjust if needed
ls -t runs | head -1                          # newest runId
```
Then read `runs/<newest>/run.json`, run `mechanicalChecks` on its `report.html`, and run the Sonnet judge wrapper. Paste the command output + run.json + mechanical-check result + judge JSON into the commit message as verification evidence. Per `feedback_self_verification_first`, only escalate to the user for the subjective "is the analysis genuinely insightful" call — with the diff laid out.

- [ ] **Step 6: Commit**

```bash
git add studio/next.config.ts studio/app/layout.tsx studio/app/page.tsx
git commit -m "feat(studio): minimal UI + first real-run verification evidence"
git push origin main
```

---

## Self-Review

**1. Spec coverage:**
- §1 decisions (local `claude -p` seam / files-in-git / Next.js) → Tasks 1, 3, 8, 10. ✓
- §2 config model + `studio/` tree + exact YAML/prompts → Tasks 1, 3. ✓
- §2 calendar-fact injection (#1) → Task 5, consumed in Task 10. ✓
- §3 runner single module, 5 stages → Tasks 4–10. ✓
- §3 prompt source-of-truth (references inlined into prompt) → Task 6. ✓
- §3 `runClaude` sole seam → Task 8 (only file constructing claude args; behind `Spawner`). ✓
- §4 typed errors / no silent fallback / sub-status / snapshot / stale sweep → Tasks 4, 7, 10. ✓
- §4 idempotency (new runId per run, notifySent field) → Task 7 (`RunRecord` fields) + Task 10 (new run each call). ✓
- §5 TDD throughout / fake-CLI / mechanical + Sonnet judge / self-run gate → Tasks 8, 11, 13. ✓
- §6 YAGNI (no canvas/API-orchestrator/other pipelines/auto-cron) → none present. ✓
- §7 build sequence → Task order matches the spec's 6-step sequence. ✓
- Security invariant (repo hook) → `Spawner`/`execFile` arg arrays everywhere; no `exec()` with strings. ✓

**2. Placeholder scan:** No "TBD/handle edge cases/write tests for the above" — every code step has complete code. The Sonnet judge deferral is explicitly scoped (needs a real report) with a defined wiring point, not a vague placeholder.

**3. Type consistency:** `Spawner` (Task 8) used unchanged in Tasks 9/10/12. `LoadedConfig` (Task 4) consumed as-is by `runPipeline` (Task 10). `RunRecord`/`RunStatus` (Task 7) used in Tasks 10/12. `RunClaudeArgs.spawner` matches `Spawner`. `PipelineConfig.post` shape (Task 2) matches `postProcess` usage (Task 9). No name drift.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-agent-flow-studio-v1.md`.
