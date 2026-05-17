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
