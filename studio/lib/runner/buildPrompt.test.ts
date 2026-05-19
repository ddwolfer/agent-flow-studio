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
  it("substitutes shell-style report vars and report css", () => {
    const out = buildPrompt({
      promptTemplate: "save to ${HTML_FILE} on ${DATE}; log ${LOG_FILE}; css:{{report_css}}",
      references: [], channel,
      calendarText: "Today is 2026-05-18 (Monday).",
      htmlPath: "/runs/r1/report.html", logPath: "/runs/r1/claude.log",
      dateIso: "2026-05-18", reportCss: "BODY{color:red}",
    });
    expect(out).toContain("save to /runs/r1/report.html on 2026-05-18");
    expect(out).toContain("log /runs/r1/claude.log");
    expect(out).toContain("css:BODY{color:red}");
    expect(out).not.toContain("${"); expect(out).not.toContain("{{report_css}}");
  });

  it("substitutes ${TRANSCRIPT_DIGEST} with the digest path", () => {
    const out = buildPrompt({
      promptTemplate: "read ${TRANSCRIPT_DIGEST} now",
      references: [], channel: {
        id: "eason", handle: "@x", name: "X", search_query: "q",
        pipeline: "eason", enabled: true,
      },
      calendarText: "CAL", transcriptDigestPath: "/runs/abc/transcript-digest.md",
    });
    expect(out).toContain("read /runs/abc/transcript-digest.md now");
  });

  it("substitutes ${TRANSCRIPT_DIGEST} with empty string when absent", () => {
    const out = buildPrompt({
      promptTemplate: "x${TRANSCRIPT_DIGEST}y", references: [],
      channel: { id: "eason", handle: "@x", name: "X", search_query: "q",
        pipeline: "eason", enabled: true },
      calendarText: "CAL",
    });
    expect(out).toContain("xy");
  });
});
