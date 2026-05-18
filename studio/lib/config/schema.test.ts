import { describe, it, expect } from "vitest";
import { ChannelsFile, PipelineFile } from "./schema";

describe("config schema", () => {
  it("accepts a valid channels file", () => {
    const parsed = ChannelsFile.parse({
      channels: [{ id: "eason", handle: "@m168", name: "Eason",
        search_query: "張貽程 外資超錢線", pipeline: "eason", enabled: true }],
    });
    expect(parsed.channels[0]!.id).toBe("eason");
  });
  it("rejects a channel missing search_query", () => {
    expect(() => ChannelsFile.parse({
      channels: [{ id: "x", handle: "@x", name: "X", pipeline: "eason", enabled: true }],
    })).toThrow();
  });
  it("accepts a valid pipeline file", () => {
    const p = PipelineFile.parse({
      name: "eason", model: "claude-sonnet-4-6", max_turns: 50,
      prompt: { template: "prompts/eason/main.md", references: ["prompts/eason/framework.md"] },
      post: { pdf: true, notify: false, picks: { model: "claude-haiku-4-5", prompt: "prompts/eason/picks.md" } },
      quality_judge: { model: "claude-sonnet-4-6", rubric: "prompts/eason/judge-rubric.md" },
    });
    expect(p.quality_judge.model).toBe("claude-sonnet-4-6");
  });
  it("accepts a pipeline file WITH quality_sections and surfaces them", () => {
    const p = PipelineFile.parse({
      name: "eason", model: "claude-sonnet-4-6", max_turns: 50,
      prompt: { template: "prompts/eason/main.md", references: [] },
      post: { pdf: true, notify: false, picks: { model: "claude-haiku-4-5", prompt: "prompts/eason/picks.md" } },
      quality_judge: { model: "claude-sonnet-4-6", rubric: "prompts/eason/judge-rubric.md" },
      quality_sections: ["指標儀表板", "風險提示"],
    });
    expect(p.quality_sections).toEqual(["指標儀表板", "風險提示"]);
  });
  it("accepts a pipeline file WITHOUT quality_sections (optional field)", () => {
    const p = PipelineFile.parse({
      name: "eason", model: "claude-sonnet-4-6", max_turns: 50,
      prompt: { template: "prompts/eason/main.md", references: [] },
      post: { pdf: true, notify: false, picks: { model: "claude-haiku-4-5", prompt: "prompts/eason/picks.md" } },
      quality_judge: { model: "claude-sonnet-4-6", rubric: "prompts/eason/judge-rubric.md" },
    });
    expect(p.quality_sections).toBeUndefined();
  });
});
