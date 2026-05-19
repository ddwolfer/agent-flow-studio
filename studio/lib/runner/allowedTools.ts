// Tool allowlists are declared per-pipeline in pipelines/<name>.yaml (allowed_tools).
// No analyst is hardcoded here.

/** The MCP/Write/Read tool ids a pipeline is allowed to use. */
export function pipelineAllowedTools(pipeline: { allowed_tools: readonly string[] }): string[] {
  return [...pipeline.allowed_tools];
}

/** Reduce an allowlist to what the digest pass may use: yt-dlp tools + Write + Read.
 *  No fallback — the pipeline must declare its tools (schema enforces non-empty). */
export function digestAllowedTools(all?: readonly string[]): string[] {
  if (!all) return [];
  const keep = (t: string) =>
    t.startsWith("mcp__yt-dlp__") || t === "Write" || t === "Read";
  return all.filter(keep);
}
