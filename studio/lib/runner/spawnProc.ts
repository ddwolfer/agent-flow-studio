import { execFile } from "node:child_process";
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

export type SpawnOpts = { cwd?: string; env?: Record<string, string>; logPath?: string };

export type Spawner = (
  file: string, args: string[],
  opts?: SpawnOpts,
) => Promise<{ code: number }>;

// Production spawner: execFile, argument array only — no shell, no injection surface.
export const spawnProc: Spawner = (file, args, opts) =>
  new Promise((resolve) => {
    execFile(file, args, {
      cwd: opts?.cwd,
      env: { ...process.env, ...(opts?.env ?? {}) },
      maxBuffer: 64 * 1024 * 1024,
    }, (err, stdout, stderr) => {
      const code = err && typeof (err as { code?: unknown }).code === "number"
        ? (err as { code: number }).code : err ? 1 : 0;
      if (opts?.logPath) {
        try {
          mkdirSync(dirname(opts.logPath), { recursive: true });
          writeFileSync(opts.logPath,
            `=== stdout ===\n${stdout ?? ""}\n=== stderr ===\n${stderr ?? ""}\n`);
        } catch { /* best-effort: never let log write break the run */ }
      }
      resolve({ code });
    });
  });
