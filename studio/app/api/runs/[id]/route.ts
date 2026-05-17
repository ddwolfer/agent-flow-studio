import { NextResponse } from "next/server";
import { readRun } from "@/lib/runner/runRecord";
import { RUNS_ROOT } from "@/lib/runner/paths";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (id.includes("..") || id.includes("/") || id.includes("\\"))
    return NextResponse.json({ error: "invalid id" }, { status: 400 });
  try { return NextResponse.json(await readRun(RUNS_ROOT, id)); }
  catch { return NextResponse.json({ error: "not found" }, { status: 404 }); }
}
