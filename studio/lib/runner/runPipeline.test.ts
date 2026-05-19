import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readdir, access } from "node:fs/promises";
import { constants } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runPipeline } from "./runPipeline";
import { spawnProc } from "./spawnProc";

const STUDIO = new URL("../../", import.meta.url).pathname;
const FAKE = new URL("../../test/fixtures/fake-claude.sh", import.meta.url).pathname;
let runsRoot: string;
beforeEach(async () => { runsRoot = await mkdtemp(join(tmpdir(), "rp-")); });

describe("runPipeline", () => {
  it("runs eason end-to-end with the fake CLI and records success", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) =>
        file.endsWith("fake-claude.sh")
          ? spawnProc(file, args, opts)
          : { code: 0 },
    });
    expect(r.status).toBe("succeeded");
    expect(r.reportOk).toBe(true);
  });
  it("rejects an unknown channel before creating a run dir", async () => {
    await expect(runPipeline("nope", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async () => ({ code: 0 }),
    })).rejects.toThrow(/unknown channel/);
    const { readdir } = await import("node:fs/promises");
    expect(await readdir(runsRoot)).toHaveLength(0);
  });
  it("records advisory qualityOk=false for the fake report but still succeeds", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) =>
        file.endsWith("fake-claude.sh") ? spawnProc(file, args, opts) : { code: 0 },
    });
    expect(r.status).toBe("succeeded");
    expect(r.qualityOk).toBe(false);
    expect(Array.isArray(r.qualityFailures)).toBe(true);
  });

  it("produces claude.log under runs/<id>/ after a fake run", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) =>
        file.endsWith("fake-claude.sh") ? spawnProc(file, args, opts) : { code: 0 },
    });
    expect(r.status).toBe("succeeded");
    // run ID comes from the run record — derive run dir from runsRoot
    const runDirs = await readdir(runsRoot);
    expect(runDirs).toHaveLength(1);
    const runDir = runDirs[0];
    if (!runDir) throw new Error("Expected exactly one run directory");
    const claudeLog = join(runsRoot, runDir, "claude.log");
    await expect(access(claudeLog, constants.F_OK)).resolves.toBeUndefined();
  });

  it("skips the digest pass under the fake CLI and still succeeds", async () => {
    let nonFakeClaudeCalls = 0;
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) => {
        if (file.endsWith("fake-claude.sh")) return spawnProc(file, args, opts);
        // count only non-fake claude invocations (not Chrome/bash helpers)
        if (file === "claude") nonFakeClaudeCalls++;
        return { code: 0 };
      },
    });
    expect(r.status).toBe("succeeded");
    // digest is skipped (isFake); only the picks claude call remains — not 2
    expect(nonFakeClaudeCalls).toBe(1);
    const { readdir } = await import("node:fs/promises");
    const runDirs = await readdir(runsRoot);
    expect(runDirs).toHaveLength(1);
  });

  it("records status=failed with stage=digest when the digest pass fails", async () => {
    const r = await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: "claude", // not fake — digest runs
      spawner: async () => ({ code: 0 }),                // writes no digest file
    });
    expect(r.status).toBe("failed");
    expect(r.error?.stage).toBe("digest");
  });

  it("substitutes the picks prompt so the picks claude call gets the real report path, not ${HTML_FILE}", async () => {
    let picksPromptArg: string | undefined;
    await runPipeline("eason", {
      studioRoot: STUDIO, runsRoot, claudeBin: FAKE,
      spawner: async (file, args, opts) => {
        if (file.endsWith("fake-claude.sh")) return spawnProc(file, args, opts);
        if (file === "claude") {
          const i = args.indexOf("-p");
          if (i >= 0) picksPromptArg = args[i + 1];
        }
        return { code: 0 };
      },
    });
    expect(picksPromptArg).toBeDefined();
    expect(picksPromptArg).toContain("report.html");
    expect(picksPromptArg).not.toContain("${HTML_FILE}");
    expect(picksPromptArg).not.toContain("${LOG_FILE}");
    expect(picksPromptArg).not.toContain("${DATE}");
  });
});
