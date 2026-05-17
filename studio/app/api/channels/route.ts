import { NextRequest, NextResponse } from "next/server";
import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import YAML from "yaml";
import { ChannelsFile } from "@/lib/config/schema";
import { STUDIO_ROOT } from "@/lib/runner/paths";

const FILE = join(STUDIO_ROOT, "config/channels.yaml");

export async function GET() {
  return NextResponse.json(ChannelsFile.parse(YAML.parse(await readFile(FILE, "utf8"))));
}
export async function PUT(req: NextRequest) {
  const parsed = ChannelsFile.parse(await req.json());     // reject invalid before write
  await writeFile(FILE, YAML.stringify(parsed));
  return NextResponse.json({ ok: true });
}
