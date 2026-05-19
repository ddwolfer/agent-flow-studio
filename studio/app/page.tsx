"use client";
import { useState, useCallback } from "react";
import {
  ReactFlow, Background, Controls, type Node, type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { CANVAS_NODES, CANVAS_EDGES } from "./canvas/nodes";
import { StageNode } from "@/components/canvas/StageNode";
import { RunBar } from "@/components/canvas/RunBar";
import { SidePanel } from "@/components/canvas/SidePanel";

const nodeTypes = { stage: StageNode };
const nodes: Node[] = CANVAS_NODES as unknown as Node[];
const edges: Edge[] = CANVAS_EDGES.map((e) => ({ ...e, animated: true }));

export default function Home() {
  const [selected, setSelected] = useState<string | null>(null);
  const onNodeClick = useCallback((_: unknown, n: Node) => setSelected(n.id), []);
  return (
    <main style={{ display: "flex", flexDirection: "column", height: "100vh" }}>
      <RunBar channelId="eason" />
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        <div style={{ flex: 1 }}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes}
            onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }}>
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {selected && (
          <div style={{ width: 380, borderLeft: "1px solid #30363d", overflow: "auto",
            background: "#0d1117", color: "#e5e7eb" }}>
            <SidePanel nodeId={selected} onClose={() => setSelected(null)} />
          </div>
        )}
      </div>
    </main>
  );
}
