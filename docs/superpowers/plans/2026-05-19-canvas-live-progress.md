# Canvas Live Progress (v1.1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** When a run is in flight, the 6-node canvas shows which of the 4 observable runner stages (摘要/分析/後處理/品質) is pending / running / done / errored, so the user can see progress and where a failure happened.

**Architecture:** `runPipeline` already transitions through digest → runClaude → postProcess → quality with a `failStage` tracker. Add a `progress` object to the run record, written via `updateRun` at each transition (whole-object each time, because `updateRun` shallow-merges). The canvas polls the newest run's `run.json` (the `/api/runs/[id]` route already returns the full record — no API change) and colours nodes from `progress`; `channels` is static and `persistence` is derived (done iff the run succeeded), per the honest limitation that the runner cannot observe persistence inside a single claude turn.

**Tech Stack:** TypeScript, Next.js 15 / React 19, `@xyflow/react` v12, Vitest. No runner behaviour change beyond additive progress writes.

---

## File Structure

- `studio/lib/runner/runRecord.ts` — add `StepState` type + `progress?` field.
- `studio/lib/runner/runPipeline.ts` — maintain + persist `progress` at each stage transition + on failure.
- `studio/lib/runner/runPipeline.test.ts` — assert progress for a fake success run and a digest-failure run.
- `studio/components/canvas/RunBar.tsx` — track the newest run's record (status + progress), poll while running, lift it up via a callback prop.
- `studio/app/page.tsx` — hold run progress state, derive per-node status, feed it into node data.
- `studio/components/canvas/StageNode.tsx` — render a status colour/dot from `data.runStatus`.
- `studio/app/canvas/nodes.ts` — add a pure `nodeRunStatus(progress, runStatus, nodeId)` helper + its test (the only new unit-tested logic on the canvas side).
- `studio/app/canvas/nodes.test.ts` — tests for `nodeRunStatus`.

---

### Task 1: Runner emits per-stage progress

**Files:**
- Modify: `studio/lib/runner/runRecord.ts`, `studio/lib/runner/runPipeline.ts`
- Test: `studio/lib/runner/runPipeline.test.ts`

- [ ] **Step 1: Write the failing tests** — append inside the existing `describe("runPipeline", …)` block in `studio/lib/runner/runPipeline.test.ts`:

```ts
  it("records per-stage progress for a fake success run", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) =>
        file.endsWith("fake-claude.sh") ? spawnProc(file, args, opts) : { code: 0 },
    });
    expect(r.status).toBe("succeeded");
    expect(r.progress).toEqual({
      digest: "skipped",      // digest pass is skipped under the fake CLI
      analysis: "done",
      postprocess: "done",
      quality: "done",
    });
  });

  it("marks the failed stage as error in progress when the digest pass fails", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: "claude", // not fake → digest runs
      spawner: async () => ({ code: 0 }),                 // writes no digest file
    });
    expect(r.status).toBe("failed");
    expect(r.progress?.digest).toBe("error");
    expect(r.progress?.analysis).toBe("pending");
  });
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts -t "progress"`
Expected: FAIL — `r.progress` is `undefined`.

- [ ] **Step 3: Extend the run record type** in `studio/lib/runner/runRecord.ts`. Add after the `RunStatus` type:

```ts
export type StepState = "pending" | "running" | "done" | "error" | "skipped";
export interface RunProgress {
  digest: StepState; analysis: StepState; postprocess: StepState; quality: StepState;
}
```

and add to the `RunRecord` interface (after `qualityFailures?`):

```ts
  progress?: RunProgress;
```

- [ ] **Step 4: Emit progress** in `studio/lib/runner/runPipeline.ts`. Import the type:

```ts
import { createRun, updateRun, readRun, type RunRecord, type RunProgress } from "./runRecord";
```

Immediately after `let failStage: ... = "runClaude";` add:

```ts
  const progress: RunProgress = {
    digest: "pending", analysis: "pending", postprocess: "pending", quality: "pending",
  };
  const setProgress = (p: Partial<RunProgress>) => {
    Object.assign(progress, p);
    return updateRun(o.runsRoot, runId, { progress: { ...progress } });
  };
```

Then instrument the existing flow (do NOT restructure it — only add `await setProgress(...)` calls and the digest skipped/running/done states):

- Replace the digest block so it sets states:

```ts
    if (!isFake && cfg.pipeline.digest && cfg.digestPrompt) {
      failStage = "digest";
      await setProgress({ digest: "running" });
      await digestPass({
        digestPromptTemplate: cfg.digestPrompt,
        channel: cfg.channel, calendarText: cal.text, dateIso: cal.iso,
        digestPath, model: cfg.pipeline.digest.model,
        maxTurns: cfg.pipeline.max_turns, cwd: financeRoot,
        claudeBin: o.claudeBin, spawner: o.spawner,
        mcpConfigPath: o.mcpConfigPath, allowedTools: o.allowedTools,
        logPath: digestLogPath,
      });
      await setProgress({ digest: "done" });
    } else {
      await setProgress({ digest: "skipped" });
    }
    failStage = "runClaude";
    await setProgress({ analysis: "running" });
```

