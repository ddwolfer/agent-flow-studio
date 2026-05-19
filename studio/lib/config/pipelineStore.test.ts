import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, mkdir, copyFile, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readPipeline, writePipeline, PipelineStoreError } from "./pipelineStore";

const REAL_EASON = new URL("../../config/pipelines/eason.yaml", import.meta.url).pathname;
let root: string;
beforeEach(async () => {
  root = await mkdtemp(join(tmpdir(), "pl-"));
  await mkdir(join(root, "config/pipelines"), { recursive: true });
  await copyFile(REAL_EASON, join(root, "config/pipelines/eason.yaml"));
});

describe("pipelineStore", () => {
  it("reads + validates the eason pipeline", async () => {
    const p = await readPipeline(root, "eason");
    expect(p.name).toBe("eason");
    expect(p.model).toMatch(/sonnet/);
  });
  it("writes a valid pipeline and reads it back", async () => {
    const p = await readPipeline(root, "eason");
    p.max_turns = 42;
    await writePipeline(root, "eason", p);
    const again = await readPipeline(root, "eason");
    expect(again.max_turns).toBe(42);
  });
  it("rejects an unknown pipeline name", async () => {
    await expect(readPipeline(root, "../secret")).rejects.toBeInstanceOf(PipelineStoreError);
    await expect(readPipeline(root, "ghost")).rejects.toBeInstanceOf(PipelineStoreError);
  });
  it("rejects a schema-invalid write without touching the file", async () => {
    const before = await readFile(join(root, "config/pipelines/eason.yaml"), "utf8");
    await expect(writePipeline(root, "eason", { name: "eason" } as never))
      .rejects.toBeInstanceOf(PipelineStoreError);
    expect(await readFile(join(root, "config/pipelines/eason.yaml"), "utf8")).toBe(before);
  });
});
