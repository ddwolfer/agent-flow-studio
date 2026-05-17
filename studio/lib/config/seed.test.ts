import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import YAML from "yaml";
import { ChannelsFile, PipelineFile } from "./schema";

describe("seeded config", () => {
  it("channels.yaml + eason.yaml satisfy the schema", () => {
    const root = new URL("../../", import.meta.url).pathname;
    ChannelsFile.parse(YAML.parse(readFileSync(root + "config/channels.yaml", "utf8")));
    PipelineFile.parse(YAML.parse(readFileSync(root + "config/pipelines/eason.yaml", "utf8")));
    expect(true).toBe(true);
  });
});
