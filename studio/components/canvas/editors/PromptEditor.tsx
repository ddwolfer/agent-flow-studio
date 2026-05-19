"use client";
import { useEffect, useState } from "react";

export function PromptEditor({ files }: { files: { rel: string; label: string }[] }) {
  const [rel, setRel] = useState(files[0]?.rel ?? "");
  const [content, setContent] = useState("");
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!rel) return;
    setMsg("載入中…");
    fetch(`/api/prompts?path=${encodeURIComponent(rel)}`)
      .then((r) => r.json())
      .then((j) => { setContent(j.content ?? ""); setMsg(j.error ? `錯誤：${j.error}` : ""); })
      .catch(() => setMsg("讀取失敗"));
  }, [rel]);

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/prompts", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify({ path: rel, content }),
    });
    const j = await r.json();
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  return (
    <div style={{ marginTop: 12 }}>
      <label style={{ fontSize: 12, color: "#9ca3af" }}>Prompt 檔</label>
      <select value={rel} onChange={(e) => setRel(e.target.value)}
        style={{ display: "block", width: "100%", margin: "4px 0 8px", padding: 6 }}>
        {files.map((f) => <option key={f.rel} value={f.rel}>{f.label}</option>)}
      </select>
      <textarea value={content} onChange={(e) => setContent(e.target.value)}
        spellCheck={false} style={{ width: "100%", height: 320, fontFamily: "monospace",
          fontSize: 12, background: "#0d1117", color: "#e5e7eb", border: "1px solid #30363d" }} />
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
        <button onClick={() => void save()}>儲存</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
