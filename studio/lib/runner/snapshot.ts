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
