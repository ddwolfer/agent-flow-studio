import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, mkdir, copyFile, writeFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readPipeline, writePipeline, PipelineStoreError } from "./pipelineStore";

const REAL_EASON = new URL("../../config/pipelines/eason.yaml", import.meta.url).pathname;
let root: string;
beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "pl-"));
  await mkdir(join(root, "config/pipelines"), { recursive: true });
  await copyFile(REAL_EASON, join(root, "config/pipelines/eason.yaml"));
  await writeFile(join(root, "config/channels.yaml"),
    "channels:\n" +
    "  - id: eason\n    handle: '@m168'\n    name: E\n    search_query: q\n    pipeline: eason\n    enabled: true\n" +
    "  - id: yt\n    handle: '@yt'\n    name: Y\n    search_query: q\n    pipeline: yutinghao\n    enabled: false\n");
});

describe("pipelineStore", () => {
  it("reads a pipeline whose name is referenced by some channel", async () => {
    const p = await readPipeline(root, "eason");
    expect(p.name).toBe("eason");
  });
  it("rejects a pipeline name not referenced by any channel", async () => {
    await expect(readPipeline(root, "../secret")).rejects.toBeInstanceOf(PipelineStoreError);
    await expect(readPipeline(root, "ghost")).rejects.toBeInstanceOf(PipelineStoreError);
  });
  it("allows a pipeline referenced by a (even disabled) channel — e.g. yutinghao", async () => {
    await expect(readPipeline(root, "yutinghao")).rejects.toThrow(/not readable/);
  });
  it("rejects a schema-invalid write without touching the file", async () => {
    const before = await readFile(join(root, "config/pipelines/eason.yaml"), "utf8");
    await expect(writePipeline(root, "eason", { name: "eason" } as never))
      .rejects.toBeInstanceOf(PipelineStoreError);
    expect(await readFile(join(root, "config/pipelines/eason.yaml"), "utf8")).toBe(before);
  });
});
