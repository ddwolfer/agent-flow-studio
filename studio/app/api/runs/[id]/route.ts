import { NextResponse } from "next/server";
import { readRun } from "@/lib/runner/runRecord";
import { RUNS_ROOT } from "@/lib/runner/paths";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  try { return NextResponse.json(await readRun(RUNS_ROOT, id)); }
  catch { return NextResponse.json({ error: "not found" }, { status: 404 }); }
}
