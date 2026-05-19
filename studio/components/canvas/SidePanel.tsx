"use client";
import { editorFor } from "@/app/canvas/nodes";
import { ChannelsEditor } from "./editors/ChannelsEditor";
import { PipelineEditor } from "./editors/PipelineEditor";
import { PromptEditor } from "./editors/PromptEditor";

const REFS = [
  { rel: "prompts/eason/main.md", label: "main.md" },
  { rel: "prompts/eason/framework.md", label: "framework.md" },
  { rel: "prompts/eason/voice.md", label: "voice.md" },
  { rel: "prompts/eason/persistence.md", label: "persistence.md" },
  { rel: "prompts/eason/transcript.md", label: "transcript.md" },
];

export function SidePanel({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  const kind = editorFor(nodeId);
  return (
    <div style={{ padding: 16 }}>
      <button onClick={onClose} style={{ float: "right", background: "transparent",
        color: "#9ca3af", border: 0, fontSize: 16, cursor: "pointer" }}>✕</button>
      <h3 style={{ marginTop: 0 }}>{nodeId}</h3>
      {kind === "channels" && <ChannelsEditor />}
      {kind === "pipeline-analysis" && <>
        <PipelineEditor section="analysis" />
        <PromptEditor files={REFS} />
      </>}
      {kind === "pipeline-digest" && <>
        <PipelineEditor section="digest" />
        <PromptEditor files={[{ rel: "prompts/eason/digest.md", label: "digest.md" }]} />
      </>}
      {kind === "pipeline-postprocess" && <>
        <PipelineEditor section="postprocess" />
        <PromptEditor files={[{ rel: "prompts/eason/picks.md", label: "picks.md" }]} />
      </>}
      {kind === "pipeline-quality" && <PipelineEditor section="quality" />}
      {kind === "persistence" && (
        <p style={{ fontSize: 13, color: "#9ca3af" }}>
          持久化：每次 run 寫入 SQLite 的 eason_training（影片樣本）、eason_daily（每日觀點）、
          eason_picks（選股追蹤）。v1 唯讀展示，不在畫布編輯。
        </p>
      )}
    </div>
  );
}
