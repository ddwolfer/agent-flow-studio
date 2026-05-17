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
}

async function readText(p: string): Promise<string> {
  try { return await readFile(p, "utf8"); }
  catch { throw new ConfigError(`missing file: ${p}`); }
}

export async function loadConfig(channelId: string, studioRoot: string): Promise<LoadedConfig> {
  const channels = ChannelsFile.parse(
    YAML.parse(await readText(join(studioRoot, "config/channels.yaml")))).channels;
  const channel = channels.find((c) => c.id === channelId);
  if (!channel) throw new ConfigError(`unknown channel: ${channelId}`);
  if (!channel.enabled) throw new ConfigError(`channel is disabled: ${channelId}`);

  const pipeline = PipelineFile.parse(
    YAML.parse(await readText(join(studioRoot, `config/pipelines/${channel.pipeline}.yaml`))));

  const promptTemplate = await readText(join(studioRoot, pipeline.prompt.template));
  const references = await Promise.all(
    pipeline.prompt.references.map((r) => readText(join(studioRoot, r))));
  const picksPrompt = await readText(join(studioRoot, pipeline.post.picks.prompt));
  const judgeRubric = await readText(join(studioRoot, pipeline.quality_judge.rubric));

  return { channel, pipeline, promptTemplate, references, picksPrompt, judgeRubric };
}
