import { NextRequest, NextResponse } from "next/server";
import { STUDIO_ROOT } from "@/lib/runner/paths";
import { readPrompt, writePrompt, PromptPathError } from "@/lib/config/promptStore";

export async function GET(req: NextRequest) {
  const rel = req.nextUrl.searchParams.get("path") ?? "";
  try {
    return NextResponse.json({ path: rel, content: await readPrompt(STUDIO_ROOT, rel) });
  } catch (e) {
    if (e instanceof PromptPathError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "read failed" }, { status: 500 });
  }
}

export async function PUT(req: NextRequest) {
  let body: { path?: string; content?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "bad json" }, { status: 400 }); }
  if (typeof body.path !== "string" || typeof body.content !== "string")
    return NextResponse.json({ error: "path and content required" }, { status: 400 });
  try {
    await writePrompt(STUDIO_ROOT, body.path, body.content);
    return NextResponse.json({ ok: true });
  } catch (e) {
    if (e instanceof PromptPathError) return NextResponse.json({ error: e.message }, { status: 400 });
    return NextResponse.json({ error: "write failed" }, { status: 500 });
  }
}
