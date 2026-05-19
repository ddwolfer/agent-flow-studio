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
