# ReactFlow Canvas v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an editable 6-node ReactFlow canvas (as the studio home page) that visualises the eason pipeline and lets the user edit channels / pipeline fields / prompts and trigger+watch runs, persisting to the existing config files.

**Architecture:** Approach 1 — the graph shape is a static frontend model (mirrors the fixed runner); editing goes through small per-resource stores (pure, root-injectable, TDD'd with tmp dirs) wrapped by thin Next route handlers. No new data model, no runner changes. `@xyflow/react` v12 renders the graph; a right-side panel switches editor by selected node.

**Tech Stack:** Next.js 15 (App Router, React 19), `@xyflow/react` v12, TypeScript, Vitest, zod (existing `PipelineFile`/`ChannelsFile`), `yaml`.

---

## File Structure

- `studio/package.json` / `studio/package-lock.json` — add `@xyflow/react`.
- `studio/app/canvas/nodes.ts` — static node/edge model + `editorFor(nodeId)` pure mapping. **Has no React/xyflow imports** (keeps it unit-testable).
- `studio/lib/config/promptPaths.ts` — `EASON_PROMPT_FILES` whitelist + `resolveSafePromptPath(root, rel)`.
- `studio/lib/config/promptStore.ts` — `readPrompt(root, rel)` / `writePrompt(root, rel, content)`.
- `studio/lib/config/pipelineStore.ts` — `readPipeline(root, name)` / `writePipeline(root, name, obj)` (zod-validated, name-whitelisted).
- `studio/app/api/prompts/route.ts` — thin GET/PUT delegating to `promptStore` with `STUDIO_ROOT`.
- `studio/app/api/pipeline/[name]/route.ts` — thin GET/PUT delegating to `pipelineStore`.
- `studio/components/canvas/StageNode.tsx` — custom node renderer.
- `studio/components/canvas/RunBar.tsx` — run trigger + recent run status.
- `studio/components/canvas/SidePanel.tsx` — composes editors by `editorFor`.
- `studio/components/canvas/editors/ChannelsEditor.tsx` / `PipelineEditor.tsx` / `PromptEditor.tsx`.
- `studio/app/page.tsx` — replaced: canvas page hosting ReactFlow + RunBar + SidePanel.
- Test files alongside: `nodes.test.ts`, `promptPaths.test.ts`, `promptStore.test.ts`, `pipelineStore.test.ts`.

**Testability decision:** Next route handlers are thin adapters; the real logic lives in `promptStore`/`pipelineStore`, which take an explicit `root` so Vitest can exercise them against a `tmpdir` without clobbering repo files (the same pattern `loadConfig(channelId, studioRoot)` already uses). Routes themselves are not unit-tested (trivial delegation) — covered by store tests + the Task 7 manual acceptance. React components are gated by `tsc --noEmit` + `next build` + manual acceptance (jsdom + React19 + xyflow is not worth unit-wiring; UI correctness is explicitly manual per the spec).

---

### Task 1: Dependency + static canvas model

**Files:**
- Modify: `studio/package.json`, `studio/package-lock.json`
- Create: `studio/app/canvas/nodes.ts`
- Test: `studio/app/canvas/nodes.test.ts`

- [ ] **Step 1: Add the dependency**

Run: `cd studio && npm install @xyflow/react@^12.3.5`
Expected: `package.json` gains `"@xyflow/react": "^12.3.5"` under dependencies; `package-lock.json` updated; no errors.

- [ ] **Step 2: Write the failing test** — `studio/app/canvas/nodes.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { CANVAS_NODES, CANVAS_EDGES, editorFor } from "./nodes";

describe("canvas nodes model", () => {
  it("has exactly the 6 fixed stage nodes with unique ids", () => {
    expect(CANVAS_NODES).toHaveLength(6);
    const ids = CANVAS_NODES.map((n) => n.id);
    expect(new Set(ids).size).toBe(6);
    expect(ids).toEqual([
      "channels", "digest", "analysis", "postprocess", "quality", "persistence",
    ]);
  });
  it("edges form the linear pipeline and reference only existing nodes", () => {
    const ids = new Set(CANVAS_NODES.map((n) => n.id));
    expect(CANVAS_EDGES).toHaveLength(5);
    for (const e of CANVAS_EDGES) {
      expect(ids.has(e.source)).toBe(true);
      expect(ids.has(e.target)).toBe(true);
    }
    expect(CANVAS_EDGES.map((e) => `${e.source}->${e.target}`)).toEqual([
      "channels->digest", "digest->analysis", "analysis->postprocess",
      "postprocess->quality", "quality->persistence",
    ]);
  });
  it("editorFor maps each node id to its editor kind, null for unknown", () => {
    expect(editorFor("channels")).toBe("channels");
    expect(editorFor("digest")).toBe("pipeline-digest");
    expect(editorFor("analysis")).toBe("pipeline-analysis");
    expect(editorFor("postprocess")).toBe("pipeline-postprocess");
    expect(editorFor("quality")).toBe("pipeline-quality");
    expect(editorFor("persistence")).toBe("persistence");
    expect(editorFor("nope")).toBeNull();
  });
});
```

- [ ] **Step 3: Run it to verify it fails**

Run: `cd studio && npx vitest run app/canvas/nodes.test.ts`
Expected: FAIL — module `./nodes` does not exist.

- [ ] **Step 4: Implement** `studio/app/canvas/nodes.ts`:

```ts
// Static model — intentionally no @xyflow/react import so this stays unit-testable.
export interface CanvasNode {
  id: string;
  type: "stage";
  position: { x: number; y: number };
  data: { title: string; subtitle: string; accent: string };
}
export interface CanvasEdge { id: string; source: string; target: string; }

export type EditorKind =
  | "channels" | "pipeline-digest" | "pipeline-analysis"
  | "pipeline-postprocess" | "pipeline-quality" | "persistence";

const ORDER = [
  "channels", "digest", "analysis", "postprocess", "quality", "persistence",
] as const;

const META: Record<string, { title: string; subtitle: string; accent: string }> = {
  channels:    { title: "頻道",   subtitle: "channels.yaml",        accent: "#2563eb" },
  digest:      { title: "摘要",   subtitle: "Sonnet · digest.md",   accent: "#7c3aed" },
  analysis:    { title: "分析",   subtitle: "main + references",    accent: "#0d9488" },
  postprocess: { title: "後處理", subtitle: "PDF · notify · picks", accent: "#b45309" },
  quality:     { title: "品質",   subtitle: "quality_sections",     accent: "#be185d" },
  persistence: { title: "持久化", subtitle: "training/daily/picks", accent: "#15803d" },
};

export const CANVAS_NODES: CanvasNode[] = ORDER.map((id, i) => ({
  id, type: "stage",
  position: { x: i * 220, y: 80 },
  data: META[id]!,
}));

export const CANVAS_EDGES: CanvasEdge[] = ORDER.slice(1).map((id, i) => ({
  id: `e-${ORDER[i]}-${id}`, source: ORDER[i]!, target: id,
}));

const EDITORS: Record<string, EditorKind> = {
  channels: "channels",
  digest: "pipeline-digest",
  analysis: "pipeline-analysis",
  postprocess: "pipeline-postprocess",
  quality: "pipeline-quality",
  persistence: "persistence",
};

export function editorFor(nodeId: string): EditorKind | null {
  return EDITORS[nodeId] ?? null;
}
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd studio && npx vitest run app/canvas/nodes.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 6: Commit + push** (git from repo root)

```bash
git add studio/package.json studio/package-lock.json studio/app/canvas/nodes.ts studio/app/canvas/nodes.test.ts
git commit -m "feat(canvas): add @xyflow/react + static 6-node canvas model (canvas v1)"
git push origin main
```

---

### Task 2: Prompt path whitelist

**Files:**
- Create: `studio/lib/config/promptPaths.ts`
- Test: `studio/lib/config/promptPaths.test.ts`

- [ ] **Step 1: Write the failing test** — `studio/lib/config/promptPaths.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { join } from "node:path";
import { EASON_PROMPT_FILES, resolveSafePromptPath } from "./promptPaths";

const ROOT = "/tmp/fake-studio";

describe("promptPaths", () => {
  it("whitelist is exactly the eason prompt set", () => {
    expect([...EASON_PROMPT_FILES].sort()).toEqual([
      "prompts/eason/digest.md",
      "prompts/eason/framework.md",
      "prompts/eason/main.md",
      "prompts/eason/persistence.md",
      "prompts/eason/picks.md",
      "prompts/eason/transcript.md",
      "prompts/eason/voice.md",
    ]);
  });
  it("resolves a whitelisted file to an absolute path under root", () => {
    expect(resolveSafePromptPath(ROOT, "prompts/eason/main.md"))
      .toBe(join(ROOT, "prompts/eason/main.md"));
  });
  it("rejects traversal, absolute, unknown, empty", () => {
    expect(resolveSafePromptPath(ROOT, "../../../etc/passwd")).toBeNull();
    expect(resolveSafePromptPath(ROOT, "prompts/eason/../../secret")).toBeNull();
    expect(resolveSafePromptPath(ROOT, "/etc/passwd")).toBeNull();
    expect(resolveSafePromptPath(ROOT, "prompts/eason/unknown.md")).toBeNull();
    expect(resolveSafePromptPath(ROOT, "")).toBeNull();
    expect(resolveSafePromptPath(ROOT, "prompts/eason/report.css")).toBeNull();
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd studio && npx vitest run lib/config/promptPaths.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `studio/lib/config/promptPaths.ts`:

```ts
import { join, normalize } from "node:path";

// Exactly the eason pipeline's editable prompts (template + references +
// digest + picks). report.css is NOT a prompt → intentionally excluded (v1).
export const EASON_PROMPT_FILES: ReadonlySet<string> = new Set([
  "prompts/eason/main.md",
  "prompts/eason/digest.md",
  "prompts/eason/framework.md",
  "prompts/eason/voice.md",
  "prompts/eason/persistence.md",
  "prompts/eason/transcript.md",
  "prompts/eason/picks.md",
]);

/** Absolute path under `root` for a whitelisted prompt, or null if rejected. */
export function resolveSafePromptPath(root: string, rel: string): string | null {
  if (!rel || !EASON_PROMPT_FILES.has(rel)) return null;
  // Defence in depth: even a whitelisted string must not normalise outside.
  if (normalize(rel) !== rel || rel.includes("..")) return null;
  return join(root, rel);
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd studio && npx vitest run lib/config/promptPaths.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Commit + push**

```bash
git add studio/lib/config/promptPaths.ts studio/lib/config/promptPaths.test.ts
git commit -m "feat(config): eason prompt-path whitelist + safe resolver (canvas v1)"
git push origin main
```

---

### Task 3: Prompt store + /api/prompts route

**Files:**
- Create: `studio/lib/config/promptStore.ts`, `studio/app/api/prompts/route.ts`
- Test: `studio/lib/config/promptStore.test.ts`

- [ ] **Step 1: Write the failing test** — `studio/lib/config/promptStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, mkdir, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readPrompt, writePrompt, PromptPathError } from "./promptStore";

let root: string;
beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "ps-"));
  await mkdir(join(root, "prompts/eason"), { recursive: true });
  await writeFile(join(root, "prompts/eason/main.md"), "ORIGINAL", "utf8");
});