- After the `const cr = await runClaude({ … });` call, add:

```ts
    await setProgress({ analysis: "done" });
```

- Replace `failStage = "postProcess";` with:

```ts
    failStage = "postProcess";
    await setProgress({ postprocess: "running" });
```

- After the `const pp = await postProcess({ … });` call, add:

```ts
    await setProgress({ postprocess: "done", quality: "running" });
```

- In the quality `try { … } catch { … }` block, after `qualityOk`/`qualityFailures` are computed (both the success path and the catch path), set quality done. Concretely, immediately BEFORE the final `await updateRun(o.runsRoot, runId, { status: "succeeded", … })` add:

```ts
    progress.quality = "done";
```

and include `progress: { ...progress }` in that final success `updateRun` patch object.

- In the outer `catch (e)` block, map the failed stage onto the progress object before the failure `updateRun`. Replace the catch body's `updateRun` call so it also writes progress:

```ts
  } catch (e) {
    const stage = e instanceof ConfigError ? "loadConfig" : failStage;
    const canvasStage =
      stage === "digest" ? "digest"
      : stage === "runClaude" ? "analysis"
      : stage === "postProcess" ? "postprocess" : null;
    if (canvasStage) (progress as Record<string, StepState>)[canvasStage] = "error";
    await updateRun(o.runsRoot, runId, {
      status: "failed",
      error: { stage, message: e instanceof Error ? e.message : String(e),
        claudeLogPath },
      progress: { ...progress },
    });
  }
```

Add `StepState` to the runRecord import:

```ts
import { createRun, updateRun, readRun, type RunRecord, type RunProgress, type StepState } from "./runRecord";
```

> Note on `updateRun` semantics: it shallow-merges `{...prev, ...patch}`, so each call passes the WHOLE `progress` object (`{ ...progress }`) — never a partial — which is exactly what `setProgress` / the success / the catch paths do. `loadConfig` failures happen before the run dir exists, so no progress write is attempted there (unchanged behaviour).

- [ ] **Step 5: Run to verify the tests pass**

Run: `cd studio && npx vitest run lib/runner/runPipeline.test.ts && npx tsc --noEmit`
Expected: PASS (the 2 new + all existing runPipeline tests), tsc clean.

- [ ] **Step 6: Run the full suite**

Run: `cd studio && npx vitest run`
Expected: all pass (progress writes are additive; existing assertions on status/reportOk/qualityOk/run-dir-count are unaffected).

- [ ] **Step 7: Commit + push** (git from repo root)

```bash
git add studio/lib/runner/runRecord.ts studio/lib/runner/runPipeline.ts studio/lib/runner/runPipeline.test.ts
git commit -m "feat(runner): emit per-stage progress into run.json (canvas live progress)"
git push origin main
```

---

### Task 2: Pure node-status mapping

**Files:**
- Modify: `studio/app/canvas/nodes.ts`
- Test: `studio/app/canvas/nodes.test.ts`

- [ ] **Step 1: Write the failing test** — append to `studio/app/canvas/nodes.test.ts`:

```ts
import { nodeRunStatus } from "./nodes";

describe("nodeRunStatus", () => {
  const prog = { digest: "done", analysis: "running", postprocess: "pending", quality: "pending" } as const;

  it("returns the progress state for the 4 observable stages", () => {
    expect(nodeRunStatus("digest", prog, "running")).toBe("done");
    expect(nodeRunStatus("analysis", prog, "running")).toBe("running");
    expect(nodeRunStatus("postprocess", prog, "running")).toBe("pending");
    expect(nodeRunStatus("quality", prog, "running")).toBe("pending");
  });
  it("channels is always neutral (null)", () => {
    expect(nodeRunStatus("channels", prog, "running")).toBeNull();
  });
  it("persistence is done only when the run succeeded, else pending", () => {
    expect(nodeRunStatus("persistence", prog, "succeeded")).toBe("done");
    expect(nodeRunStatus("persistence", prog, "running")).toBe("pending");
    expect(nodeRunStatus("persistence", prog, "failed")).toBe("pending");
  });
  it("returns null when there is no progress (no active run)", () => {
    expect(nodeRunStatus("analysis", undefined, undefined)).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd studio && npx vitest run app/canvas/nodes.test.ts -t nodeRunStatus`
Expected: FAIL — `nodeRunStatus` not exported.

- [ ] **Step 3: Implement** — append to `studio/app/canvas/nodes.ts`:

