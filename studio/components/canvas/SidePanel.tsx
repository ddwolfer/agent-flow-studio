"use client";
export function SidePanel({ nodeId, onClose }: { nodeId: string; onClose: () => void }) {
  return (<div style={{ padding: 16 }}>
    <button onClick={onClose} style={{ float: "right" }}>✕</button>
    <p>panel: {nodeId} (Task 6)</p>
  </div>);
}
