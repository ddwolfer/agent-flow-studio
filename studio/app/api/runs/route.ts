import { NextRequest, NextResponse } from "next/server";
import { readdir } from "node:fs/promises";
import { runPipeline } from "@/lib/runner/runPipeline";
import { spawnProc } from "@/lib/runner/spawnProc";
import { RUNS_ROOT, STUDIO_ROOT } from "@/lib/runner/paths";

export async function POST(req: NextRequest) {
  const { channelId, notify } = await req.json();
  // Fire-and-forget: failures are recorded in run.json; never crash the route.
  void runPipeline(channelId, {
    studioRoot: STUDIO_ROOT, runsRoot: RUNS_ROOT, notify, spawner: spawnProc,
  }).catch(() => {});
  return NextResponse.json({ started: true });
}

export async function GET() {
  let ids: string[] = [];
  try { ids = await readdir(RUNS_ROOT); } catch { /* none yet */ }
  return NextResponse.json({ runs: ids.sort().reverse() });
}
