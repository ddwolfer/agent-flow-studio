import { describe, it, expect } from "vitest";
import { PipelineFile } from "./schema";

const base = {
  name: "x", model: "m", max_turns: 10,
  prompt: { template: "p.md", references: [] },
  post: { pdf: true, notify: false },
  allowed_tools: ["Write", "Read"],
};

describe("PipelineFile schema", () => {
  it("accepts a pipeline WITHOUT post.picks and WITHOUT quality_judge", () => {
    const r = PipelineFile.safeParse(base);
    expect(r.success).toBe(true);
  });
  it("still accepts a pipeline WITH post.picks + quality_judge", () => {
    const r = PipelineFile.safeParse({
      ...base,
      post: { ...base.post, picks: { model: "h", prompt: "picks.md" } },
      quality_judge: { model: "m", rubric: "r.md" },
    });
    expect(r.success).toBe(true);
  });
  it("requires allowed_tools (non-empty)", () => {
    expect(PipelineFile.safeParse({ ...base, allowed_tools: undefined }).success).toBe(false);
    expect(PipelineFile.safeParse({ ...base, allowed_tools: [] }).success).toBe(false);
  });
});
