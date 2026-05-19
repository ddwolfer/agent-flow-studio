"use client";
import { useEffect, useState, useCallback } from "react";

interface RunStatus { id: string; status?: string; qualityOk?: boolean; }

export function RunBar({ channelId }: { channelId: string }) {
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const ids: string[] = (await (await fetch("/api/runs")).json()).runs ?? [];
    const top = ids.slice(0, 5);
    const detailed = await Promise.all(top.map(async (id) => {
      try {
        const r = await (await fetch(`/api/runs/${encodeURIComponent(id)}`)).json();
        return { id, status: r.status, qualityOk: r.qualityOk } as RunStatus;
      } catch { return { id } as RunStatus; }
    }));
    setRuns(detailed);
  }, []);

  useEffect(() => { void load(); }, [load]);

  const trigger = async () => {
    setBusy(true);
    await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ channelId }),
    });
    setTimeout(() => { void load(); setBusy(false); }, 2000);
  };

  const color = (s?: string, q?: boolean) =>
    s === "succeeded" ? (q ? "#15803d" : "#b45309")
    : s === "failed" ? "#b91c1c" : s === "running" ? "#2563eb" : "#6b7280";

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 12px",
      borderBottom: "1px solid #30363d", fontSize: 13, color: "#cbd5e1" }}>
      <button onClick={() => void trigger()} disabled={busy}
        style={{ background: "#2563eb", color: "#fff", border: 0, borderRadius: 6,
          padding: "6px 14px", cursor: busy ? "default" : "pointer" }}>
        {busy ? "啟動中…" : `▶ Run ${channelId}`}
      </button>
      <button onClick={() => void load()} style={{ background: "transparent",
        color: "#9ca3af", border: "1px solid #374151", borderRadius: 6, padding: "5px 10px" }}>
        ⟳
      </button>
      <span style={{ color: "#9ca3af" }}>最近：</span>
      {runs.length === 0 && <span style={{ color: "#6b7280" }}>（無）</span>}
      {runs.map((r) => (
        <span key={r.id} title={r.id} style={{ display: "inline-flex", gap: 5, alignItems: "center" }}>
          <span style={{ width: 8, height: 8, borderRadius: 4, background: color(r.status, r.qualityOk) }} />
          <code style={{ fontSize: 11 }}>{r.id.slice(11, 19)}</code>
          <span style={{ fontSize: 11, color: "#9ca3af" }}>
            {r.status ?? "?"}{r.status === "succeeded" ? (r.qualityOk ? " · qOK" : " · q✗") : ""}
          </span>
        </span>
      ))}
    </div>
  );
}