describe("promptStore", () => {
  it("reads a whitelisted prompt", async () => {
    expect(await readPrompt(root, "prompts/eason/main.md")).toBe("ORIGINAL");
  });
  it("writes a whitelisted prompt and reads it back", async () => {
    await writePrompt(root, "prompts/eason/main.md", "NEW BODY");
    expect(await readFile(join(root, "prompts/eason/main.md"), "utf8")).toBe("NEW BODY");
  });
  it("rejects a non-whitelisted / traversal path on read and write", async () => {
    await expect(readPrompt(root, "../../etc/passwd")).rejects.toBeInstanceOf(PromptPathError);
    await expect(writePrompt(root, "prompts/eason/x.md", "y")).rejects.toBeInstanceOf(PromptPathError);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd studio && npx vitest run lib/config/promptStore.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `studio/lib/config/promptStore.ts`:

```ts
import { readFile, writeFile } from "node:fs/promises";
import { resolveSafePromptPath } from "./promptPaths";

export class PromptPathError extends Error {
  constructor(rel: string) { super(`prompt path not allowed: ${rel}`); this.name = "PromptPathError"; }
}

export async function readPrompt(root: string, rel: string): Promise<string> {
  const abs = resolveSafePromptPath(root, rel);
  if (!abs) throw new PromptPathError(rel);
  return readFile(abs, "utf8");
}

export async function writePrompt(root: string, rel: string, content: string): Promise<void> {
  const abs = resolveSafePromptPath(root, rel);
  if (!abs) throw new PromptPathError(rel);
  await writeFile(abs, content, "utf8");
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd studio && npx vitest run lib/config/promptStore.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Implement the thin route** `studio/app/api/prompts/route.ts`:

```ts
import { NextRequest, NextResponse } from "next/server";
import { STUDIO_ROOT } from "@/lib/runner/paths";
import { readPrompt, writePrompt, PromptPathError } from "@/lib/config/promptStore";

export async function GET(req: NextRequest) {
  const rel = req.nextUrl.searchParams.get("path") ?? "";
  try {
    return NextResponse.json({ path: rel, content: await readPrompt(STUDIO_ROOT, rel) });
  } catch (e) {
    if (e instanceof PromptPathError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "read failed" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest) {
  let body: { path?: string; content?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "bad json" }, { status: 400 }); }
  if (typeof body.path !== "string" || typeof body.content !== "string")
    return NextResponse.json({ error: "path and content required" }, { status: 400 });
  try {
    await writePrompt(STUDIO_ROOT, body.path, body.content);
    return NextResponse.json({ ok: true });
  } catch (e) {
    if (e instanceof PromptPathError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "write failed" }, { status: 500 });
  }
}
```

- [ ] **Step 6: Verify build + types**

Run: `cd studio && npx tsc --noEmit && npx next build`
Expected: tsc clean; `next build` succeeds (route compiles).

- [ ] **Step 7: Commit + push**

```bash
git add studio/lib/config/promptStore.ts studio/lib/config/promptStore.test.ts studio/app/api/prompts/route.ts
git commit -m "feat(api): /api/prompts GET/PUT via whitelisted prompt store (canvas v1)"
git push origin main
```

---

### Task 4: Pipeline store + /api/pipeline/[name] route

**Files:**
- Create: `studio/lib/config/pipelineStore.ts`, `studio/app/api/pipeline/[name]/route.ts`
- Test: `studio/lib/config/pipelineStore.test.ts`

- [ ] **Step 1: Write the failing test** — `studio/lib/config/pipelineStore.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, mkdir, copyFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readPipeline, writePipeline, PipelineStoreError } from "./pipelineStore";

const REAL_EASON = new URL("../../config/pipelines/eason.yaml", import.meta.url).pathname;
let root: string;
beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "pl-"));
  await mkdir(join(root, "config/pipelines"), { recursive: true });
  await copyFile(REAL_EASON, join(root, "config/pipelines/eason.yaml"));
});

