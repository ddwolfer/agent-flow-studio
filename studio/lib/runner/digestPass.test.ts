import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, writeFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { digestPass } from "./digestPass";

let runDir: string;
beforeEach(async () => {
  runDir = await mkdtemp(join(tmpdir(), "dp-"));
});

const baseChannel = {
  id: "eason", handle: "@x", name: "X", search_query: "q",
  pipeline: "eason", enabled: true,
};

describe("digestPass", () => {
  it("resolves when the digest file is produced", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    await digestPass({
      digestPromptTemplate: "make digest at ${TRANSCRIPT_DIGEST}",
      channel: baseChannel, calendarText: "CAL", dateIso: "2026-05-19",
      digestPath, model: "claude-sonnet-4-6", maxTurns: 20,
      cwd: runDir, claudeBin: "claude",
      spawner: async () => {
        await writeFile(digestPath, "# 逐字稿摘要\n".padEnd(400, "x"));
        return { code: 0 };
      },
      logPath: join(runDir, "digest.log"),
    });
  });

  it("throws ClaudeRunError when no usable digest file is produced", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    await expect(digestPass({
      digestPromptTemplate: "x", channel: baseChannel, calendarText: "C",
      dateIso: "2026-05-19", digestPath, model: "m", maxTurns: 5,
      cwd: runDir, claudeBin: "claude",
      spawner: async () => ({ code: 0 }),    // writes nothing
      logPath: join(runDir, "digest.log"),
    })).rejects.toThrow(/digest/i);
  });

  it("passes a reduced (yt-dlp + Write + Read) allowedTools list to claude", async () => {
    const digestPath = join(runDir, "transcript-digest.md");
    let seenTools = "";
    await digestPass({
      digestPromptTemplate: "d ${TRANSCRIPT_DIGEST}", channel: baseChannel,
      calendarText: "C", dateIso: "2026-05-19", digestPath,
      model: "claude-sonnet-4-6", maxTurns: 10, cwd: runDir, claudeBin: "claude",
      allowedTools: ["mcp__yt-dlp__ytdlp_transcript_page", "mcp__sqlite__query", "Write", "Read"],
      spawner: async (_f, args) => {
        const i = args.indexOf("--allowedTools");
        seenTools = i >= 0 ? args[i + 1]! : "";
        await writeFile(digestPath, "x".padEnd(400, "x"));
        return { code: 0 };
      },
      logPath: join(runDir, "digest.log"),
    });
    expect(seenTools).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(seenTools).not.toContain("mcp__sqlite__query");
  });
});
