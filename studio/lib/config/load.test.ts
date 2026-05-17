import { describe, it, expect, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
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

describe("loadConfig — YAML/schema error wrapping", () => {
  let tmpRoot: string;

  afterEach(async () => {
    if (tmpRoot) await rm(tmpRoot, { recursive: true, force: true });
  });

  it("wraps invalid YAML syntax in channels.yaml as ConfigError with /invalid YAML/", async () => {
    tmpRoot = await mkdtemp(join(tmpdir(), "load-test-"));
    await mkdir(join(tmpRoot, "config"), { recursive: true });
    // Broken YAML: unmatched bracket
    await writeFile(join(tmpRoot, "config/channels.yaml"), "channels: [{{bad yaml}}", "utf8");

    await expect(loadConfig("eason", tmpRoot)).rejects.toBeInstanceOf(ConfigError);
    await expect(loadConfig("eason", tmpRoot)).rejects.toThrow(/invalid YAML/);
  });

  it("wraps schema-invalid channels.yaml (missing required field) as ConfigError with /schema validation/", async () => {
    tmpRoot = await mkdtemp(join(tmpdir(), "load-test-"));
    await mkdir(join(tmpRoot, "config"), { recursive: true });
    // Valid YAML but missing required field `search_query` on the channel entry
    await writeFile(
      join(tmpRoot, "config/channels.yaml"),
      [
        "channels:",
        "  - id: eason",
        "    name: Eason",
        "    handle: '@m168'",
        "    enabled: true",
        "    pipeline: eason",
        // intentionally omitting search_query
      ].join("\n"),
      "utf8",
    );

    await expect(loadConfig("eason", tmpRoot)).rejects.toBeInstanceOf(ConfigError);
    await expect(loadConfig("eason", tmpRoot)).rejects.toThrow(/schema validation/);
  });
});
