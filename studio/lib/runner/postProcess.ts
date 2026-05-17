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
}
export interface PostProcessResult {
  pdfOk?: boolean; notifyOk?: boolean; picksOk?: boolean; pdfPath?: string;
}

export async function postProcess(a: PostProcessArgs): Promise<PostProcessResult> {
  const res: PostProcessResult = {};
  if (a.post.pdf) {
    const pdf = a.pdfPath ?? a.htmlPath.replace(/\.html$/, ".pdf");
    const { code } = await a.spawner("google-chrome",
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
    const { code } = await a.spawner("claude",
      ["-p", a.picksPrompt, "--model", a.post.picks.model],
      { cwd: a.financeRoot });
    res.picksOk = code === 0;
  }
  return res;
}
