import type { Spawner } from "./spawnProc";
import { ClaudeRunError } from "./errors";

export interface RunClaudeArgs {
  prompt: string; model: string; maxTurns: number; cwd: string; htmlOut: string;
  claudeBin?: string;                       // default "claude"; tests inject the fake
  env?: Record<string, string>;
  spawner: Spawner;                          // injected; prod = spawnProc
  mcpConfigPath?: string;
  allowedTools?: string[];
  logPath?: string;                         // optional: capture stdout+stderr to this file
}
export interface RunClaudeResult { exitCode: number; htmlPath: string; }

export async function runClaude(a: RunClaudeArgs): Promise<RunClaudeResult> {
  const bin = a.claudeBin ?? "claude";
  // Argument array only — prompt is a single argv element, never shell-parsed.
  const args = bin.endsWith("fake-claude.sh")
    ? []
    : ["-p", a.prompt, "--model", a.model, "--max-turns", String(a.maxTurns),
        ...(a.mcpConfigPath ? ["--mcp-config", a.mcpConfigPath, "--strict-mcp-config"] : []),
        ...(a.allowedTools && a.allowedTools.length
          ? ["--allowedTools", a.allowedTools.join(",")] : []),
      ];
  const { code } = await a.spawner(bin, args, {
    cwd: bin.endsWith("fake-claude.sh") ? undefined : a.cwd,
    env: a.env, logPath: a.logPath,
  });
  if (code !== 0) throw new ClaudeRunError(`claude exited ${code}`);
  return { exitCode: 0, htmlPath: a.htmlOut };
}
