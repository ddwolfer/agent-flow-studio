import { existsSync, readFileSync, writeFileSync } from 'node:fs';

export function readJsonSafe(file) {
  if (!existsSync(file)) return null;
  const raw = readFileSync(file, 'utf8');
  try {
    return JSON.parse(raw);
  } catch (e) {
    throw new Error(`Invalid JSON in ${file}: ${e.message} (aborting; file left untouched)`);
  }
}

export function ensureMcpServer(file, name, serverDef) {
  const json = readJsonSafe(file) ?? {};
  if (!json.mcpServers || typeof json.mcpServers !== 'object') json.mcpServers = {};
  json.mcpServers[name] = serverDef;
  writeFileSync(file, JSON.stringify(json, null, 2) + '\n');
}
