// Offline end-to-end: copy repo to temp, run initialize.js --no-team, assert
// machine-correct output, then re-run to assert idempotency.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, cpSync, rmSync, readFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const REPO = process.cwd();
const work = mkdtempSync(join(tmpdir(), 'ai-tmpl-smoke-'));
cpSync(REPO, work, {
  recursive: true,
  filter: (s) => !/[\\/](\.git|node_modules)([\\/]|$)/.test(s)
});

function init() {
  return spawnSync('node', ['scripts/initialize.js', '--name', 'SmokeProj',
    '--desc', 'smoke test project', '--no-team'],
    { cwd: work, encoding: 'utf8' });
}

test('initialize.js --no-team succeeds', () => {
  const r = init();
  assert.equal(r.status, 0, r.stderr);
});

test('.mcp.json valid + KG server with real absolute main.js path', () => {
  const j = JSON.parse(readFileSync(join(work, '.mcp.json'), 'utf8'));
  const mainPath = j.mcpServers['knowledge-graph'].args[0];
  assert.ok(existsSync(mainPath), `main.js not found at ${mainPath}`);
  assert.ok(!/\{\{/.test(mainPath), 'placeholder not substituted');
});

test('.claude/settings.json valid + 4 hook scripts resolve on disk', () => {
  const s = JSON.parse(readFileSync(join(work, '.claude/settings.json'), 'utf8'));
  const cmds = JSON.stringify(s).match(/node ([^"]+\.js)/g).map(x => x.slice(5));
  for (const p of cmds) assert.ok(existsSync(p), `hook missing: ${p}`);
});

test('no leftover {{PLACEHOLDERS}} in generated configs/docs', () => {
  for (const f of ['.mcp.json', '.claude/settings.json', 'CLAUDE.md', 'README.md']) {
    assert.ok(!/\{\{[A-Z0-9_]+\}\}/.test(readFileSync(join(work, f), 'utf8')),
      `placeholder remains in ${f}`);
  }
});

test('CLAUDE.md has KG-BRIEFING block + project name stamped', () => {
  const c = readFileSync(join(work, 'CLAUDE.md'), 'utf8');
  assert.ok(c.includes('KG-BRIEFING:START') && c.includes('KG-BRIEFING:END'));
  assert.ok(c.includes('SmokeProj'));
});

test('idempotent: second run still exit 0 and configs unchanged', () => {
  const before = readFileSync(join(work, '.mcp.json'), 'utf8');
  const r = init();
  assert.equal(r.status, 0, r.stderr);
  assert.equal(readFileSync(join(work, '.mcp.json'), 'utf8'), before);
});

test.after(() => rmSync(work, { recursive: true, force: true }));
