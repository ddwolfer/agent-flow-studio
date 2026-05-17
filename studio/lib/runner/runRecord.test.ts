import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRun, updateRun, sweepStale, readRun } from "./runRecord";

let root: string;
beforeEach(async () => { root = await mkdtemp(join(tmpdir(), "runs-")); });

describe("runRecord", () => {
  it("pending → running → succeeded persists fields", async () => {
    const id = await createRun(root, "eason", { gitSha: "abc", promptHashes: {} });
    await updateRun(root, id, { status: "running" });
    await updateRun(root, id, { status: "succeeded", reportOk: true });
    const r = await readRun(root, id);
    expect(r.status).toBe("succeeded");
    expect(r.reportOk).toBe(true);
    const onDisk = JSON.parse(await readFile(join(root, id, "run.json"), "utf8"));
    expect(onDisk.channelId).toBe("eason");
  });
  it("sweepStale marks a pid-less running run as failed", async () => {
    const id = await createRun(root, "eason", { gitSha: "x", promptHashes: {} });
    await updateRun(root, id, { status: "running", pid: 999999999 });
    await sweepStale(root);
    expect((await readRun(root, id)).status).toBe("failed");
  });
});
