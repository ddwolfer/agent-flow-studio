import { stat } from "node:fs/promises";
import type { Channel } from "../config/schema";
import type { Spawner } from "./spawnProc";
import { buildPrompt } from "./buildPrompt";
import { runClaude } from "./runClaude";
import { digestAllowedTools } from "./allowedTools";
import { ClaudeRunError } from "./errors";

// a valid minimal digest is several hundred bytes; 200 is a safety floor to catch empty/truncated output
const MIN_DIGEST_BYTES = 200;

export interface DigestPassArgs {
  digestPromptTemplate: string;
  channel: Channel;
  calendarText: string;
  dateIso: string;
  digestPath: string;            // runs/<id>/transcript-digest.md
  model: string;
  maxTurns: number;
  cwd: string;
  claudeBin?: string;
  spawner: Spawner;
  mcpConfigPath?: string;
  allowedTools?: string[];       // full list; reduced to yt-dlp + Write + Read
  logPath: string;               // runs/<id>/digest.log
}

export async function digestPass(a: DigestPassArgs): Promise<void> {
  const prompt = buildPrompt({
    promptTemplate: a.digestPromptTemplate,
    references: [],
    channel: a.channel,
    calendarText: a.calendarText,
    dateIso: a.dateIso,
    transcriptDigestPath: a.digestPath,
  });
  await runClaude({
    prompt,
    model: a.model,
    maxTurns: a.maxTurns,
    cwd: a.cwd,
    htmlOut: a.digestPath,        // unused by digest; runClaude just echoes it back
    claudeBin: a.claudeBin,
    spawner: a.spawner,
    mcpConfigPath: a.mcpConfigPath,
    allowedTools: digestAllowedTools(a.allowedTools),
    logPath: a.logPath,
  });
  let size = 0;
  try { size = (await stat(a.digestPath)).size; } catch { size = 0; }
  if (size < MIN_DIGEST_BYTES) {
    throw new ClaudeRunError(
      `digest pass produced no usable digest (${size} bytes at ${a.digestPath})`);
  }
}
