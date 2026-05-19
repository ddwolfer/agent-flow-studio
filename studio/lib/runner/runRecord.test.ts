import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createRun, updateRun, sweepStale, readRun, isRunId } from "./runRecord";

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

describe("isRunId", () => {
  it("accepts real run dir names", () => {
    expect(isRunId("2026-05-19T12-53-13-571Z_eason")).toBe(true);
    expect(isRunId("2026-05-18T23-05-58-449Z_eason")).toBe(true);
    expect(isRunId("2026-01-02T03-04-05-006Z_yutinghao")).toBe(true);
  });
  it("rejects junk entries", () => {
    expect(isRunId("_e2e3.log")).toBe(false);
    expect(isRunId("_fu6_launch.log")).toBe(false);
    expect(isRunId(".DS_Store")).toBe(false);
    expect(isRunId("report.html")).toBe(false);
    expect(isRunId("")).toBe(false);
    expect(isRunId("2026-05-19T12-53-13-571Z")).toBe(false); // no _channel suffix
  });
});
