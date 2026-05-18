import { describe, it, expect, beforeEach } from "vitest";
import { mkdtemp, writeFile, readFile, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { renderMcpConfig } from "./mcpConfig";

let root: string;
beforeEach(async () => { root = await mkdtemp(join(tmpdir(), "mc-")); });

describe("renderMcpConfig", () => {
  it("substitutes tokens and injects FRED key from the inherited .env", async () => {
    const mcpDir = join(root, "studio", "mcp");
    await mkdir(mcpDir, { recursive: true });
    await writeFile(join(mcpDir, "mcp.json.tmpl"),
      JSON.stringify({ mcpServers: { fred: { command: "@PY@",
        args: ["@MCPDIR@/servers/fred_server.py"], env: { FRED_API_KEY: "@FREDKEY@" } },
        sqlite: { command: "@PY@", args: ["@MCPDIR@/servers/sqlite_server.py"],
          env: { STUDIO_DB_PATH: "@DBPATH@" } } } }));
    const envFile = join(root, ".env");
    await writeFile(envFile, "DISCORD_WEBHOOK=secret\nFRED_API_KEY=ABC123\n");
    const out = join(mcpDir, "mcp.json");
    await renderMcpConfig({ mcpDir, envFile, dbPath: "/db/financial.db",
      pythonBin: "/v/python", outPath: out });
    const cfg = JSON.parse(await readFile(out, "utf8"));
    expect(cfg.mcpServers.fred.env.FRED_API_KEY).toBe("ABC123");
    expect(cfg.mcpServers.fred.command).toBe("/v/python");
    expect(cfg.mcpServers.fred.args[0]).toBe(mcpDir + "/servers/fred_server.py");
    expect(cfg.mcpServers.sqlite.env.STUDIO_DB_PATH).toBe("/db/financial.db");
    expect(JSON.stringify(cfg)).not.toContain("secret");
  });

  it("throws if FRED_API_KEY missing from env file", async () => {
    const mcpDir = join(root, "m"); await mkdir(mcpDir, { recursive: true });
    await writeFile(join(mcpDir, "mcp.json.tmpl"), "{}");
    const envFile = join(root, ".env"); await writeFile(envFile, "X=1\n");
    await expect(renderMcpConfig({ mcpDir, envFile, dbPath: "d",
      pythonBin: "p", outPath: join(mcpDir, "mcp.json") })).rejects.toThrow(/FRED_API_KEY/);
  });
});
