import { readFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { ChannelsFile, PipelineFile, type Channel, type PipelineConfig } from "./schema";
import { ConfigError } from "../runner/errors";

export interface LoadedConfig {
  channel: Channel;
  pipeline: PipelineConfig;
  promptTemplate: string;
  references: string[];
  picksPrompt: string;
  judgeRubric: string;
  qualitySections: string[];
  digestPrompt?: string;
}

async function readText(p: string): Promise<string> {
  try { return await readFile(p, "utf8"); }
  catch { throw new ConfigError(`missing file: ${p}`); }
}

function parseYamlValidated<T>(label: string, raw: string, schema: { parse: (v: unknown) => T }): T {
  let doc: unknown;
  try { doc = YAML.parse(raw); }
  catch (e) { throw new ConfigError(`invalid YAML in ${label}: ${e instanceof Error ? e.message : String(e)}`); }
  try { return schema.parse(doc); }
  catch (e) { throw new ConfigError(`config schema validation failed for ${label}: ${e instanceof Error ? e.message : String(e)}`); }
}

export async function loadConfig(channelId: string, studioRoot: string): Promise<LoadedConfig> {
  const channels = parseYamlValidated(
    "config/channels.yaml",
    await readText(join(studioRoot, "config/channels.yaml")),
    ChannelsFile,
  ).channels;
  const channel = channels.find((c) => c.id === channelId);
  if (!channel) throw new ConfigError(`unknown channel: ${channelId}`);
  if (!channel.enabled) throw new ConfigError(`channel is disabled: ${channelId}`);

  const pipeline = parseYamlValidated(
    `config/pipelines/${channel.pipeline}.yaml (channel ${channel.id})`,
    await readText(join(studioRoot, `config/pipelines/${channel.pipeline}.yaml`)),
    PipelineFile,
  );

  const promptTemplate = await readText(join(studioRoot, pipeline.prompt.template));
  const references = await Promise.all(
    pipeline.prompt.references.map((r) => readText(join(studioRoot, r))));
  const picksPrompt = await readText(join(studioRoot, pipeline.post.picks.prompt));
  const judgeRubric = await readText(join(studioRoot, pipeline.quality_judge.rubric));

  const qualitySections = pipeline.quality_sections ?? [];
  const digestPrompt = pipeline.digest
    ? await readText(join(studioRoot, pipeline.digest.prompt))
    : undefined;
  return { channel, pipeline, promptTemplate, references, picksPrompt, judgeRubric, qualitySections, digestPrompt };
}
