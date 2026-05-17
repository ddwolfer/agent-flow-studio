#!/usr/bin/env node
// Refresh vendored knowledgeGraph from upstream into mcp/knowledge-graph/.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, cpSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const UPSTREAM = 'https://github.com/ChenLiangChong/knowledgeGraph';
const dest = resolve(process.cwd(), 'mcp/knowledge-graph');
const tmp = mkdtempSync(join(tmpdir(), 'kg-vendor-'));

try {
  console.log(`Cloning ${UPSTREAM} ...`);
  execFileSync('git', ['clone', '--depth', '1', UPSTREAM, tmp], { stdio: 'inherit' });
  rmSync(join(tmp, '.git'), { recursive: true, force: true });
  if (existsSync(dest)) rmSync(dest, { recursive: true, force: true });
  cpSync(tmp, dest, { recursive: true });
  console.log(`Vendored knowledgeGraph → ${dest}`);
  console.log('Review changes, then: git add mcp/knowledge-graph && git commit');
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
