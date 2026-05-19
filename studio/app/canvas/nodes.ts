// Static model — intentionally no @xyflow/react import so this stays unit-testable.
export interface CanvasNode {
  id: string;
  type: "stage";
  position: { x: number; y: number };
  data: { title: string; subtitle: string; accent: string };
}
export interface CanvasEdge { id: string; source: string; target: string; }

export type EditorKind =
  | "channels" | "pipeline-digest" | "pipeline-analysis"
  | "pipeline-postprocess" | "pipeline-quality" | "persistence";

const ORDER = [
  "channels", "digest", "analysis", "postprocess", "quality", "persistence",
] as const;

const META: Record<string, { title: string; subtitle: string; accent: string }> = {
  channels:    { title: "頻道",   subtitle: "channels.yaml",        accent: "#2563eb" },
  digest:      { title: "摘要",   subtitle: "Sonnet · digest.md",   accent: "#7c3aed" },
  analysis:    { title: "分析",   subtitle: "main + references",    accent: "#0d9488" },
  postprocess: { title: "後處理", subtitle: "PDF · notify · picks", accent: "#b45309" },
  quality:     { title: "品質",   subtitle: "quality_sections",     accent: "#be185d" },
  persistence: { title: "持久化", subtitle: "training/daily/picks", accent: "#15803d" },
};

export const CANVAS_NODES: CanvasNode[] = ORDER.map((id, i) => ({
  id, type: "stage",
  position: { x: i * 220, y: 80 },
  data: META[id]!,
}));

export const CANVAS_EDGES: CanvasEdge[] = ORDER.slice(1).map((id, i) => ({
  id: `e-${ORDER[i]}-${id}`, source: ORDER[i]!, target: id,
}));

const EDITORS: Record<string, EditorKind> = {
  channels: "channels",
  digest: "pipeline-digest",
  analysis: "pipeline-analysis",
  postprocess: "pipeline-postprocess",
  quality: "pipeline-quality",
  persistence: "persistence",
};

export function editorFor(nodeId: string): EditorKind | null {
  return EDITORS[nodeId] ?? null;
}

export type StepState = "pending" | "running" | "done" | "error" | "skipped";
export interface RunProgress {
  digest: StepState; analysis: StepState; postprocess: StepState; quality: StepState;
}

/** Per-node status for canvas colouring. `null` = no run-status accent (neutral).
 *  channels is config (always null); persistence is derived (runner can't observe
 *  it mid-turn) — done only when the whole run succeeded. */
export function nodeRunStatus(
  nodeId: string,
  progress: RunProgress | undefined,
  runStatus: string | undefined,
): StepState | null {
  if (nodeId === "channels") return null;
  if (nodeId === "persistence") return runStatus === "succeeded" ? "done" : "pending";
  if (!progress) return null;
  if (nodeId === "digest" || nodeId === "analysis"
      || nodeId === "postprocess" || nodeId === "quality") {
    return progress[nodeId];
  }
  return null;
}
