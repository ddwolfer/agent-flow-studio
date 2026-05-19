import { NextRequest, NextResponse } from "next/server";
import { readdir } from "node:fs/promises";
import { join } from "node:path";
import { runPipeline } from "@/lib/runner/runPipeline";
import { spawnProc } from "@/lib/runner/spawnProc";
import { RUNS_ROOT, STUDIO_ROOT } from "@/lib/runner/paths";
import { isRunId } from "@/lib/runner/runRecord";
import { loadConfig } from "@/lib/config/load";
import { renderMcpConfig } from "@/lib/runner/mcpConfig";
import { pipelineAllowedTools } from "@/lib/runner/allowedTools";

export async function POST(req: NextRequest) {
  const { channelId, notify } = await req.json();

  // Resolve the channel's pipeline tool allow-list + render mcp.json (best-effort:
  // if either fails the run still starts and the failure is recorded in run.json).
  let allowedTools: string[] | undefined;
  let mcpConfigPath: string | undefined;
  try {
    const cfg = await loadConfig(channelId, STUDIO_ROOT);
    allowedTools = pipelineAllowedTools(cfg.pipeline);
  } catch { /* loadConfig will throw again inside runPipeline and be recorded */ }
  try {
    mcpConfigPath = await renderMcpConfig({
      mcpDir: join(STUDIO_ROOT, "mcp"),
      envFile: join(STUDIO_ROOT, "../financial-report-system/scripts/.env"),
      dbPath: join(STUDIO_ROOT, "../financial-report-system/data/financial.db"),
      pythonBin: join(STUDIO_ROOT, "mcp/.venv/bin/python"),
      outPath: join(STUDIO_ROOT, "mcp/mcp.json"),
    });
  } catch { /* no MCP config → degraded run, still recorded */ }

  void runPipeline(channelId, {
    studioRoot: STUDIO_ROOT, runsRoot: RUNS_ROOT, notify,
    spawner: spawnProc, mcpConfigPath, allowedTools,
  }).catch(() => {});
  return NextResponse.json({ started: true });
}

export async function GET() {
  let ids: string[] = [];
  try { ids = await readdir(RUNS_ROOT); } catch { /* none yet */ }
  return NextResponse.json({ runs: ids.filter(isRunId).sort().reverse() });
}
