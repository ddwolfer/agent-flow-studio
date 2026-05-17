#!/usr/bin/env node
// Deterministic in-place initializer. Orchestration only; logic lives in lib/.
import { existsSync, renameSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from './lib/args.js';
import { substitute, hasPlaceholders } from './lib/placeholders.js';
import { ensureMcpServer } from './lib/json-merge.js';
import { ensureBlock } from './lib/markers.js';
import { run } from './lib/exec.js';

const ROOT = process.cwd();
const ROOT_POSIX = ROOT.split('\\').join('/');
const opts = parseArgs(process.argv.slice(2));
const name = opts.name || ROOT.split(/[\\/]/).filter(Boolean).pop();
const desc = opts.desc || `${name} — bootstrapped from AI Team Start Template`;

function preflight() {
  const [maj] = process.versions.node.split('.').map(Number);
  if (maj < 18) throw new Error(`Node ≥18 required, found ${process.versions.node}`);
  run('git', ['--version'], 'preflight: git');
  run('node', ['-e', 'process.exit(0)'], 'preflight: node');
  if (!existsSync(join(ROOT, 'mcp/knowledge-graph/main.js')))
    throw new Error('mcp/knowledge-graph/main.js missing — run: node scripts/update-vendor.js');
}

function resetGit() {
  if (!opts.resetGit) return;
  const dotgit = join(ROOT, '.git');
  if (existsSync(dotgit)) {
    const bak = join(ROOT, `.git.bak-${Date.now()}`);
    try {
      renameSync(dotgit, bak);
      console.log(`Moved .git → ${bak}`);
    } catch (e) {
      throw new Error(`Could not move .git to ${bak} (${e.code || e.message}). Close editors/git processes holding the repo, then re-run (idempotent).`);
    }
  }
  run('git', ['init'], 'git init');
}

function npmInstalls() {
  run('npm', ['install'], 'npm install (root: devDeps incl. let-them-talk)');
  run('npm', ['install'], 'npm install (mcp/knowledge-graph: native deps)',
      { cwd: join(ROOT, 'mcp/knowledge-graph') });
}

function runLetThemTalk() {
  if (!opts.team) { console.log('--no-team: skipping let-them-talk init'); return; }
  run('npx', ['--no-install', 'let-them-talk', 'init', `--${opts.providers}`,
      '--template', opts.template], 'npx let-them-talk init');
}

function mergeAndRewrite() {
  const mcpFile = join(ROOT, '.mcp.json');
  // KG server (idempotent, key-merge alongside whatever let-them-talk wrote)
  ensureMcpServer(mcpFile, 'knowledge-graph', {
    command: 'node',
    args: ['{{PROJECT_ROOT}}/mcp/knowledge-graph/main.js']
  });
  // Rewrite {{PROJECT_ROOT}} placeholders → this machine's absolute root
  for (const rel of ['.mcp.json', '.claude/settings.json']) {
    const f = join(ROOT, rel);
    if (!existsSync(f)) continue;
    const out = substitute(readFileSync(f, 'utf8'), { PROJECT_ROOT: ROOT_POSIX });
    writeFileSync(f, out);
    if (hasPlaceholders(out))
      throw new Error(`Unresolved placeholder in ${rel}: ${out.match(/\{\{[A-Z0-9_]+\}\}/)?.[0]}`);
  }
}

function stampMetadata() {
  for (const rel of ['CLAUDE.md', 'README.md']) {
    const f = join(ROOT, rel);
    if (!existsSync(f)) continue;
    let c = substitute(readFileSync(f, 'utf8'), { PROJECT_NAME: name, PROJECT_DESC: desc });
    // Re-ensure our KG briefing block (idempotent; survives let-them-talk's CLAUDE.md edits)
    if (rel === 'CLAUDE.md') {
      const m = c.match(/<!-- KG-BRIEFING:START -->\n([\s\S]*?)\n<!-- KG-BRIEFING:END -->/);
      const body = m ? m[1] : 'Knowledge Graph + Agent Team are pre-wired. See README.';
      c = ensureBlock(c, '<!-- KG-BRIEFING:START -->', '<!-- KG-BRIEFING:END -->', body);
    }
    writeFileSync(f, c);
  }
}

function summary() {
  console.log('\n=== Init complete ===');
  console.log(`Project: ${name}`);
  console.log('Next steps:');
  console.log('  1. Restart Claude Code so MCP servers + hooks load');
  if (opts.team) console.log('  2. node .agent-bridge/launch.js   # dashboard http://localhost:3000');
  console.log('  Re-running init-project is safe (idempotent).');
}

try {
  preflight();
  resetGit();
  npmInstalls();
  runLetThemTalk();
  mergeAndRewrite();
  stampMetadata();
  summary();
} catch (e) {
  console.error(`\nINIT FAILED: ${e.message}`);
  process.exit(1);
}
