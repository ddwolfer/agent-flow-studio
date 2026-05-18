import { readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { ConfigError } from "./errors";

function readEnvValue(envText: string, key: string): string | null {
  for (const line of envText.split("\n")) {
    const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
    if (m && m[1] === key) return m[2]!.trim();
  }
  return null;
}

export interface RenderMcpArgs {
  mcpDir: string; envFile: string; dbPath: string;
  pythonBin: string; outPath: string;
}

export async function renderMcpConfig(a: RenderMcpArgs): Promise<string> {
  const tmpl = await readFile(join(a.mcpDir, "mcp.json.tmpl"), "utf8");
  let envText = "";
  try { envText = await readFile(a.envFile, "utf8"); }
  catch { throw new ConfigError(`inherited .env not readable: ${a.envFile}`); }
  const fred = readEnvValue(envText, "FRED_API_KEY");
  if (!fred) throw new ConfigError("FRED_API_KEY not found in inherited .env");
  const rendered = tmpl
    .replaceAll("@PY@", a.pythonBin)
    .replaceAll("@MCPDIR@", a.mcpDir)
    .replaceAll("@DBPATH@", a.dbPath)
    .replaceAll("@FREDKEY@", fred);
  await writeFile(a.outPath, rendered);
  return a.outPath;
}
