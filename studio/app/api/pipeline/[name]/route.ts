import { NextRequest, NextResponse } from "next/server";
import { STUDIO_ROOT } from "@/lib/runner/paths";
import { readPipeline, writePipeline, PipelineStoreError } from "@/lib/config/pipelineStore";

export async function GET(_req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  try {
    return NextResponse.json({ name, pipeline: await readPipeline(STUDIO_ROOT, name) });
  } catch (e) {
    if (e instanceof PipelineStoreError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "read failed" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest, { params }: { params: Promise<{ name: string }> }) {
  const { name } = await params;
  let body: unknown;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "bad json" }, { status: 400 }); }
  try {
    await writePipeline(STUDIO_ROOT, name, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    if (e instanceof PipelineStoreError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "write failed" }, { status: 500 });
  }
}
