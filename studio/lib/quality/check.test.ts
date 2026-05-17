import { describe, it, expect } from "vitest";
import { mechanicalChecks } from "./check";

describe("mechanicalChecks", () => {
  it("passes a report with required sections + correct weekday", () => {
    const html = "<h2>Overall signal</h2><p>Today is 2026-04-30 (Thursday).</p>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    expect(mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" }).ok).toBe(true);
  });
  it("fails when the report weekday contradicts calendar facts", () => {
    const html = "<p>Today is 2026-04-30 (Monday).</p><h2>Overall signal</h2>" +
      "<h2>Key levels</h2><h2>Picks</h2>";
    const r = mechanicalChecks(html, { iso: "2026-04-30", weekday: "Thursday" });
    expect(r.ok).toBe(false);
    expect(r.failures.join()).toMatch(/weekday/i);
  });
});