```ts
export type StepState = "pending" | "running" | "done" | "error" | "skipped";
export interface RunProgress {
  digest: StepState; analysis: StepState; postprocess: StepState; quality: StepState;
}

/** Per-node status for canvas colouring. `null` = no run-status accent (neutral).
 *  channels is config (always null); persistence is derived (runner can't observe
 *  it mid-turn) — done only when the whole run succeeded. */
export function nodeRunStatus(
  nodeId: string,
  progress: RunProgress | undefined,
  runStatus: string | undefined,
): StepState | null {
  if (nodeId === "channels") return null;
  if (nodeId === "persistence") return runStatus === "succeeded" ? "done" : "pending";
  if (!progress) return null;
  if (nodeId === "digest" || nodeId === "analysis"
      || nodeId === "postprocess" || nodeId === "quality") {
    return progress[nodeId];
  }
  return null;
}
```

> Keep the existing `StepState`/`RunProgress` names identical to `runRecord.ts` (they are duplicated here intentionally so this frontend module stays free of any `node:`/server import — same rationale as the existing "no @xyflow import in nodes.ts").

- [ ] **Step 4: Run to verify it passes**

Run: `cd studio && npx vitest run app/canvas/nodes.test.ts && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Commit + push**

```bash
git add studio/app/canvas/nodes.ts studio/app/canvas/nodes.test.ts
git commit -m "feat(canvas): pure nodeRunStatus mapping (digest/analysis/postprocess/quality + derived persistence)"
git push origin main
```

---

### Task 3: Canvas live colouring

**Files:**
- Modify: `studio/components/canvas/RunBar.tsx`, `studio/app/page.tsx`, `studio/components/canvas/StageNode.tsx`

No unit test (React); gated by `tsc --noEmit` + `next build` + full vitest staying green + Task 4 manual check.

- [ ] **Step 1: Update** `studio/components/canvas/RunBar.tsx` to report the newest run's status+progress upward and poll while running. Replace its contents with:

```tsx
"use client";
import { useEffect, useState, useCallback } from "react";
import type { RunProgress } from "@/app/canvas/nodes";

interface RunStatus { id: string; status?: string; qualityOk?: boolean; progress?: RunProgress; }

export function RunBar({ channelId, onActive }:
  { channelId: string; onActive?: (s: { status?: string; progress?: RunProgress }) => void }) {
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [busy, setBusy] = useState(false);

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
    const newest = detailed[0];
    if (newest && onActive) onActive({ status: newest.status, progress: newest.progress });
    return newest;
  }, [onActive]);

  useEffect(() => { void load(); }, [load]);

  // Poll every 4s while the newest run is still running.
  useEffect(() => {
    const t = setInterval(() => {
      if (runs[0]?.status === "running" || runs[0]?.status === "pending") void load();
    }, 4000);
    return () => clearInterval(t);
  }, [runs, load]);

  const trigger = async () => {
    setBusy(true);
    try {
      await fetch("/api/runs", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ channelId }),
      });
      setTimeout(() => { void load(); setBusy(false); }, 2000);
    } catch { setBusy(false); }
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

- [ ] **Step 2: Update** `studio/app/page.tsx` to thread progress into node data. Replace its contents with:

```tsx
"use client";
import { useState, useCallback, useMemo } from "react";
import {
  ReactFlow, Background, Controls, type Node, type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CANVAS_NODES, CANVAS_EDGES, nodeRunStatus, type RunProgress } from "./canvas/nodes";
import { StageNode } from "@/components/canvas/StageNode";
import { RunBar } from "@/components/canvas/RunBar";
import { SidePanel } from "@/components/canvas/SidePanel";

const nodeTypes = { stage: StageNode };
const edges: Edge[] = CANVAS_EDGES.map((e) => ({ ...e, animated: true }));

export default function Home() {
  const [selected, setSelected] = useState<string | null>(null);
  const [active, setActive] = useState<{ status?: string; progress?: RunProgress }>({});
  const onNodeClick = useCallback((_: unknown, n: Node) => setSelected(n.id), []);
  const onActive = useCallback(
    (s: { status?: string; progress?: RunProgress }) => setActive(s), []);

  const nodes: Node[] = useMemo(() => CANVAS_NODES.map((n) => ({
    ...n,
    data: { ...n.data, runStatus: nodeRunStatus(n.id, active.progress, active.status) },
  })) as unknown as Node[], [active]);

  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <RunBar channelId="eason" onActive={onActive} />
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

- [ ] **Step 3: Update** `studio/components/canvas/StageNode.tsx` to show the run-status accent:

```tsx
"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";

const STATUS_COLOR: Record<string, string> = {
  running: "#2563eb", done: "#15803d", error: "#b91c1c",
  pending: "#6b7280", skipped: "#4b5563",
};

