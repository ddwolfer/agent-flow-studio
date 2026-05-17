import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { ensureMcpServer, readJsonSafe } from './json-merge.js';

function tmp() { return mkdtempSync(join(tmpdir(), 'jm-')); }

test('adds KG server without removing existing servers', () => {
  const d = tmp(); const f = join(d, '.mcp.json');
  writeFileSync(f, JSON.stringify({ mcpServers: { 'agent-bridge': { command: 'node', args: ['x'] } } }));
  ensureMcpServer(f, 'knowledge-graph', { command: 'node', args: ['{{PROJECT_ROOT}}/mcp/knowledge-graph/main.js'] });
  const j = JSON.parse(readFileSync(f, 'utf8'));
  assert.ok(j.mcpServers['agent-bridge']);
  assert.deepEqual(j.mcpServers['knowledge-graph'].args, ['{{PROJECT_ROOT}}/mcp/knowledge-graph/main.js']);
  rmSync(d, { recursive: true, force: true });
});

test('idempotent: second call does not duplicate or change', () => {
  const d = tmp(); const f = join(d, '.mcp.json');
  writeFileSync(f, JSON.stringify({ mcpServers: {} }));
  const srv = { command: 'node', args: ['a'] };
  ensureMcpServer(f, 'knowledge-graph', srv);
  const first = readFileSync(f, 'utf8');
  ensureMcpServer(f, 'knowledge-graph', srv);
  assert.equal(readFileSync(f, 'utf8'), first);
  rmSync(d, { recursive: true, force: true });
});

test('creates file with mcpServers when missing', () => {
  const d = tmp(); const f = join(d, '.mcp.json');
  ensureMcpServer(f, 'knowledge-graph', { command: 'node', args: ['a'] });
  assert.ok(JSON.parse(readFileSync(f, 'utf8')).mcpServers['knowledge-graph']);
  rmSync(d, { recursive: true, force: true });
});

test('readJsonSafe throws on malformed JSON (never clobbers)', () => {
  const d = tmp(); const f = join(d, '.mcp.json');
  writeFileSync(f, '{ not json');
  assert.throws(() => readJsonSafe(f), /Invalid JSON/);
  rmSync(d, { recursive: true, force: true });
});
