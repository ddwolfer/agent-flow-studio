import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readFile } from "node:fs/promises";
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

  it("passes mcp-config + allowedTools to a real (non-fake) bin", async () => {
    const seen: string[] = [];
    const spy = async (_f: string, args: string[]) => { seen.push(...args); return { code: 0 }; };
    await runClaude({ prompt: "p", model: "m", maxTurns: 5, cwd: ".", htmlOut: "/tmp/o.html",
      claudeBin: "claude", spawner: spy as any,
      mcpConfigPath: "/x/mcp.json", allowedTools: ["mcp__fred__fred_get_series", "Write"] });
    expect(seen).toContain("--mcp-config");
    expect(seen).toContain("/x/mcp.json");
    expect(seen).toContain("--strict-mcp-config");
    expect(seen.join(",")).toContain("mcp__fred__fred_get_series,Write");
  });

  it("creates claude.log when logPath is provided (fake-claude fixture)", async () => {
    const out = join(dir, "report.html");
    const logPath = join(dir, "claude.log");
    const res = await runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out }, spawner: spawnProc,
      logPath,
    });
    expect(res.exitCode).toBe(0);
    // fake-claude.sh writes to stdout (or the file); the log file must exist
    const logContent = await readFile(logPath, "utf8");
    // log file exists and has the expected sections
    expect(logContent).toContain("=== stdout ===");
    expect(logContent).toContain("=== stderr ===");
  });

  it("logPath is optional — omitting it keeps backward compat (no log file)", async () => {
    const out = join(dir, "report.html");
    const res = await runClaude({
      prompt: "hi", model: "m", maxTurns: 1, cwd: dir, htmlOut: out,
      claudeBin: FAKE, env: { FAKE_CLAUDE_OUT: out }, spawner: spawnProc,
      // no logPath
    });
    expect(res.exitCode).toBe(0);
  });
});
