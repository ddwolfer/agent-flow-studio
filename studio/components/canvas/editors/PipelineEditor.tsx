"use client";
import { useEffect, useState } from "react";

type Section = "digest" | "analysis" | "postprocess" | "quality";

export function PipelineEditor({ section }: { section: Section }) {
  const [p, setP] = useState<any>(null);
  const [msg, setMsg] = useState("載入中…");

  useEffect(() => {
    fetch("/api/pipeline/eason").then((r) => r.json())
      .then((j) => { setP(j.pipeline ?? null); setMsg(j.error ? `錯誤：${j.error}` : ""); })
      .catch(() => setMsg("讀取失敗"));
  }, []);

  if (!p) return <p style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</p>;

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/pipeline/eason", {
      method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(p),
    });
    const j = await r.json();
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  const field = (label: string, value: string, on: (v: string) => void) => (
    <div style={{ margin: "6px 0" }}>
      <label style={{ fontSize: 12, color: "#9ca3af" }}>{label}</label>
      <input value={value} onChange={(e) => on(e.target.value)}
        style={{ display: "block", width: "100%", padding: 6, marginTop: 3 }} />
    </div>
  );

  return (
    <div style={{ marginTop: 12 }}>
      {section === "analysis" && <>
        {field("model", p.model ?? "", (v) => setP({ ...p, model: v }))}
        {field("max_turns", String(p.max_turns ?? ""), (v) => { const n = Number(v); if (!Number.isNaN(n)) setP({ ...p, max_turns: n }); })}
      </>}
      {section === "digest" && p.digest &&
        field("digest.model", p.digest.model ?? "", (v) => setP({ ...p, digest: { ...p.digest, model: v } }))}
      {section === "postprocess" && <>
        {field("post.picks.model", p.post?.picks?.model ?? "",
          (v) => setP({ ...p, post: { ...p.post, picks: { ...p.post.picks, model: v } } }))}
        <label style={{ fontSize: 12, color: "#9ca3af", display: "block", marginTop: 6 }}>
          <input type="checkbox" checked={!!p.post?.pdf}
            onChange={(e) => setP({ ...p, post: { ...p.post, pdf: e.target.checked } })} /> post.pdf
        </label>
        <label style={{ fontSize: 12, color: "#9ca3af", display: "block" }}>
          <input type="checkbox" checked={!!p.post?.notify}
            onChange={(e) => setP({ ...p, post: { ...p.post, notify: e.target.checked } })} /> post.notify
        </label>
      </>}
      {section === "quality" &&
        <div style={{ margin: "6px 0" }}>
          <label style={{ fontSize: 12, color: "#9ca3af" }}>quality_sections（一行一個）</label>
          <textarea value={(p.quality_sections ?? []).join("\n")}
            onChange={(e) => setP({ ...p, quality_sections: e.target.value.split("\n").map((s) => s.trim()).filter(Boolean) })}
            style={{ width: "100%", height: 120, fontFamily: "monospace", fontSize: 12,
              background: "#0d1117", color: "#e5e7eb", border: "1px solid #30363d", marginTop: 3 }} />
        </div>}
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button onClick={() => void save()}>儲存 pipeline</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
