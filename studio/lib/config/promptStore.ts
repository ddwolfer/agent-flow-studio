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
