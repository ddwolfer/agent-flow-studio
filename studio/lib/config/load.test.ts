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
  it("eason references include persistence instructions (eason_training + eason_daily)", async () => {
    const c = await loadConfig("eason", ROOT);
    // persistence.md must be inlined — check key phrases from the file
    const allRefs = c.references.join("\n");
    expect(allRefs).toContain("eason_training");
    expect(allRefs).toContain("eason_daily");
    expect(allRefs).toContain("mcp__sqlite__create_record");
  });
  it("eason references include transcript.md (instructs tool-result usage, no file/Bash)", async () => {
    const c = await loadConfig("eason", ROOT);
    // transcript.md must be present in references
    expect(c.pipeline.prompt.references).toContain("prompts/eason/transcript.md");
    // transcript.md content must be inlined into references array
    const allRefs = c.references.join("\n");
    // Must instruct model to use mcp__yt-dlp__ytdlp_download_transcript
    expect(allRefs).toContain("mcp__yt-dlp__ytdlp_download_transcript");
    // Must explicitly prohibit Bash/file reads
    expect(allRefs).toContain("禁止");
    // Must mention the text field of the tool result
    expect(allRefs).toContain("text");
    // Must mention truncated handling
    expect(allRefs).toContain("truncated");
  });
  it("throws ConfigError for an unknown channel", async () => {
    await expect(loadConfig("nope", ROOT)).rejects.toBeInstanceOf(ConfigError);
  });
  it("throws ConfigError for a disabled channel", async () => {
    await expect(loadConfig("yutinghao", ROOT)).rejects.toThrow(/disabled/);
  });
  it("eason loadConfig surfaces qualitySections from eason.yaml", async () => {
    const c = await loadConfig("eason", ROOT);
    expect(Array.isArray(c.qualitySections)).toBe(true);
    expect(c.qualitySections.length).toBeGreaterThan(0);
    expect(c.qualitySections).toContain("指標儀表板");
    expect(c.qualitySections).toContain("風險提示");
    expect(c.qualitySections).toContain("報告總結");
  });
});

describe("loadConfig — quality_sections defaulting", () => {
  let tmpRoot: string;

  afterEach(async () => {
    if (tmpRoot) await rm(tmpRoot, { recursive: true, force: true });
  });

  it("defaults qualitySections to [] when pipeline yaml omits quality_sections", async () => {
    // Build a minimal but valid studioRoot with eason pipeline lacking quality_sections
    const src = new URL("../../", import.meta.url).pathname; // real studio/
    tmpRoot = await mkdtemp(join(tmpdir(), "load-qs-"));
    // Copy config dirs and necessary prompt files from real studio
    const { cp } = await import("node:fs/promises");
    await cp(join(src, "config"), join(tmpRoot, "config"), { recursive: true });
    await cp(join(src, "prompts"), join(tmpRoot, "prompts"), { recursive: true });
    // Overwrite eason.yaml with no quality_sections
    const originalYaml = await import("node:fs/promises").then(m =>
      m.readFile(join(src, "config/pipelines/eason.yaml"), "utf8"));
    const withoutQs = originalYaml.replace(/^quality_sections:[\s\S]*$/m, "").trimEnd() + "\n";
    await writeFile(join(tmpRoot, "config/pipelines/eason.yaml"), withoutQs, "utf8");

    const c = await loadConfig("eason", tmpRoot);
    expect(c.qualitySections).toEqual([]);
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
