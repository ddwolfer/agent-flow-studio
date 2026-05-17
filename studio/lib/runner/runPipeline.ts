import { join } from "node:path";
import { loadConfig } from "../config/load";
import { calendarFacts } from "./calendar";
import { buildPrompt } from "./buildPrompt";
import { runClaude } from "./runClaude";
import { postProcess } from "./postProcess";
import { createRun, updateRun, readRun, type RunRecord } from "./runRecord";
import { gitSha, hashAll } from "./snapshot";
import type { Spawner } from "./spawnProc";
import { ConfigError, ClaudeRunError } from "./errors";

export interface RunPipelineOpts {
  studioRoot: string; runsRoot: string;
  notify?: boolean; claudeBin?: string; spawner: Spawner; now?: Date;
}

export async function runPipeline(channelId: string,
  o: RunPipelineOpts): Promise<RunRecord> {
  const cfg = await loadConfig(channelId, o.studioRoot); // config errors: no run dir
  const financeRoot = join(o.studioRoot, "../financial-report-system");
  const snap = { gitSha: gitSha(o.studioRoot),
    promptHashes: hashAll({ main: cfg.promptTemplate, picks: cfg.picksPrompt }) };
  const runId = await createRun(o.runsRoot, channelId, snap);
  try {
    await updateRun(o.runsRoot, runId, { status: "running", pid: process.pid });
    const cal = calendarFacts(o.now ?? new Date());
    const prompt = buildPrompt({
      promptTemplate: cfg.promptTemplate, references: cfg.references,
      channel: cfg.channel, calendarText: cal.text,
    });
    const htmlOut = join(o.runsRoot, runId, "report.html");
    const cr = await runClaude({
      prompt, model: cfg.pipeline.model, maxTurns: cfg.pipeline.max_turns,
      cwd: financeRoot, htmlOut, claudeBin: o.claudeBin,
      env: o.claudeBin?.endsWith("fake-claude.sh")
        ? { FAKE_CLAUDE_OUT: htmlOut } : undefined, spawner: o.spawner,
    });
    const pp = await postProcess({
      htmlPath: cr.htmlPath, financeRoot,
      post: { ...cfg.pipeline.post, notify: o.notify ?? cfg.pipeline.post.notify },
      runPicks: true, picksPrompt: cfg.picksPrompt, spawner: o.spawner,
    });
    await updateRun(o.runsRoot, runId, {
      status: "succeeded", exitCode: 0, reportHtmlPath: cr.htmlPath,
      reportOk: true, pdfOk: pp.pdfOk, notifyOk: pp.notifyOk, pdfPath: pp.pdfPath,
    });
  } catch (e) {
    const stage = e instanceof ConfigError ? "loadConfig"
      : e instanceof ClaudeRunError ? "runClaude" : "postProcess";
    await updateRun(o.runsRoot, runId, {
      status: "failed",
      error: { stage, message: e instanceof Error ? e.message : String(e),
        claudeLogPath: join(o.runsRoot, runId, "claude.log") },
    });
  }
  return readRun(o.runsRoot, runId);
}
