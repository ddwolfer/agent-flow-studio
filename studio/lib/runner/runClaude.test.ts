import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runClaude } from "./runClaude";
import { spawnProc } from "./spawnProc";
import { ClaudeRunError } from "./errors";

let dir: string;
beforeEach(async () => { dir = await mkdtemp(join(tmpdir(), "rc-")); });
const FAKE = new URL("../../test/fixtures/fake-claude.sh", import.meta.url).pathname;

describe("runClaude", () => {
  it("spawns the fake CLI and returns the html path on success", async () => {
    const out = join(dir, "report.html");
    const res = await runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out }, spawner: spawnProc,
    });
    expect(res.exitCode).toBe(0);
    expect(res.htmlPath).toBe(out);
  });
  it("throws ClaudeRunError on non-zero exit", async () => {
    const out = join(dir, "r.html");
    await expect(runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out, FAKE_CLAUDE_EXIT: "3" },
      spawner: spawnProc,
    })).rejects.toBeInstanceOf(ClaudeRunError);
  });
});
