"use client";
import { Handle, Position, type NodeProps } from "@xyflow/react";

export function StageNode({ data, selected }: NodeProps) {
  const d = data as { title: string; subtitle: string; accent: string };
  return (
    <div style={{
      minWidth: 130, padding: "10px 12px", borderRadius: 8,
      background: "#1f2937", color: "#e5e7eb",
      border: `2px solid ${selected ? d.accent : "#374151"}`,
      boxShadow: selected ? `0 0 0 2px ${d.accent}55` : "none", cursor: "pointer",
    }}>
      <Handle type="target" position={Position.Left} />
      <div style={{ fontSize: 14, fontWeight: 600 }}>{d.title}</div>
      <div style={{ fontSize: 11, color: "#9ca3af", marginTop: 3 }}>{d.subtitle}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
