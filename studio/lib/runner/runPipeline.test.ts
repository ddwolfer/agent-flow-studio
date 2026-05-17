import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp } from "node:fs/promises";
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
});
