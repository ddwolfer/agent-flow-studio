import { describe, it, expect } from "vitest";
import { CANVAS_NODES, CANVAS_EDGES, editorFor } from "./nodes";
import { nodeRunStatus } from "./nodes";

describe("canvas nodes model", () => {
  it("has exactly the 6 fixed stage nodes with unique ids", () => {
    expect(CANVAS_NODES).toHaveLength(6);
    const ids = CANVAS_NODES.map((n) => n.id);
    expect(new Set(ids).size).toBe(6);
    expect(ids).toEqual([
      "channels", "digest", "analysis", "postprocess", "quality", "persistence",
    ]);
  });
  it("edges form the linear pipeline and reference only existing nodes", () => {
    const ids = new Set(CANVAS_NODES.map((n) => n.id));
    expect(CANVAS_EDGES).toHaveLength(5);
    for (const e of CANVAS_EDGES) {
      expect(ids.has(e.source)).toBe(true);
      expect(ids.has(e.target)).toBe(true);
    }
    expect(CANVAS_EDGES.map((e) => `${e.source}->${e.target}`)).toEqual([
      "channels->digest", "digest->analysis", "analysis->postprocess",
      "postprocess->quality", "quality->persistence",
    ]);
  });
  it("editorFor maps each node id to its editor kind, null for unknown", () => {
    expect(editorFor("channels")).toBe("channels");
    expect(editorFor("digest")).toBe("pipeline-digest");
    expect(editorFor("analysis")).toBe("pipeline-analysis");
    expect(editorFor("postprocess")).toBe("pipeline-postprocess");
    expect(editorFor("quality")).toBe("pipeline-quality");
    expect(editorFor("persistence")).toBe("persistence");
    expect(editorFor("nope")).toBeNull();
  });
});

describe("nodeRunStatus", () => {
  const prog = { digest: "done", analysis: "running", postprocess: "pending", quality: "pending" } as const;

  it("returns the progress state for the 4 observable stages", () => {
    expect(nodeRunStatus("digest", prog, "running")).toBe("done");
    expect(nodeRunStatus("analysis", prog, "running")).toBe("running");
    expect(nodeRunStatus("postprocess", prog, "running")).toBe("pending");
    expect(nodeRunStatus("quality", prog, "running")).toBe("pending");
  });
  it("channels is always neutral (null)", () => {
    expect(nodeRunStatus("channels", prog, "running")).toBeNull();
  });
  it("persistence is done only when the run succeeded, else pending", () => {
    expect(nodeRunStatus("persistence", prog, "succeeded")).toBe("done");
    expect(nodeRunStatus("persistence", prog, "running")).toBe("pending");
    expect(nodeRunStatus("persistence", prog, "failed")).toBe("pending");
  });
  it("returns null when there is no progress (no active run)", () => {
    expect(nodeRunStatus("analysis", undefined, undefined)).toBeNull();
  });
});
