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
