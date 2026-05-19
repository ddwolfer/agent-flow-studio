import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { PipelineFile, type PipelineConfig } from "./schema";

const ALLOWED_PIPELINES = new Set(["eason"]);

export class PipelineStoreError extends Error {
  constructor(m: string) { super(m); this.name = "PipelineStoreError"; }
}

function pathFor(root: string, name: string): string {
  if (!ALLOWED_PIPELINES.has(name)) throw new PipelineStoreError(`unknown pipeline: ${name}`);
  return join(root, `config/pipelines/${name}.yaml`);
}

export async function readPipeline(root: string, name: string): Promise<PipelineConfig> {
  const p = pathFor(root, name);
  let raw: string;
  try { raw = await readFile(p, "utf8"); }
  catch { throw new PipelineStoreError(`pipeline file not readable: ${name}`); }
  try { return PipelineFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid pipeline ${name}: ${e instanceof Error ? e.message : String(e)}`); }
}

export async function writePipeline(root: string, name: string, obj: unknown): Promise<void> {
  const p = pathFor(root, name);
  let valid: PipelineConfig;
  try { valid = PipelineFile.parse(obj); }
  catch (e) { throw new PipelineStoreError(`schema validation failed: ${e instanceof Error ? e.message : String(e)}`); }
  await writeFile(p, YAML.stringify(valid), "utf8");
}
