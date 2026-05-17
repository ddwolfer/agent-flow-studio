import { describe, it, expect } from "vitest";
import { buildPrompt } from "./buildPrompt";

const channel = { id: "eason", handle: "@m168", name: "Eason",
  search_query: "Q", pipeline: "eason", enabled: true };

describe("buildPrompt", () => {
  it("interpolates channel + calendar, appends references, leaves no placeholders", () => {
    const out = buildPrompt({
      promptTemplate: "Channel {{channel.handle}} q {{channel.search_query}}\n{{calendar}}",
      references: ["REF-A", "REF-B"], channel, calendarText: "Today is 2026-04-30 (Thursday).",
    });
    expect(out).toContain("Channel @m168 q Q");
    expect(out).toContain("Today is 2026-04-30 (Thursday).");
    expect(out).toContain("REF-A");
    expect(out).toContain("REF-B");
    expect(out).not.toContain("{{");
  });
  it("is deterministic", () => {
    const args = { promptTemplate: "{{channel.name}} {{calendar}}", references: [],
      channel, calendarText: "C" } as const;
    expect(buildPrompt(args)).toBe(buildPrompt(args));
  });
});
