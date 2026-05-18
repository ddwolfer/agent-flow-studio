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
    const htmlOut = join(o.runsRoot, runId, "report.html");
    let reportCss = "";
    try { reportCss = await readFile(join(o.studioRoot, "prompts/eason/report.css"), "utf8"); } catch { reportCss = ""; }
    const prompt = buildPrompt({
      promptTemplate: cfg.promptTemplate, references: cfg.references,
      channel: cfg.channel, calendarText: cal.text,
      htmlPath: htmlOut, logPath: join(o.runsRoot, runId, "claude.log"),
      dateIso: cal.iso, reportCss,
    });
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
    let qualityOk: boolean | undefined;
    let qualityFailures: string[] | undefined;
    try {
      const _html = await readFile(cr.htmlPath, "utf8");
      const _q = mechanicalChecks(_html, { iso: cal.iso, weekday: cal.weekday });
      qualityOk = _q.ok; qualityFailures = _q.failures;
    } catch { qualityOk = false; qualityFailures = ["report HTML unreadable"]; }
    await updateRun(o.runsRoot, runId, {
      status: "succeeded", exitCode: 0, reportHtmlPath: cr.htmlPath,
      reportOk: true, pdfOk: pp.pdfOk, notifyOk: pp.notifyOk, pdfPath: pp.pdfPath,
      qualityOk, qualityFailures,
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
