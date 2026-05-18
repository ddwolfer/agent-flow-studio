import { describe, it, expect } from "vitest";
import { postProcess } from "./postProcess";
import type { Spawner } from "./spawnProc";

const okPipelinePost = { pdf: true, notify: false,
  picks: { model: "claude-haiku-4-5", prompt: "p" } };

describe("postProcess", () => {
  it("runs the pdf step when enabled and records pdfOk", async () => {
    const seen: string[] = [];
    const spy: Spawner = async (file) => { seen.push(file); return { code: 0 }; };
    const r = await postProcess({
      htmlPath: "/tmp/r.html", post: okPipelinePost as any,
      runPicks: false, picksPrompt: "PICKS_PROMPT_TEXT",
      financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    expect(seen.some((f) => /chrome/i.test(f))).toBe(true);
    expect(r.pdfOk).toBe(true);
    expect(r.notifyOk).toBeUndefined();
  });
  it("notify failure does not throw; sets notifyOk=false", async () => {
    const spy: Spawner = async (file) =>
      ({ code: file.includes("bash") ? 1 : 0 });
    const r = await postProcess({
      htmlPath: "/tmp/r.html",
      post: { ...okPipelinePost, pdf: false, notify: true } as any,
      runPicks: false, picksPrompt: "PICKS_PROMPT_TEXT",
      financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    expect(r.notifyOk).toBe(false);
  });
  it("passes the picks prompt text to claude when runPicks", async () => {
    const calls: { file: string; args: string[] }[] = [];
    const spy: Spawner = async (file, args) => { calls.push({ file, args }); return { code: 0 }; };
    const r = await postProcess({
      htmlPath: "/tmp/r.html",
      post: { pdf: false, notify: false, picks: { model: "claude-haiku-4-5", prompt: "p" } } as any,
      runPicks: true, picksPrompt: "EXTRACT-EASON-PICKS-PROMPT",
      financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    const claudeCall = calls.find((c) => c.file === "claude");
    expect(claudeCall).toBeTruthy();
    expect(claudeCall!.args).toContain("EXTRACT-EASON-PICKS-PROMPT");
    expect(claudeCall!.args).not.toContain("extract picks");
    expect(r.picksOk).toBe(true);
  });
  it("uses a resolvable chrome binary for the pdf step", async () => {
    const seen: string[] = [];
    const spy: Spawner = async (file) => { seen.push(file); return { code: 0 }; };
    await postProcess({ htmlPath: "/tmp/r.html",
      post: { pdf: true, notify: false, picks: { model: "h", prompt: "p" } } as any,
      runPicks: false, picksPrompt: "x",
      financeRoot: "/repo/financial-report-system", spawner: spy });
    expect(seen.some((f) => /chrome/i.test(f))).toBe(true);
  });
});