describe("pipelineStore", () => {
  it("reads + validates the eason pipeline", async () => {
    const p = await readPipeline(root, "eason");
    expect(p.name).toBe("eason");
    expect(p.model).toMatch(/sonnet/);
  });
  it("writes a valid pipeline and reads it back", async () => {
    const p = await readPipeline(root, "eason");
    p.max_turns = 42;
    await writePipeline(root, "eason", p);
    const again = await readPipeline(root, "eason");
    expect(again.max_turns).toBe(42);
  });
  it("rejects an unknown pipeline name", async () => {
    await expect(readPipeline(root, "../secret")).rejects.toBeInstanceOf(PipelineStoreError);
    await expect(readPipeline(root, "ghost")).rejects.toBeInstanceOf(PipelineStoreError);
  });
  it("rejects a schema-invalid write without touching the file", async () => {
    const before = await readFile(join(root, "config/pipelines/eason.yaml"), "utf8");
    await expect(writePipeline(root, "eason", { name: "eason" } as never))
      .rejects.toBeInstanceOf(PipelineStoreError);
    expect(await readFile(join(root, "config/pipelines/eason.yaml"), "utf8")).toBe(before);
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd studio && npx vitest run lib/config/pipelineStore.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement** `studio/lib/config/pipelineStore.ts`:

```ts
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { PipelineFile, type PipelineConfig } from "./schema";

const ALLOWED_PIPELINES = new Set(["eason"]);

export class PipelineStoreError extends Error {
  constructor(m: string) { super(m); this.name = "PipelineStoreError"; }
}

function pathFor(root: string, name: string): string {
  if (!ALLOWED_PIPELINES.has(name)) throw new PipelineStoreError(`unknown pipeline: ${name}`);
  return join(root, `config/pipelines/${name}.yaml`);
}

export async function readPipeline(root: string, name: string): Promise<PipelineConfig> {
  const p = pathFor(root, name);
  let raw: string;
  try { raw = await readFile(p, "utf8"); }
  catch { throw new PipelineStoreError(`pipeline file not readable: ${name}`); }
  try { return PipelineFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid pipeline ${name}: ${e instanceof Error ? e.message : String(e)}`); }
}

export async function writePipeline(root: string, name: string, obj: unknown): Promise<void> {
  const p = pathFor(root, name);
  let valid: PipelineConfig;
  try { valid = PipelineFile.parse(obj); }
  catch (e) { throw new PipelineStoreError(`schema validation failed: ${e instanceof Error ? e.message : String(e)}`); }
  await writeFile(p, YAML.stringify(valid), "utf8");
}
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd studio && npx vitest run lib/config/pipelineStore.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Implement the thin route** `studio/app/api/pipeline/[name]/route.ts`:

> Next.js 15: the dynamic route `params` is a Promise and MUST be awaited.

```ts
import { NextRequest, NextResponse } from "next/server";
import { STUDIO_ROOT } from "@/lib/runner/paths";
import { readPipeline, writePipeline, PipelineStoreError } from "@/lib/config/pipelineStore";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  try {
    return NextResponse.json({ name, pipeline: await readPipeline(STUDIO_ROOT, name) });
  } catch (e) {
    if (e instanceof PipelineStoreError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "read failed" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "bad json" }, { status: 400 }); }
  try {
    await writePipeline(STUDIO_ROOT, name, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    if (e instanceof PipelineStoreError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "write failed" }, { status: 500 });
  }
}
```

- [ ] **Step 6: Verify build + types**

Run: `cd studio && npx tsc --noEmit && npx next build`
Expected: tsc clean; `next build` succeeds.

- [ ] **Step 7: Commit + push**

```bash
git add studio/lib/config/pipelineStore.ts studio/lib/config/pipelineStore.test.ts studio/app/api/pipeline
git commit -m "feat(api): /api/pipeline/[name] GET/PUT via zod-validated pipeline store (canvas v1)"
git push origin main
```

---

### Task 5: Canvas page — graph + RunBar

**Files:**
- Create: `studio/components/canvas/StageNode.tsx`, `studio/components/canvas/RunBar.tsx`
- Modify: `studio/app/page.tsx`

No unit test (React/xyflow); gated by `tsc --noEmit` + `next build` + Task 7 manual acceptance.

- [ ] **Step 1: Implement** `studio/components/canvas/StageNode.tsx`:

```tsx
"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export function StageNode({ data, selected }: NodeProps) {
  const d = data as { title: string; subtitle: string; accent: string };
  return (
    <div style={{
      minWidth: 130, padding: "10px 12px", borderRadius: 8,
      background: "#1f2937", color: "#e5e7eb",
      border: `2px solid ${selected ? d.accent : "#374151"}`,
      boxShadow: selected ? `0 0 0 2px ${d.accent}55` : "none", cursor: "pointer",
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</div>
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>{d.subtitle}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

- [ ] **Step 2: Implement** `studio/components/canvas/RunBar.tsx`:

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";

interface RunStatus { id: string; status?: string; qualityOk?: boolean; }

export function RunBar({ channelId }: { channelId: string }) {
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const ids: string[] = (await (await fetch("/api/runs")).json()).runs ?? [];
    const top = ids.slice(0, 5);
    const detailed = await Promise.all(top.map(async (id) => {
      try {
        const r = await (await fetch(`/api/runs/${encodeURIComponent(id)}`)).json();
        return { id, status: r.status, qualityOk: r.qualityOk } as RunStatus;
      } catch { return { id } as RunStatus; }
    }));
    setRuns(detailed);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const trigger = async () => {
    setBusy(true);
    await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ channelId }),
    });
    setTimeout(() => { void load(); setBusy(false); }, 2000);
  };

  const color = (s?: string, q?: boolean) =>
    s === "succeeded" ? (q ? "#15803d" : "#b45309")
    : s === "failed" ? "#b91c1c" : s === "running" ? "#2563eb" : "#6b7280";

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 12px",
      borderBottom: "1px solid #30363d", fontSize: 13, color: "#cbd5e1" }}>
      <button onClick={() => void trigger()} disabled={busy}
        style={{ background: "#2563eb", color: "#fff", border: 0, borderRadius: 6,
          padding: "6px 14px", cursor: busy ? "default" : "pointer" }}>
        {busy ? "啟動中…" : `▶ Run ${channelId}`}
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

- [ ] **Step 3: Replace** `studio/app/page.tsx`:

```tsx
"use client";
import { useState, useCallback } from "react";
import {
  ReactFlow, Background, Controls, type Node, type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CANVAS_NODES, CANVAS_EDGES } from "./canvas/nodes";
import { StageNode } from "@/components/canvas/StageNode";
import { RunBar } from "@/components/canvas/RunBar";
import { SidePanel } from "@/components/canvas/SidePanel";

const nodeTypes = { stage: StageNode };
const nodes: Node[] = CANVAS_NODES as unknown as Node[];
const edges: Edge[] = CANVAS_EDGES.map((e) => ({ ...e, animated: true }));

export default function Home() {
  const [selected, setSelected] = useState<string | null>(null);
  const onNodeClick = useCallback((_: unknown, n: Node) => setSelected(n.id), []);
  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <RunBar channelId="eason" />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1 }}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes}
            onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {selected && (
          <div style={{ width: 380, borderLeft: "1px solid #30363d", overflow: "auto",
            background: "#0d1117", color: "#e5e7eb" }}>
            <SidePanel nodeId={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </main>
  );
}
```

> Note: `SidePanel` is created in Task 6. To keep this task's `next build` green, create a temporary stub `studio/components/canvas/SidePanel.tsx` now:
>
> ```tsx
> "use client";
> export function SidePanel({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
>   return (<div style={{ padding: 16 }}>
>     <button onClick={onClose} style={{ float: "right" }}>✕</button>
>     <p>panel: {nodeId} (Task 6)</p>
>   </div>);
> }
> ```
> Task 6 replaces this stub with the real implementation.

- [ ] **Step 4: Verify build + types**

Run: `cd studio && npx tsc --noEmit && npx next build && npx vitest run`
Expected: tsc clean; `next build` succeeds; all existing + Task1-4 tests still pass.

- [ ] **Step 5: Commit + push**

```bash
git add studio/components/canvas/StageNode.tsx studio/components/canvas/RunBar.tsx studio/components/canvas/SidePanel.tsx studio/app/page.tsx
git commit -m "feat(canvas): 6-node ReactFlow page + RunBar (canvas v1)"
git push origin main
```

---

### Task 6: Side panel + editors

**Files:**
- Modify: `studio/components/canvas/SidePanel.tsx`
- Create: `studio/components/canvas/editors/ChannelsEditor.tsx`, `PipelineEditor.tsx`, `PromptEditor.tsx`

No unit test (React data wiring); gated by `tsc --noEmit` + `next build` + Task 7 manual acceptance.

- [ ] **Step 1: Implement** `studio/components/canvas/editors/PromptEditor.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";

export function PromptEditor({ files }: { files: { rel: string; label: string }[] }) {
  const [rel, setRel] = useState(files[0]?.rel ?? "");
  const [content, setContent] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!rel) return;
    setMsg("載入中…");
    fetch(`/api/prompts?path=${encodeURIComponent(rel)}`)
      .then((r) => r.json())
      .then((j) => { setContent(j.content ?? ""); setMsg(j.error ? `錯誤：${j.error}` : ""); })
      .catch(() => setMsg("讀取失敗"));
  }, [rel]);

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/prompts", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify({ path: rel, content }),
    });
    const j = await r.json();
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  return (
    <div style={{ marginTop: 12 }}>
      <label style={{ fontSize: 12, color: "#9ca3af" }}>Prompt 檔</label>
      <select value={rel} onChange={(e) => setRel(e.target.value)}
        style={{ display: "block", width: "100%", margin: "4px 0 8px", padding: 6 }}>
        {files.map((f) => <option key={f.rel} value={f.rel}>{f.label}</option>)}
      </select>
      <textarea value={content} onChange={(e) => setContent(e.target.value)}
        spellCheck={false} style={{ width: "100%", height: 320, fontFamily: "monospace",
          fontSize: 12, background: "#0d1117", color: "#e5e7eb", border: "1px solid #30363d" }} />
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button onClick={() => void save()}>儲存</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Implement** `studio/components/canvas/editors/PipelineEditor.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";

type Section = "digest" | "analysis" | "postprocess" | "quality";

export function PipelineEditor({ section }: { section: Section }) {
  const [p, setP] = useState<any>(null);
  const [msg, setMsg] = useState("載入中…");

  useEffect(() => {
    fetch("/api/pipeline/eason").then((r) => r.json())
      .then((j) => { setP(j.pipeline ?? null); setMsg(j.error ? `錯誤：${j.error}` : ""); })
      .catch(() => setMsg("讀取失敗"));
  }, []);

  if (!p) return <p style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</p>;

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/pipeline/eason", {
      method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(p),
    });
    const j = await r.json();
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  const field = (label: string, value: string, on: (v: string) => void) => (
    <div style={{ margin: "6px 0" }}>
      <label style={{ fontSize: 12, color: "#9ca3af" }}>{label}</label>
      <input value={value} onChange={(e) => on(e.target.value)}
        style={{ display: "block", width: "100%", padding: 6, marginTop: 3 }} />
    </div>
  );

  return (
    <div style={{ marginTop: 12 }}>
      {section === "analysis" && <>
        {field("model", p.model ?? "", (v) => setP({ ...p, model: v }))}
        {field("max_turns", String(p.max_turns ?? ""), (v) => setP({ ...p, max_turns: Number(v) || p.max_turns }))}
      </>}
      {section === "digest" && p.digest &&
        field("digest.model", p.digest.model ?? "", (v) => setP({ ...p, digest: { ...p.digest, model: v } }))}
      {section === "postprocess" && <>
        {field("post.picks.model", p.post?.picks?.model ?? "",
          (v) => setP({ ...p, post: { ...p.post, picks: { ...p.post.picks, model: v } } }))}
        <label style={{ fontSize: 12, color: "#9ca3af", display: "block", marginTop: 6 }}>
          <input type="checkbox" checked={!!p.post?.pdf}
            onChange={(e) => setP({ ...p, post: { ...p.post, pdf: e.target.checked } })} /> post.pdf
        </label>
        <label style={{ fontSize: 12, color: "#9ca3af", display: "block" }}>
          <input type="checkbox" checked={!!p.post?.notify}
            onChange={(e) => setP({ ...p, post: { ...p.post, notify: e.target.checked } })} /> post.notify
        </label>
      </>}
      {section === "quality" &&
        <div style={{ margin: "6px 0" }}>
          <label style={{ fontSize: 12, color: "#9ca3af" }}>quality_sections（一行一個）</label>
          <textarea value={(p.quality_sections ?? []).join("\n")}
            onChange={(e) => setP({ ...p, quality_sections: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
            style={{ width: "100%", height: 120, fontFamily: "monospace", fontSize: 12,
              background: "#0d1117", color: "#e5e7eb", border: "1px solid #30363d", marginTop: 3 }} />
        </div>}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button onClick={() => void save()}>儲存 pipeline</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Implement** `studio/components/canvas/editors/ChannelsEditor.tsx`:

```tsx
"use client";
import { useEffect, useState } from "react";

interface Ch { id: string; handle: string; name: string; search_query: string; pipeline: string; enabled: boolean; }

export function ChannelsEditor() {
  const [chs, setChs] = useState<Ch[]>([]);
  const [msg, setMsg] = useState("載入中…");

  const load = () => fetch("/api/channels").then((r) => r.json())
    .then((j) => { setChs(j.channels ?? []); setMsg(""); })
    .catch(() => setMsg("讀取失敗"));
  useEffect(() => { void load(); }, []);

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/channels", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify({ channels: chs }),
    });
    const j = await r.json().catch(() => ({}));
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  const addBlank = () => setChs([...chs, {
    id: "new-channel", handle: "@handle", name: "新頻道",
    search_query: "搜尋關鍵字", pipeline: "eason", enabled: false,
  }]);
  const upd = (i: number, k: keyof Ch, v: string | boolean) =>
    setChs(chs.map((c, j) => j === i ? { ...c, [k]: v } : c));

  return (
    <div style={{ marginTop: 12 }}>
      <button onClick={addBlank}>+ 新增 YouTuber</button>
      {chs.map((c, i) => (
        <div key={i} style={{ border: "1px solid #30363d", borderRadius: 6, padding: 8, margin: "8px 0" }}>
          {(["id", "handle", "name", "search_query", "pipeline"] as (keyof Ch)[]).map((k) => (
            <div key={k} style={{ margin: "4px 0" }}>
              <label style={{ fontSize: 11, color: "#9ca3af" }}>{k}</label>
              <input value={String(c[k])} onChange={(e) => upd(i, k, e.target.value)}
                style={{ display: "block", width: "100%", padding: 5 }} />
            </div>
          ))}
          <label style={{ fontSize: 12, color: "#9ca3af" }}>
            <input type="checkbox" checked={c.enabled}
              onChange={(e) => upd(i, "enabled", e.target.checked)} /> enabled
          </label>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button onClick={() => void save()}>儲存 channels.yaml</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement** the real `studio/components/canvas/SidePanel.tsx` (replaces the Task 5 stub):

```tsx
"use client";
import { editorFor } from "@/app/canvas/nodes";
import { ChannelsEditor } from "./editors/ChannelsEditor";
import { PipelineEditor } from "./editors/PipelineEditor";
import { PromptEditor } from "./editors/PromptEditor";

const REFS = [
  { rel: "prompts/eason/main.md", label: "main.md" },
  { rel: "prompts/eason/framework.md", label: "framework.md" },
  { rel: "prompts/eason/voice.md", label: "voice.md" },
  { rel: "prompts/eason/persistence.md", label: "persistence.md" },
  { rel: "prompts/eason/transcript.md", label: "transcript.md" },
];

export function SidePanel({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  const kind = editorFor(nodeId);
  return (
    <div style={{ padding: 16 }}>
      <button onClick={onClose} style={{ float: "right", background: "transparent",
        color: "#9ca3af", border: 0, fontSize: 16, cursor: "pointer" }}>✕</button>
      <h3 style={{ marginTop: 0 }}>{nodeId}</h3>
      {kind === "channels" && <ChannelsEditor />}
      {kind === "pipeline-analysis" && <>
        <PipelineEditor section="analysis" />
        <PromptEditor files={REFS} />
      </>}
      {kind === "pipeline-digest" && <>
        <PipelineEditor section="digest" />
        <PromptEditor files={[{ rel: "prompts/eason/digest.md", label: "digest.md" }]} />
      </>}
      {kind === "pipeline-postprocess" && <>
        <PipelineEditor section="postprocess" />
        <PromptEditor files={[{ rel: "prompts/eason/picks.md", label: "picks.md" }]} />
      </>}
      {kind === "pipeline-quality" && <PipelineEditor section="quality" />}
      {kind === "persistence" && (
        <p style={{ fontSize: 13, color: "#9ca3af" }}>
          持久化：每次 run 寫入 SQLite 的 eason_training（影片樣本）、eason_daily（每日觀點）、
          eason_picks（選股追蹤）。v1 唯讀展示，不在畫布編輯。
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Verify build + types + full suite**

Run: `cd studio && npx tsc --noEmit && npx next build && npx vitest run`
Expected: tsc clean; `next build` succeeds; all tests pass.

- [ ] **Step 6: Commit + push**

```bash
git add studio/components/canvas/SidePanel.tsx studio/components/canvas/editors
git commit -m "feat(canvas): side panel + channels/pipeline/prompt editors (canvas v1)"
git push origin main
```

---

### Task 7: Manual acceptance + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

Operational task (controller-run), like prior confirming runs.

- [ ] **Step 1:** `cd studio && npx next build` then start the server (`npx next start -p 3100` or `npx next dev -p 3100`) in the background; load `http://localhost:3100`.

- [ ] **Step 2:** Walk the spec §9 delivery definition, recording the real outcome of each (no glossing):
  1. `/` shows the 6-node eason graph, pan/zoom works.
  2. Channels node → add a disabled channel, Save → `channels.yaml` actually gained the entry (verify file on disk + GET returns it; then revert the test entry).
  3. Analysis node → edit `main.md` (append a harmless comment line), Save → file on disk changed; revert. Pipeline field edit (e.g. `max_turns`) Save → `eason.yaml` changed; revert.
  4. Invalid input is rejected: PUT a bad pipeline (e.g. `max_turns: "abc"` via the field) → UI shows 儲存失敗, file unchanged.
  5. RunBar → trigger `eason`, observe status pill transition running→succeeded and the qualityOk marker (this reuses the proven pipeline; ~15 min — may note as "triggered + status wiring confirmed" if a full run is impractical at review time, but the trigger + at least the `running` state must be observed live).
- [ ] **Step 3:** Append a dated **"Canvas v1 acceptance"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md`: what was verified, screenshots-by-description or file-diff evidence, any gaps, honest verdict. Restore any test edits made to config files (channels.yaml/prompts) so the repo is clean. Commit + push. Record a KG `record_experience` on the outcome. Remove any temp files.

---

## Self-Review

**1. Spec coverage:**
- §3 architecture (6-node static graph, @xyflow/react v12, replace page.tsx, side panel) → Tasks 1, 5, 6.
- §4 components (nodes.ts, promptPaths, stores, 2 routes, StageNode/SidePanel/3 editors/RunBar) → Tasks 1–6, each file mapped.
- §5 data flow (load/save/run) → RunBar+editors (5,6) hitting channels/runs/prompts/pipeline APIs (3,4 + existing).
- §6 error handling (400 on zod/whitelist, no write; 500 on IO; UI inline error) → store throw-types + route mapping (3,4) + editor `msg` states (6).
- §6 path safety → Task 2 `resolveSafePromptPath` (traversal/absolute/unknown/`..` cases tested) + Task 4 pipeline name whitelist.
- §7 testing → pure tests in Tasks 1–4; frontend gated by tsc+next build; manual acceptance Task 7. Matches spec's "UI correctness is manual" honesty.
- §9 delivery definition → Task 7 walks all 5 items.
- §2/§8 (no runner change, only eason, no auth, no layout persistence) → respected: no task touches `lib/runner/*` or `lib/config/{schema,load}.ts`; positions fixed in nodes.ts; pipeline store whitelists `eason`.

**2. Placeholder scan:** No TBD/TODO. Every code step has full file content. The only "stub" is the explicitly-temporary `SidePanel` in Task 5 Step 3, fully specified and replaced with complete code in Task 6 Step 4 — not a placeholder, a sequencing scaffold.

**3. Type consistency:** `editorFor` returns `EditorKind | null` (Task 1) and `SidePanel` switches on exactly those literals (`channels`/`pipeline-digest`/`pipeline-analysis`/`pipeline-postprocess`/`pipeline-quality`/`persistence`) (Task 6). `PromptPathError`/`PipelineStoreError` thrown by stores (Tasks 3,4) and caught by name in routes (same tasks). `resolveSafePromptPath(root, rel)` signature identical across Task 2 def, its test, and `promptStore` use. `CANVAS_NODES`/`CANVAS_EDGES` shapes consumed unchanged by `page.tsx`. Reused existing `PipelineFile`/`ChannelsFile` zod + `STUDIO_ROOT` — no signature drift.

**Open risks (flagged, not blocking):** (a) `next build`/`next dev` has not been run in this repo before — if the bare prior `page.tsx` never exercised a build, Task 5 may surface a pre-existing Next/React19 config gap; if so, fixing the build config is in-scope for Task 5 (it's the first task that needs a build) and should be reported, not worked around. (b) Full run in Task 7 is ~15 min; the acceptance must at minimum observe the trigger + a live `running` status, with the full succeed verified if practical — stated honestly either way.
