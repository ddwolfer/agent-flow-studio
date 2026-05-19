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
