import { describe, it, expect } from "vitest";
import { EASON_ALLOWED_TOOLS, digestAllowedTools } from "./allowedTools";

describe("allowedTools", () => {
  it("EASON_ALLOWED_TOOLS includes the paged transcript tool, Write and Read", () => {
    expect(EASON_ALLOWED_TOOLS).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(EASON_ALLOWED_TOOLS).toContain("Write");
    expect(EASON_ALLOWED_TOOLS).toContain("Read");
  });
  it("digestAllowedTools keeps only yt-dlp tools + Write + Read", () => {
    const r = digestAllowedTools([
      "mcp__yt-dlp__ytdlp_search_videos", "mcp__sqlite__query",
      "mcp__fred__fred_get_series", "Write", "Read", "Bash",
    ]);
    expect(r).toEqual([
      "mcp__yt-dlp__ytdlp_search_videos", "Write", "Read",
    ]);
  });
  it("digestAllowedTools falls back to the yt-dlp subset of EASON_ALLOWED_TOOLS when given nothing", () => {
    const r = digestAllowedTools(undefined);
    expect(r).toContain("mcp__yt-dlp__ytdlp_transcript_page");
    expect(r).toContain("Write");
    expect(r.some((t) => t.startsWith("mcp__sqlite__"))).toBe(false);
  });
});
