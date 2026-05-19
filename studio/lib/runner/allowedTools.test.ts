import { describe, it, expect } from "vitest";
import { pipelineAllowedTools, digestAllowedTools } from "./allowedTools";

describe("allowedTools", () => {
  it("pipelineAllowedTools returns the pipeline's declared list", () => {
    expect(pipelineAllowedTools({ allowed_tools: ["mcp__fred__fred_get_series", "Write"] }))
      .toEqual(["mcp__fred__fred_get_series", "Write"]);
  });
  it("digestAllowedTools keeps only yt-dlp tools + Write + Read, order preserved", () => {
    expect(digestAllowedTools([
      "mcp__yt-dlp__ytdlp_transcript_page", "mcp__twse__twse_fmtqik",
      "Write", "Read", "Bash",
    ])).toEqual(["mcp__yt-dlp__ytdlp_transcript_page", "Write", "Read"]);
  });
  it("digestAllowedTools on undefined/empty returns empty (no Eason fallback)", () => {
    expect(digestAllowedTools(undefined)).toEqual([]);
    expect(digestAllowedTools([])).toEqual([]);
  });
});
