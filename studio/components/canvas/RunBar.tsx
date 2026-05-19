"use client";
import { useEffect, useState, useCallback } from "react";
import type { RunProgress } from "@/app/canvas/nodes";

interface RunStatus { id: string; status?: string; qualityOk?: boolean; progress?: RunProgress; }
interface Ch { id: string; name: string; enabled: boolean; }

export function RunBar({ onActive }:
  { onActive?: (s: { status?: string; progress?: RunProgress }) => void }) {
  const [runs, setRuns] = useState<RunStatus[]>([]);
  const [busy, setBusy] = useState(false);
  const [channels, setChannels] = useState<Ch[]>([]);
  const [sel, setSel] = useState<string>("");

  useEffect(() => {
    fetch("/api/channels").then((r) => r.json()).then((j) => {
      const enabled: Ch[] = (j.channels ?? []).filter((c: Ch) => c.enabled);
      setChannels(enabled);
      setSel((s) => s || enabled[0]?.id || "");
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    const ids: string[] = (await (await fetch("/api/runs")).json()).runs ?? [];
    const top = ids.slice(0, 5);
    const detailed = await Promise.all(top.map(async (id) => {
      try {
        const r = await (await fetch(`/api/runs/${encodeURIComponent(id)}`)).json();
        return { id, status: r.status, qualityOk: r.qualityOk, progress: r.progress } as RunStatus;
      } catch { return { id } as RunStatus; }
    }));
    setRuns(detailed);
    const newest = detailed.find((d) => d.status) ?? detailed[0];
    if (newest && onActive) onActive({ status: newest.status, progress: newest.progress });
  }, [onActive]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    const t = setInterval(() => {
      if (runs[0]?.status === "running" || runs[0]?.status === "pending") void load();
    }, 4000);
    return () => clearInterval(t);
  }, [runs, load]);

  const trigger = async () => {
    if (!sel) return;
    setBusy(true);
    try {
      await fetch("/api/runs", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ channelId: sel }),
      });
      setTimeout(() => { void load(); setBusy(false); }, 2000);
    } catch { setBusy(false); }
  };

  const color = (s?: string, q?: boolean) =>
    s === "succeeded" ? (q ? "#15803d" : "#b45309")
    : s === "failed" ? "#b91c1c" : s === "running" ? "#2563eb" : "#6b7280";

  const newest = runs.find((d) => d.status) ?? runs[0];
  const inFlight = newest?.status === "running" || newest?.status === "pending";
  const disabled = busy || inFlight || !sel;

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "8px 12px",
      borderBottom: "1px solid #30363d", fontSize: 13, color: "#cbd5e1" }}>
      <select value={sel} onChange={(e) => setSel(e.target.value)}
        disabled={busy || inFlight}
        style={{ background: "#0d1117", color: "#e5e7eb", border: "1px solid #374151",
          borderRadius: 6, padding: "5px 8px", fontSize: 13 }}>
        {channels.length === 0 && <option value="">（無啟用頻道）</option>}
        {channels.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <button onClick={() => void trigger()} disabled={disabled}
        style={{ background: disabled ? "#374151" : "#2563eb", color: "#fff", border: 0,
          borderRadius: 6, padding: "6px 14px", cursor: disabled ? "default" : "pointer" }}>
        {busy ? "啟動中…" : inFlight ? "● 跑中…" : `▶ Run ${sel || "?"}`}
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