export function StageNode({ data, selected }: NodeProps) {
  const d = data as { title: string; subtitle: string; accent: string; runStatus?: string | null };
  const sc = d.runStatus ? STATUS_COLOR[d.runStatus] : undefined;
  return (
    <div style={{
      minWidth: 130, padding: "10px 12px", borderRadius: 8,
      background: "#1f2937", color: "#e5e7eb",
      border: `2px solid ${selected ? d.accent : (sc ?? "#374151")}`,
      boxShadow: selected ? `0 0 0 2px ${d.accent}55`
        : sc ? `0 0 0 2px ${sc}55` : "none", cursor: "pointer",
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {sc && <span style={{ width: 8, height: 8, borderRadius: 4, background: sc,
          ...(d.runStatus === "running" ? { animation: "pulse 1s infinite" } : {}) }} />}
        <span style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</span>
      </div>
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>
        {d.subtitle}{d.runStatus ? ` · ${d.runStatus}` : ""}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

- [ ] **Step 4: Verify build + types + full suite**

Run: `cd studio && npx tsc --noEmit && npx next build && npx vitest run`
Expected: tsc clean; `next build` succeeds; all tests pass (no test/lib regression — page/RunBar/StageNode are not unit-tested; `nodeRunStatus` tests from Task 2 still pass).

- [ ] **Step 5: Commit + push**

```bash
git add studio/components/canvas/RunBar.tsx studio/app/page.tsx studio/components/canvas/StageNode.tsx
git commit -m "feat(canvas): live per-stage node colouring while a run is in flight (canvas live progress)"
git push origin main
```

---

### Task 4: Acceptance + honest evidence

**Files:**
- Modify: `docs/superpowers/plans/PHASE2-EVIDENCE.md`

Operational (controller-run).

- [ ] **Step 1:** Confirm the deterministic path: a fake-CLI `runPipeline` (covered by Task 1 tests) yields `progress {digest:skipped, analysis:done, postprocess:done, quality:done}`; the digest-failure test yields `progress.digest:"error"`. Re-run the targeted tests and record the result.

- [ ] **Step 2:** Start `cd studio && npx next start -p 3100`. Trigger a real `eason` run from the canvas (or `POST /api/runs`). Within the first ~1–2 min, poll `/api/runs/<newest>` a few times and capture the evolving `progress` object (it should show `digest:"running"` then `digest:"done"` then `analysis:"running"`…). You do NOT need to wait the full ~15 min — capturing at least one live `running→done` transition on a real run is sufficient evidence that the runner emits progress and the API surfaces it. Note honestly if you stop before completion.

- [ ] **Step 3:** Append a dated **"Canvas live progress (v1.1)"** section to `docs/superpowers/plans/PHASE2-EVIDENCE.md`: the deterministic test evidence, the captured real-run `progress` transition(s), the honest limitation (channels static, persistence derived, visual node colouring still needs a human eyeball in the browser), and a plain verdict. Restore any test mutations; clean the tree. Commit + push. KG `record_experience`.

---

## Self-Review

**1. Spec coverage:** "show which stage is running/done/errored on the canvas" → Task 1 (runner emits `progress`), Task 2 (pure mapping incl. honest channels=null / persistence=derived), Task 3 (poll + colour nodes), Task 4 (prove it). The accepted limitation (4 observable stages; channels/persistence not live) is encoded in `nodeRunStatus` and stated in evidence.

**2. Placeholder scan:** No TBD/TODO; every step has full code or an exact command + expected result.

**3. Type consistency:** `RunProgress`/`StepState` defined in `runRecord.ts` (Task 1) and intentionally re-declared identically in `nodes.ts` (Task 2) with a stated rationale (frontend module must stay server-import-free, mirroring the existing no-`@xyflow`-in-nodes.ts rule); the literals match exactly (`pending|running|done|error|skipped`; digest/analysis/postprocess/quality). `nodeRunStatus(nodeId, progress, runStatus)` signature identical across Task 2 def, its test, and the Task 3 `page.tsx` call. `RunBar`'s new optional `onActive` prop is additive — `page.tsx` supplies it; no other caller exists. `updateRun` shallow-merge handled by always writing the whole `progress` object.

**Open risks (flagged):** (a) Task 1 adds several `updateRun` (read-modify-write of run.json) calls per run — fine for this low-frequency single-run tool; not a concern at this scale. (b) The success path must set `progress.quality="done"` and include `progress` in the final `updateRun` patch — Step 4 specifies exactly where; the implementer must not drop it (Task 1 test only asserts the fake path where quality reaches "done", so a missed wire would fail that test — the test is the guard). (c) Real-run capture in Task 4 is timing-sensitive; polling every few seconds in the first 1–2 min reliably catches the digest/analysis transitions since the digest pass alone takes minutes.
