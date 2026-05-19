// Canonical Eason tool allowlist. The real-run launcher and the digest pass
// derive from here so the security-critical list lives in one committed place.
export const EASON_ALLOWED_TOOLS: readonly string[] = [
  "mcp__yt-dlp__ytdlp_search_videos",
  "mcp__yt-dlp__ytdlp_download_transcript",
  "mcp__yt-dlp__ytdlp_transcript_page",
  "mcp__twse__twse_fmtqik",
  "mcp__twse__twse_mi_index",
  "mcp__twse__twse_mi_margn",
  "mcp__twse__twse_stock_day_all",
  "mcp__twse__twse_mi_qfiis_cat",
  "mcp__yahoo-finance__yahoo_quote",
  "mcp__fred__fred_get_series",
  "mcp__sqlite__query",
  "mcp__sqlite__create_record",
  "mcp__sqlite__update_records",
  "Write",
  "Read",
];

/** Reduce a full allowlist to what the digest pass may use:
 *  yt-dlp tools + Write + Read only. Falls back to the yt-dlp subset of
 *  EASON_ALLOWED_TOOLS when no list is supplied. Order is preserved. */
export function digestAllowedTools(all?: readonly string[]): string[] {
  const keep = (t: string) =>
    t.startsWith("mcp__yt-dlp__") || t === "Write" || t === "Read";
  const src = all && all.length ? all : EASON_ALLOWED_TOOLS;
  return src.filter(keep);
}
