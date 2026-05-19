import { mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import { join } from "node:path";

export type RunStatus = "pending" | "running" | "succeeded" | "failed";
export type StepState = "pending" | "running" | "done" | "error" | "skipped";
export interface RunProgress {
  digest: StepState; analysis: StepState; postprocess: StepState; quality: StepState;
}
export interface RunRecord {
  runId: string; channelId: string; status: RunStatus;
  startedAt: string; finishedAt?: string; exitCode?: number;
  reportHtmlPath?: string; pdfPath?: string;
  reportOk?: boolean; pdfOk?: boolean; notifyOk?: boolean; notifySent?: boolean;
  qualityOk?: boolean;
  qualityFailures?: string[];
  progress?: RunProgress;
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
