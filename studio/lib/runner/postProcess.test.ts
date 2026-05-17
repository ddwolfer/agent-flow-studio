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
      runPicks: false, financeRoot: "/repo/financial-report-system", spawner: spy,
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
      runPicks: false, financeRoot: "/repo/financial-report-system", spawner: spy,
    });
    expect(r.notifyOk).toBe(false);
  });
});
