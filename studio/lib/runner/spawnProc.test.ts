import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readFile, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { constants } from "node:fs";
import { spawnProc } from "./spawnProc";

let dir: string;
beforeEach(async () => { dir = await mkdtemp(join(tmpdir(), "sp-")); });

describe("spawnProc", () => {
  it("returns {code:0} on successful command", async () => {
    const result = await spawnProc("node", ["-e", "process.exit(0)"]);
    expect(result).toEqual({ code: 0 });
  });

  it("returns non-zero code when process exits with failure", async () => {
    const result = await spawnProc("node", ["-e", "process.exit(2)"]);
    expect(result.code).toBe(2);
  });

  it("no logPath → no file written, still returns {code}", async () => {
    const result = await spawnProc("node", [
      "-e", "process.stdout.write('HELLO');process.stderr.write('ERR');process.exit(0)",
    ]);
    expect(result).toEqual({ code: 0 });
    // no file should exist in our dir (nothing was asked to be written)
    const files = await import("node:fs/promises").then((m) => m.readdir(dir));
    expect(files).toHaveLength(0);
  });

  it("writes stdout and stderr to logPath when provided", async () => {
    const logPath = join(dir, "claude.log");
    const result = await spawnProc("node", [
      "-e", "process.stdout.write('HELLO');process.stderr.write('ERR');process.exit(0)",
    ], { logPath });
    expect(result).toEqual({ code: 0 });
    const contents = await readFile(logPath, "utf8");
    expect(contents).toContain("HELLO");
    expect(contents).toContain("ERR");
  });

  it("creates parent directories if they do not exist", async () => {
    const logPath = join(dir, "nested", "deep", "claude.log");
    await spawnProc("node", ["-e", "process.stdout.write('OK')"], { logPath });
    const contents = await readFile(logPath, "utf8");
    expect(contents).toContain("OK");
  });

  it("still writes the log and returns code on non-zero exit", async () => {
    const logPath = join(dir, "fail.log");
    const result = await spawnProc("node", [
      "-e", "process.stdout.write('before-fail');process.stderr.write('oops');process.exit(5)",
    ], { logPath });
    expect(result.code).toBe(5);
    const contents = await readFile(logPath, "utf8");
    expect(contents).toContain("before-fail");
    expect(contents).toContain("oops");
  });

  it("backward-compatible: opts with only cwd/env (no logPath) still works", async () => {
    const result = await spawnProc("node", ["-e", "process.exit(0)"], { cwd: dir });
    expect(result).toEqual({ code: 0 });
    // no log file was written
    const files = await import("node:fs/promises").then((m) => m.readdir(dir));
    expect(files).toHaveLength(0);
  });
});
