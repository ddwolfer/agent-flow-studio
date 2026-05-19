import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { PipelineFile, ChannelsFile, type PipelineConfig } from "./schema";

export class PipelineStoreError extends Error {
  constructor(m: string) { super(m); this.name = "PipelineStoreError"; }
}

/** Pipeline names allowed = the distinct `pipeline` values referenced in channels.yaml. */
async function allowedPipelines(root: string): Promise<Set<string>> {
  let raw: string;
  try { raw = await readFile(join(root, "config/channels.yaml"), "utf8"); }
  catch { throw new PipelineStoreError("channels.yaml not readable"); }
  let parsed;
  try { parsed = ChannelsFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid channels.yaml: ${e instanceof Error ? e.message : String(e)}`); }
  return new Set(parsed.channels.map((c) => c.pipeline));
}

async function pathFor(root: string, name: string): Promise<string> {
  const allowed = await allowedPipelines(root);
  if (!allowed.has(name)) throw new PipelineStoreError(`unknown pipeline: ${name}`);
  return join(root, `config/pipelines/${name}.yaml`);
}

export async function readPipeline(root: string, name: string): Promise<PipelineConfig> {
  const p = await pathFor(root, name);
  let raw: string;
  try { raw = await readFile(p, "utf8"); }
  catch { throw new PipelineStoreError(`pipeline file not readable: ${name}`); }
  try { return PipelineFile.parse(YAML.parse(raw)); }
  catch (e) { throw new PipelineStoreError(`invalid pipeline ${name}: ${e instanceof Error ? e.message : String(e)}`); }
}

export async function writePipeline(root: string, name: string, obj: unknown): Promise<void> {
  const p = await pathFor(root, name);
  let valid: PipelineConfig;
  try { valid = PipelineFile.parse(obj); }
  catch (e) { throw new PipelineStoreError(`schema validation failed: ${e instanceof Error ? e.message : String(e)}`); }
  await writeFile(p, YAML.stringify(valid), "utf8");
}
