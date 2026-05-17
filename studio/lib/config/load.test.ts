import { describe, it, expect } from "vitest";
import { loadConfig } from "./load";
import { ConfigError } from "../runner/errors";

const ROOT = new URL("../../", import.meta.url).pathname; // studio/

describe("loadConfig", () => {
  it("loads the eason channel with its pipeline + prompts", async () => {
    const c = await loadConfig("eason", ROOT);
    expect(c.channel.handle).toBe("@m168");
    expect(c.pipeline.name).toBe("eason");
    expect(c.promptTemplate).toContain("{{calendar}}");
    expect(c.references.length).toBeGreaterThan(0);
  });
  it("throws ConfigError for an unknown channel", async () => {
    await expect(loadConfig("nope", ROOT)).rejects.toBeInstanceOf(ConfigError);
  });
  it("throws ConfigError for a disabled channel", async () => {
    await expect(loadConfig("yutinghao", ROOT)).rejects.toThrow(/disabled/);
  });
});
