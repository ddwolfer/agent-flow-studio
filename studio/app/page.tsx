"use client";
import { useEffect, useState } from "react";

interface Ch { id: string; name: string; handle: string; enabled: boolean; }

export default function Home() {
  const [channels, setChannels] = useState<Ch[]>([]);
  const [runs, setRuns] = useState<string[]>([]);
  const load = async () => {
    setChannels((await (await fetch("/api/channels")).json()).channels);
    setRuns((await (await fetch("/api/runs")).json()).runs);
  };
  useEffect(() => { void load(); }, []);
  const run = async (id: string) => {
    await fetch("/api/runs", { method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ channelId: id }) });
    setTimeout(() => void load(), 1500);
  };
  return (<main>
    <h1>agent-flow-studio</h1>
    <h2>Channels</h2>
    <ul>{channels.map((c) => (<li key={c.id}>
      {c.name} ({c.handle}) {c.enabled ? "" : "(disabled) "}
      <button disabled={!c.enabled} onClick={() => void run(c.id)}>Run</button>
    </li>))}</ul>
    <h2>Runs</h2>
    <ul>{runs.map((r) => (<li key={r}>{r}</li>))}</ul>
  </main>);
}
