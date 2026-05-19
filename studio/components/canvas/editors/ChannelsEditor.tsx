"use client";
import { useEffect, useState } from "react";

interface Ch { id: string; handle: string; name: string; search_query: string; pipeline: string; enabled: boolean; }

export function ChannelsEditor() {
  const [chs, setChs] = useState<Ch[]>([]);
  const [msg, setMsg] = useState("載入中…");

  const load = () => fetch("/api/channels").then((r) => r.json())
    .then((j) => { setChs(j.channels ?? []); setMsg(""); })
    .catch(() => setMsg("讀取失敗"));
  useEffect(() => { void load(); }, []);

  const save = async () => {
    setMsg("儲存中…");
    const r = await fetch("/api/channels", {
      method: "PUT", headers: { "content-type": "application/json" },
      body: JSON.stringify({ channels: chs }),
    });
    const j = await r.json().catch(() => ({}));
    setMsg(r.ok ? "已儲存 ✓" : `儲存失敗：${j.error ?? r.status}`);
  };

  const addBlank = () => setChs([...chs, {
    id: "new-channel", handle: "@handle", name: "新頻道",
    search_query: "搜尋關鍵字", pipeline: "eason", enabled: false,
  }]);
  const upd = (i: number, k: keyof Ch, v: string | boolean) =>
    setChs(chs.map((c, j) => j === i ? { ...c, [k]: v } : c));

  return (
    <div style={{ marginTop: 12 }}>
      <button onClick={addBlank}>+ 新增 YouTuber</button>
      {chs.map((c, i) => (
        <div key={i} style={{ border: "1px solid #30363d", borderRadius: 6, padding: 8, margin: "8px 0" }}>
          {(["id", "handle", "name", "search_query", "pipeline"] as (keyof Ch)[]).map((k) => (
            <div key={k} style={{ margin: "4px 0" }}>
              <label style={{ fontSize: 11, color: "#9ca3af" }}>{k}</label>
              <input value={String(c[k])} onChange={(e) => upd(i, k, e.target.value)}
                style={{ display: "block", width: "100%", padding: 5 }} />
            </div>
          ))}
          <label style={{ fontSize: 12, color: "#9ca3af" }}>
            <input type="checkbox" checked={c.enabled}
              onChange={(e) => upd(i, "enabled", e.target.checked)} /> enabled
          </label>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button onClick={() => void save()}>儲存 channels.yaml</button>
        <span style={{ fontSize: 12, color: "#9ca3af" }}>{msg}</span>
      </div>
    </div>
  );
}
