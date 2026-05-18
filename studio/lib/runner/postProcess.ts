import { join } from "node:path";
import type { Spawner } from "./spawnProc";
import type { PipelineConfig } from "../config/schema";

export interface PostProcessArgs {
  htmlPath: string;
  post: PipelineConfig["post"];
  runPicks: boolean;
  picksPrompt: string;             // externalized picks prompt text (from prompts/eason/picks.md)
  financeRoot: string;             // path to inherited financial-report-system/
  pdfPath?: string;
  spawner: Spawner;
  /** Pass through from RunPipelineOpts so the picks claude call gets sqlite MCP access. */
  mcpConfigPath?: string;
  allowedTools?: string[];
}
export interface PostProcessResult {
  pdfOk?: boolean; notifyOk?: boolean; picksOk?: boolean; pdfPath?: string;
}

export async function postProcess(a: PostProcessArgs): Promise<PostProcessResult> {
  const res: PostProcessResult = {};
  const { existsSync } = await import("node:fs");
  const CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
  ].find((p) => existsSync(p)) ?? "google-chrome";
  if (a.post.pdf) {
    const pdf = a.pdfPath ?? a.htmlPath.replace(/\.html$/, ".pdf");
    const { code } = await a.spawner(CHROME,
      ["--headless", `--print-to-pdf=${pdf}`, a.htmlPath]);   // arg array, no shell
    res.pdfOk = code === 0;
    if (res.pdfOk) res.pdfPath = pdf;
  }
  if (a.post.notify) {
    const { code } = await a.spawner("bash",
      [join(a.financeRoot, "scripts/notify.sh"), a.htmlPath]);
    res.notifyOk = code === 0;     // failure recorded, never thrown
  }
  if (a.runPicks) {
    const picksArgs = [
      "-p", a.picksPrompt,
      "--model", a.post.picks.model,
      ...(a.mcpConfigPath ? ["--mcp-config", a.mcpConfigPath, "--strict-mcp-config"] : []),
      ...(a.allowedTools && a.allowedTools.length
        ? ["--allowedTools", a.allowedTools.join(",")] : []),
    ];
    const { code } = await a.spawner("claude", picksArgs, { cwd: a.financeRoot });
    res.picksOk = code === 0;
  }
  return res;
}
