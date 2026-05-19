"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";

const STATUS_COLOR: Record<string, string> = {
  running: "#2563eb", done: "#15803d", error: "#b91c1c",
  pending: "#6b7280", skipped: "#4b5563",
};

export function StageNode({ data, selected }: NodeProps) {
  const d = data as { title: string; subtitle: string; accent: string; runStatus?: string | null };
  const sc = d.runStatus ? STATUS_COLOR[d.runStatus] : undefined;
  return (
    <div style={{
      minWidth: 130, padding: "10px 12px", borderRadius: 8,
      background: "#1f2937", color: "#e5e7eb",
      border: `2px solid ${selected ? d.accent : (sc ?? "#374151")}`,
      boxShadow: selected ? `0 0 0 2px ${d.accent}55`
        : sc ? `0 0 0 2px ${sc}55` : "none", cursor: "pointer",
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {sc && <span style={{ width: 8, height: 8, borderRadius: 4, background: sc }} />}
        <span style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</span>
      </div>
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>
        {d.subtitle}{d.runStatus ? ` · ${d.runStatus}` : ""}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
