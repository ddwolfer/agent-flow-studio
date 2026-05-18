import { describe, it, expect } from "vitest";
import { mechanicalChecks } from "./check";

const ZH_SECTIONS = ["指標儀表板", "邏輯鏈", "今日語錄", "風險提示", "報告總結"] as const;
const EN_SECTIONS = ["Overall signal", "Key levels", "Picks"] as const;

describe("mechanicalChecks", () => {
  it("passes a report with required sections + correct weekday", () => {
    const html = "<h2>Overall signal</h2><p>Today is 2026-04-30 (Thursday).</p>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    expect(mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" }, EN_SECTIONS).ok).toBe(true);
  });
  it("fails when the report weekday contradicts calendar facts", () => {
    const html = "<p>Today is 2026-04-30 (Monday).</p><h2>Overall signal</h2>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    const r = mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" }, EN_SECTIONS);
    expect(r.ok).toBe(false);
    expect(r.failures.join()).toMatch(/weekday/i);
  });

  // zh-TW Eason markers
  it("passes a zh-TW report with all Eason section markers present", () => {
    const html = "<h2>② 指標儀表板</h2><h2>③ 5 層邏輯鏈分析</h2>" +
      "<h2>④ Eason 今日語錄</h2><h2>⑧ 風險提示</h2><h2>⑨ 報告總結</h2>";
    const r = mechanicalChecks(html, { iso: "2026-05-18", weekday: "Monday" }, ZH_SECTIONS);
    expect(r.ok).toBe(true);
    expect(r.failures).toHaveLength(0);
  });
  it("fails with a named failure when a zh-TW section marker is missing", () => {
    // omit 風險提示
    const html = "<h2>② 指標儀表板</h2><h2>③ 5 層邏輯鏈分析</h2>" +
      "<h2>④ Eason 今日語錄</h2><h2>⑨ 報告總結</h2>";
    const r = mechanicalChecks(html, { iso: "2026-05-18", weekday: "Monday" }, ZH_SECTIONS);
    expect(r.ok).toBe(false);
    expect(r.failures.some(f => f.includes("風險提示"))).toBe(true);
  });
  it("treats empty requiredSections as ok for the sections part", () => {
    const html = "<p>no sections here</p>";
    const r = mechanicalChecks(html, { iso: "2026-05-18", weekday: "Monday" }, []);
    expect(r.ok).toBe(true);
    expect(r.failures).toHaveLength(0);
  });
  it("weekday mismatch still fails even with empty requiredSections", () => {
    const html = "<p>Today is 2026-05-18 (Monday).</p>";
    const r = mechanicalChecks(html, { iso: "2026-05-18", weekday: "Tuesday" }, []);
    expect(r.ok).toBe(false);
    expect(r.failures.join()).toMatch(/weekday/i);
  });
});
