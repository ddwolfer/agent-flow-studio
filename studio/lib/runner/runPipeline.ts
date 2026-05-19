import { join } from "node:path";
import { readFile } from "node:fs/promises";
import { loadConfig } from "../config/load";
import { calendarFacts } from "./calendar";
import { buildPrompt } from "./buildPrompt";
import { runClaude } from "./runClaude";
import { postProcess } from "./postProcess";
import { createRun, updateRun, readRun, type RunRecord } from "./runRecord";
import { gitSha, hashAll } from "./snapshot";
import type { Spawner } from "./spawnProc";
import { ConfigError, ClaudeRunError } from "./errors";
import { mechanicalChecks } from "../quality/check";
import { digestPass } from "./digestPass";

export interface RunPipelineOpts {
  studioRoot: string; runsRoot: string;
  notify?: boolean; claudeBin?: string; spawner: Spawner; now?: Date;
  mcpConfigPath?: string;
  allowedTools?: string[];
}

export async function runPipeline(channelId: string,
  o: RunPipelineOpts): Promise<RunRecord> {
  const cfg = await loadConfig(channelId, o.studioRoot); // config errors: no run dir
  const financeRoot = join(o.studioRoot, "../financial-report-system");
  const snap = { gitSha: gitSha(o.studioRoot),
    promptHashes: hashAll({ main: cfg.promptTemplate, picks: cfg.picksPrompt }) };
  const runId = await createRun(o.runsRoot, channelId, snap);
  const claudeLogPath = join(o.runsRoot, runId, "claude.log");
  const digestPath = join(o.runsRoot, runId, "transcript-digest.md");
  const digestLogPath = join(o.runsRoot, runId, "digest.log");
  const isFake = !!o.claudeBin?.endsWith("fake-claude.sh");
  let failStage: "loadConfig" | "digest" | "runClaude" | "postProcess" = "runClaude";
  try {
    await updateRun(o.runsRoot, runId, { status: "running", pid: process.pid });
    const cal = calendarFacts(o.now ?? new Date());
    const htmlOut = join(o.runsRoot, runId, "report.html");
    let reportCss = "";
    try { reportCss = await readFile(join(o.studioRoot, "prompts/eason/report.css"), "utf8"); } catch { reportCss = ""; }
    if (!isFake && cfg.pipeline.digest && cfg.digestPrompt) {
      failStage = "digest";
      await digestPass({
        digestPromptTemplate: cfg.digestPrompt,
        channel: cfg.channel, calendarText: cal.text, dateIso: cal.iso,
        digestPath, model: cfg.pipeline.digest.model,
        maxTurns: cfg.pipeline.max_turns, cwd: financeRoot,
        claudeBin: o.claudeBin, spawner: o.spawner,
        mcpConfigPath: o.mcpConfigPath, allowedTools: o.allowedTools,
        logPath: digestLogPath,
      });
    }
    failStage = "runClaude";
    const prompt = buildPrompt({
      promptTemplate: cfg.promptTemplate, references: cfg.references,
      channel: cfg.channel, calendarText: cal.text,
      htmlPath: htmlOut, logPath: claudeLogPath,
      dateIso: cal.iso, reportCss,
      transcriptDigestPath: digestPath,
    });
    const cr = await runClaude({
      prompt, model: cfg.pipeline.model, maxTurns: cfg.pipeline.max_turns,
      cwd: financeRoot, htmlOut, claudeBin: o.claudeBin,
      env: o.claudeBin?.endsWith("fake-claude.sh")
        ? { FAKE_CLAUDE_OUT: htmlOut } : undefined, spawner: o.spawner,
      mcpConfigPath: o.mcpConfigPath,
      allowedTools: o.allowedTools,
      logPath: claudeLogPath,
    });
    const pp = await postProcess({
      htmlPath: cr.htmlPath, financeRoot,
      post: { ...cfg.pipeline.post, notify: o.notify ?? cfg.pipeline.post.notify },
      runPicks: true, picksPrompt: cfg.picksPrompt, spawner: o.spawner,
      mcpConfigPath: o.mcpConfigPath,
      allowedTools: o.allowedTools,
    });
    let qualityOk: boolean | undefined;
    let qualityFailures: string[] | undefined;
    try {
      const _html = await readFile(cr.htmlPath, "utf8");
      const _q = mechanicalChecks(_html, { iso: cal.iso, weekday: cal.weekday }, cfg.qualitySections);
      qualityOk = _q.ok; qualityFailures = _q.failures;
    } catch { qualityOk = false; qualityFailures = ["report HTML unreadable"]; }
    await updateRun(o.runsRoot, runId, {
      status: "succeeded", exitCode: 0, reportHtmlPath: cr.htmlPath,
      reportOk: true, pdfOk: pp.pdfOk, notifyOk: pp.notifyOk, pdfPath: pp.pdfPath,
      qualityOk, qualityFailures,
    });
  } catch (e) {
    const stage = e instanceof ConfigError ? "loadConfig" : failStage;
    await updateRun(o.runsRoot, runId, {
      status: "failed",
      error: { stage, message: e instanceof Error ? e.message : String(e),
        claudeLogPath },
    });
  }
  return readRun(o.runsRoot, runId);
}
