# AI Team Start Template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a clone-once, share-anywhere starter template that vendors knowledgeGraph + let-them-talk and, via a project-local skill calling a deterministic Node engine, initializes a new project in place on any machine.

**Architecture:** The repo root *is* the new project after `git clone` + git reset. A conversational skill (`.claude/skills/init-project`) collects requirements and calls `scripts/initialize.js`. The engine runs npm installs, runs `npx let-them-talk init`, key-merges the KG MCP entry, rewrites `{{PROJECT_ROOT}}` placeholders to per-machine absolute paths, and substitutes project metadata. All committed configs are machine-agnostic (placeholders only) so the repo is portable. Pure Node + `node:test`, no extra deps.

**Tech Stack:** Node.js ≥18 (ESM, `node:test`, `node:fs`, `node:path`, `node:child_process`), vendored `knowledge-graph` (native `better-sqlite3`), `let-them-talk@5.5.4` as devDependency.

---

## Resolved Upstream Facts (verified against cloned repos 2026-05-18)

These replace the "assumptions to verify" in the design spec — they are now known:

- **KG layout:** repo root contains `main.js`, `hooks/`, `lib/`, `tools/`, `scripts/`, `package.json`, `README.md`. Vendor the **entire repo** into `mcp/knowledge-graph/`. Entry = `mcp/knowledge-graph/main.js`.
- **KG hook scripts (exact filenames):** `hooks/session-start.js`, `hooks/post-compact.js`, `hooks/auto-recall.js`, `hooks/search-enforcer.js`. The Stop/auto-capture hook is `type: "agent"` (no script file).
- **KG `package.json`:** `"type": "module"`, deps include native `better-sqlite3` → must `npm install` on each machine; never commit `node_modules`.
- **KG `.mcp.json` shape:** `{"mcpServers":{"knowledge-graph":{"command":"node","args":["<ABS>/mcp/knowledge-graph/main.js"]}}}`.
- **KG hooks block:** exact JSON reproduced in Task 6 Step 1, with `/path/to/hooks/` → `{{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/`.
- **let-them-talk:** version `5.5.4`, bin `let-them-talk`. `npx let-them-talk init --all --template team` is non-interactive. Writes `.mcp.json`, `.gemini/settings.json`, `.codex/config.toml`, marker block in `CLAUDE.md`/`AGENTS.md`, `.agent-bridge/launch.js`, `.gitignore`; creates `.backup` files; never clobbers existing content. It does **not** touch `.claude/settings.json`.

---

## File Structure

```
.claude/
  settings.json                  # KG hooks; {{PROJECT_ROOT}} placeholder (ours only, no merge)
  skills/init-project/SKILL.md   # conversational front-end
mcp/knowledge-graph/             # vendored upstream KG (entire repo, .git stripped)
scripts/
  initialize.js                  # engine orchestrator (CLI)
  update-vendor.js               # refresh vendored KG from upstream
  smoke-test.js                  # node:test end-to-end (offline, --no-team)
  lib/
    args.js                      # parse argv → options
    placeholders.js              # idempotent {{TOKEN}} substitution
    json-merge.js                # safe read + mcpServers key-merge + write
    markers.js                   # idempotent marker-delimited block ensure
    exec.js                      # child_process wrapper with step context
    args.test.js
    placeholders.test.js
    json-merge.test.js
    markers.test.js
.mcp.json                        # KG entry; {{PROJECT_ROOT}} placeholder
CLAUDE.md                        # template self-doc + KG-BRIEFING marker block + {{PROJECT_NAME/DESC}}
README.md
package.json                     # let-them-talk@5.5.4 devDep; scripts
.gitignore
```

Each `scripts/lib/*.js` has one responsibility and its own unit test. `initialize.js` only orchestrates — all logic lives in tested helpers.

---

### Task 1: Repo skeleton — package.json, .gitignore

**Files:**
- Create: `package.json`
- Create: `.gitignore`

- [ ] **Step 1: Create `package.json`**

```json
{
  "name": "ai-team-start-template",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "description": "Clone-once starter template wiring knowledgeGraph + let-them-talk for a new AI project",
  "scripts": {
    "init": "node scripts/initialize.js",
    "update-vendor": "node scripts/update-vendor.js",
    "test": "node --test scripts/lib/",
    "smoke": "node --test scripts/smoke-test.js"
  },
  "devDependencies": {
    "let-them-talk": "5.5.4"
  }
}
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
node_modules/
mcp/knowledge-graph/node_modules/
mcp/knowledge-graph/*.db
mcp/knowledge-graph/*.sqlite*
.agent-bridge/
.agent-bridge-markdown/
*.backup
.git.bak-*
.DS_Store
```

- [ ] **Step 3: Commit**

```bash
git add package.json .gitignore
git commit -m "chore: repo skeleton (package.json, gitignore)"
```

---

### Task 2: Vendor knowledgeGraph + update-vendor.js

**Files:**
- Create: `scripts/update-vendor.js`
- Create: `mcp/knowledge-graph/**` (generated by running the script)

- [ ] **Step 1: Write `scripts/update-vendor.js`**

```javascript
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
```

- [ ] **Step 2: Run it to vendor KG**

Run: `node scripts/update-vendor.js`
Expected: prints "Vendored knowledgeGraph → .../mcp/knowledge-graph"

- [ ] **Step 3: Verify vendored layout**

Run: `node -e "const f=require('fs');for(const p of ['mcp/knowledge-graph/main.js','mcp/knowledge-graph/hooks/session-start.js','mcp/knowledge-graph/hooks/post-compact.js','mcp/knowledge-graph/hooks/auto-recall.js','mcp/knowledge-graph/hooks/search-enforcer.js','mcp/knowledge-graph/package.json'])if(!f.existsSync(p)){console.error('MISSING '+p);process.exit(1)}console.log('layout OK')"`
Expected: `layout OK`

- [ ] **Step 4: Confirm `.git` was stripped**

Run: `node -e "process.exit(require('fs').existsSync('mcp/knowledge-graph/.git')?1:0)" && echo "no nested git OK"`
Expected: `no nested git OK`

- [ ] **Step 5: Commit**

```bash
git add scripts/update-vendor.js mcp/knowledge-graph
git commit -m "feat: vendor knowledgeGraph + update-vendor script"
```

---

### Task 3: lib/args.js — CLI option parsing

**Files:**
- Create: `scripts/lib/args.js`
- Test: `scripts/lib/args.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseArgs } from './args.js';

test('defaults: team on, all providers, no git reset', () => {
  const o = parseArgs([]);
  assert.equal(o.team, true);
  assert.equal(o.providers, 'all');
  assert.equal(o.template, 'team');
  assert.equal(o.resetGit, false);
});

test('flags override defaults', () => {
  const o = parseArgs(['--name', 'Foo', '--desc', 'a bot', '--no-team', '--providers', 'claude', '--template', 'pair', '--reset-git']);
  assert.equal(o.name, 'Foo');
  assert.equal(o.desc, 'a bot');
  assert.equal(o.team, false);
  assert.equal(o.providers, 'claude');
  assert.equal(o.template, 'pair');
  assert.equal(o.resetGit, true);
});

test('rejects unknown provider', () => {
  assert.throws(() => parseArgs(['--providers', 'bogus']), /providers/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/lib/args.test.js`
Expected: FAIL — cannot find module `./args.js`

- [ ] **Step 3: Write `scripts/lib/args.js`**

```javascript
const PROVIDERS = new Set(['all', 'claude', 'gemini', 'codex']);
const TEMPLATES = new Set(['pair', 'team', 'review', 'debate', 'managed']);

export function parseArgs(argv) {
  const o = { name: '', desc: '', team: true, providers: 'all', template: 'team', resetGit: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--name') o.name = argv[++i] ?? '';
    else if (a === '--desc') o.desc = argv[++i] ?? '';
    else if (a === '--no-team') o.team = false;
    else if (a === '--providers') o.providers = argv[++i] ?? '';
    else if (a === '--template') o.template = argv[++i] ?? '';
    else if (a === '--reset-git') o.resetGit = true;
    else throw new Error(`Unknown argument: ${a}`);
  }
  if (!PROVIDERS.has(o.providers)) throw new Error(`Invalid --providers: ${o.providers}`);
  if (!TEMPLATES.has(o.template)) throw new Error(`Invalid --template: ${o.template}`);
  return o;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/lib/args.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/args.js scripts/lib/args.test.js
git commit -m "feat: lib/args option parsing"
```

---

### Task 4: lib/placeholders.js — idempotent token substitution

**Files:**
- Create: `scripts/lib/placeholders.js`
- Test: `scripts/lib/placeholders.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { substitute, hasPlaceholders } from './placeholders.js';

test('replaces all occurrences of each token', () => {
  const out = substitute('{{A}}/x/{{A}}/{{B}}', { A: 'p', B: 'q' });
  assert.equal(out, 'p/x/p/q');
});

test('idempotent: re-running on substituted text is a no-op', () => {
  const once = substitute('{{NAME}}', { NAME: 'demo' });
  const twice = substitute(once, { NAME: 'demo' });
  assert.equal(twice, 'demo');
});

test('hasPlaceholders detects leftover {{TOKENS}}', () => {
  assert.equal(hasPlaceholders('a {{X}} b'), true);
  assert.equal(hasPlaceholders('a b'), false);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/lib/placeholders.test.js`
Expected: FAIL — cannot find module

- [ ] **Step 3: Write `scripts/lib/placeholders.js`**

```javascript
export function substitute(text, map) {
  let out = text;
  for (const [key, val] of Object.entries(map)) {
    out = out.split(`{{${key}}}`).join(String(val));
  }
  return out;
}

export function hasPlaceholders(text) {
  return /\{\{[A-Z0-9_]+\}\}/.test(text);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/lib/placeholders.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/placeholders.js scripts/lib/placeholders.test.js
git commit -m "feat: lib/placeholders idempotent substitution"
```

---

### Task 5: lib/json-merge.js — safe read + mcpServers key-merge

**Files:**
- Create: `scripts/lib/json-merge.js`
- Test: `scripts/lib/json-merge.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/lib/json-merge.test.js`
Expected: FAIL — cannot find module

- [ ] **Step 3: Write `scripts/lib/json-merge.js`**

```javascript
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/lib/json-merge.test.js`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/json-merge.js scripts/lib/json-merge.test.js
git commit -m "feat: lib/json-merge safe mcpServers key-merge"
```

---

### Task 6: lib/markers.js — idempotent marker-delimited block

**Files:**
- Create: `scripts/lib/markers.js`
- Test: `scripts/lib/markers.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { ensureBlock } from './markers.js';

const S = '<!-- KG-BRIEFING:START -->';
const E = '<!-- KG-BRIEFING:END -->';

test('appends block when absent', () => {
  const out = ensureBlock('existing\n', S, E, 'BODY');
  assert.ok(out.includes(S) && out.includes('BODY') && out.includes(E));
  assert.ok(out.startsWith('existing'));
});

test('idempotent: second ensure with same body is unchanged', () => {
  const a = ensureBlock('doc\n', S, E, 'BODY');
  const b = ensureBlock(a, S, E, 'BODY');
  assert.equal(a, b);
});

test('replaces stale block body in place, no duplicate markers', () => {
  const a = ensureBlock('doc\n', S, E, 'OLD');
  const b = ensureBlock(a, S, E, 'NEW');
  assert.ok(b.includes('NEW') && !b.includes('OLD'));
  assert.equal(b.split(S).length - 1, 1);
  assert.equal(b.split(E).length - 1, 1);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/lib/markers.test.js`
Expected: FAIL — cannot find module

- [ ] **Step 3: Write `scripts/lib/markers.js`**

```javascript
export function ensureBlock(content, startMarker, endMarker, body) {
  const block = `${startMarker}\n${body}\n${endMarker}`;
  const s = content.indexOf(startMarker);
  const e = content.indexOf(endMarker);
  if (s !== -1 && e !== -1 && e > s) {
    return content.slice(0, s) + block + content.slice(e + endMarker.length);
  }
  const sep = content.endsWith('\n') ? '\n' : '\n\n';
  return content + sep + block + '\n';
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/lib/markers.test.js`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/markers.js scripts/lib/markers.test.js
git commit -m "feat: lib/markers idempotent marker block"
```

---

### Task 7: lib/exec.js — child_process wrapper with step context

**Files:**
- Create: `scripts/lib/exec.js`
- Test: `scripts/lib/exec.test.js`

- [ ] **Step 1: Write the failing test**

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { run } from './exec.js';

test('run returns on success', () => {
  assert.doesNotThrow(() => run('node', ['-e', 'process.exit(0)'], 'noop step'));
});

test('run throws with step context on failure', () => {
  assert.throws(() => run('node', ['-e', 'process.exit(3)'], 'failing step'),
    /failing step/);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test scripts/lib/exec.test.js`
Expected: FAIL — cannot find module

- [ ] **Step 3: Write `scripts/lib/exec.js`**

```javascript
import { spawnSync } from 'node:child_process';

export function run(cmd, args, stepLabel, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: process.platform === 'win32', ...opts });
  if (r.error) throw new Error(`[${stepLabel}] failed to start: ${r.error.message}`);
  if (r.status !== 0) {
    throw new Error(`[${stepLabel}] exited with code ${r.status}. Fix the cause and re-run the init-project skill (steps are idempotent).`);
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test scripts/lib/exec.test.js`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/lib/exec.js scripts/lib/exec.test.js
git commit -m "feat: lib/exec child process wrapper"
```

---

### Task 8: Committed config templates (.mcp.json, .claude/settings.json, CLAUDE.md, README.md)

**Files:**
- Create: `.mcp.json`
- Create: `.claude/settings.json`
- Create: `CLAUDE.md`
- Create: `README.md`

- [ ] **Step 1: Create `.mcp.json` (placeholder path, machine-agnostic)**

```json
{
  "mcpServers": {
    "knowledge-graph": {
      "command": "node",
      "args": ["{{PROJECT_ROOT}}/mcp/knowledge-graph/main.js"]
    }
  }
}
```

- [ ] **Step 2: Create `.claude/settings.json` (exact upstream hooks block, paths placeholdered)**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup",
        "hooks": [{ "type": "command", "command": "node {{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/session-start.js", "timeout": 10 }]
      },
      {
        "matcher": "compact",
        "hooks": [{ "type": "command", "command": "node {{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/post-compact.js", "timeout": 10 }]
      }
    ],
    "UserPromptSubmit": [{
      "hooks": [{ "type": "command", "command": "node {{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/auto-recall.js", "timeout": 10 }]
    }],
    "Stop": [{
      "hooks": [{ "type": "agent", "model": "claude-opus-4-6", "prompt": "See auto-capture prompt in settings.json", "timeout": 60 }]
    }],
    "PreToolUse": [{
      "hooks": [{ "type": "command", "command": "node {{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/search-enforcer.js", "timeout": 5 }]
    }]
  }
}
```

Note: this is upstream's documented block verbatim except `/path/to/hooks/` → `{{PROJECT_ROOT}}/mcp/knowledge-graph/hooks/`. The Stop hook's `prompt` is upstream's own placeholder text; leave as-is (out of scope to author the auto-capture prompt — see spec §8).

- [ ] **Step 3: Create `CLAUDE.md` with the KG-BRIEFING marker block and metadata placeholders**

```markdown
# {{PROJECT_NAME}}

{{PROJECT_DESC}}

This project was started from the AI Team Start Template.

## Starting a new project from this template

`git clone` this template into a new folder, delete `.git`, then in that folder
open Claude Code and run the `init-project` skill (or:
`node scripts/initialize.js --name "<name>" --desc "<desc>"`).
Re-running is safe — every step is idempotent.

<!-- KG-BRIEFING:START -->
## Tooling: Knowledge Graph + Agent Team

**Knowledge Graph** (`mcp/knowledge-graph`, MCP server `knowledge-graph`): a local
long-term memory. Before acting on domain knowledge, search it
(`search_memory`); record durable lessons (`store_knowledge`,
`record_experience`). Lifecycle hooks in `.claude/settings.json` auto-recall on
prompt, auto-capture on stop, and self-maintain on session start.

**Agent Team** (`let-them-talk`, MCP server `agent-bridge`): multi-agent
collaboration across Claude/Codex/Gemini. Agents `register()`,
`get_briefing()`, then loop with `listen_group()` / `get_work()` /
`verify_and_advance()`. Launch the dashboard with
`node .agent-bridge/launch.js` (http://localhost:3000).

**Workflow:** consult Knowledge Graph for what's known → coordinate execution
through the Agent Team → record what was learned back into Knowledge Graph.
<!-- KG-BRIEFING:END -->
```

- [ ] **Step 4: Create `README.md`**

```markdown
# {{PROJECT_NAME}}

{{PROJECT_DESC}}

Bootstrapped from [AI Team Start Template]. Knowledge Graph (local memory) and
let-them-talk (multi-agent team) are pre-wired.

## Init
- In Claude Code: run the `init-project` skill.
- Or: `node scripts/initialize.js --name "<name>" --desc "<desc>" [--no-team] [--reset-git]`

## Dashboard
`node .agent-bridge/launch.js` → http://localhost:3000
```

- [ ] **Step 5: Verify all committed configs are machine-agnostic (no absolute paths)**

Run: `node -e "const f=require('fs');const t=f.readFileSync('.mcp.json','utf8')+f.readFileSync('.claude/settings.json','utf8');if(/([A-Za-z]:\\\\|\/Users\/|\/home\/)/.test(t)){console.error('ABS PATH LEAK');process.exit(1)}console.log('machine-agnostic OK')"`
Expected: `machine-agnostic OK`

- [ ] **Step 6: Commit**

```bash
git add .mcp.json .claude/settings.json CLAUDE.md README.md
git commit -m "feat: committed machine-agnostic config templates"
```

---

### Task 9: scripts/initialize.js — engine orchestrator

**Files:**
- Create: `scripts/initialize.js`

- [ ] **Step 1: Write `scripts/initialize.js`**

```javascript
#!/usr/bin/env node
// Deterministic in-place initializer. Orchestration only; logic lives in lib/.
import { existsSync, renameSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { parseArgs } from './lib/args.js';
import { substitute, hasPlaceholders } from './lib/placeholders.js';
import { ensureMcpServer } from './lib/json-merge.js';
import { ensureBlock } from './lib/markers.js';
import { run } from './lib/exec.js';

const ROOT = process.cwd();
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
    renameSync(dotgit, bak);
    console.log(`Moved .git → ${bak}`);
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
    args: [`${ROOT}/mcp/knowledge-graph/main.js`]
  });
  // Rewrite {{PROJECT_ROOT}} placeholders → this machine's absolute root
  for (const rel of ['.mcp.json', '.claude/settings.json']) {
    const f = join(ROOT, rel);
    if (!existsSync(f)) continue;
    const out = substitute(readFileSync(f, 'utf8'), { PROJECT_ROOT: ROOT });
    writeFileSync(f, out);
    if (hasPlaceholders(out) && /PROJECT_ROOT/.test(out))
      throw new Error(`PROJECT_ROOT placeholder still present in ${rel}`);
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
```

- [ ] **Step 2: Verify it parses and rejects bad Node gracefully (dry structural check)**

Run: `node --check scripts/initialize.js && echo "syntax OK"`
Expected: `syntax OK`

- [ ] **Step 3: Commit**

```bash
git add scripts/initialize.js
git commit -m "feat: initialize.js engine orchestrator"
```

---

### Task 10: scripts/smoke-test.js — offline end-to-end + idempotency

**Files:**
- Create: `scripts/smoke-test.js`

- [ ] **Step 1: Write `scripts/smoke-test.js`**

```javascript
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
    { cwd: work, encoding: 'utf8', shell: process.platform === 'win32' });
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
```

- [ ] **Step 2: Run the smoke test**

Run: `node --test scripts/smoke-test.js`
Expected: PASS (6 tests). (Runs `npm install` in the temp copy — needs network the first time; native `better-sqlite3` builds via prebuilt binary.)

- [ ] **Step 3: Run the full unit suite**

Run: `npm test`
Expected: all `scripts/lib/*.test.js` PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/smoke-test.js
git commit -m "test: offline end-to-end smoke test + idempotency"
```

---

### Task 11: init-project skill

**Files:**
- Create: `.claude/skills/init-project/SKILL.md`

- [ ] **Step 1: Write `.claude/skills/init-project/SKILL.md`**

```markdown
---
name: init-project
description: Use when starting a new project from this template — collects project name/description and team preferences, then runs the deterministic initializer to wire Knowledge Graph + the agent team in place.
---

# init-project

You are initializing THIS cloned template directory in place as a new project.

## Collect (ask only what's not already given, one question at a time)

1. Project name — default: current folder name.
2. Project description — one sentence.
3. Agent team? — default yes. If yes, template: `pair` / `team` (default) /
   `review` / `debate` / `managed`; providers: `all` (default) / `claude` /
   `gemini` / `codex`.
4. Reset git? — if the user cloned this template and wants fresh history,
   yes (moves `.git` to a timestamped backup, then `git init`).

## Run the engine (do NOT re-implement its steps)

Build one command and run it via Bash:

\`\`\`
node scripts/initialize.js --name "<name>" --desc "<desc>" \
  [--no-team] [--providers <p>] [--template <t>] [--reset-git]
\`\`\`

- Omit `--no-team` when a team is wanted; include it when not.
- Pass `--providers` / `--template` only when a team is wanted.

## After it runs

- Relay the engine's "Next steps" output to the user.
- If it exits non-zero: report the failing step verbatim. The fix is always
  "resolve the cause, then re-run this skill" — every step is idempotent.
- Do not hand-edit `.mcp.json`, `.claude/settings.json`, or `CLAUDE.md`; the
  engine owns them. Re-run the skill instead.
```

- [ ] **Step 2: Verify skill frontmatter is well-formed**

Run: `node -e "const t=require('fs').readFileSync('.claude/skills/init-project/SKILL.md','utf8');if(!/^---\r?\nname: init-project/.test(t)){console.error('bad frontmatter');process.exit(1)}console.log('skill OK')"`
Expected: `skill OK`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/init-project/SKILL.md
git commit -m "feat: init-project skill (conversational front-end)"
```

---

### Task 12: Manual acceptance + finalize

**Files:**
- Modify: `README.md` (add template-maintainer section if needed — only if missing)

- [ ] **Step 1: Full manual run with the team (network + Claude/Codex/Gemini CLI present)**

```bash
# In a throwaway copy of the repo:
node scripts/initialize.js --name "AcceptProj" --desc "manual acceptance" --providers all --template team
```
Expected: exits 0; `.agent-bridge/launch.js` exists; `.mcp.json` contains BOTH `knowledge-graph` and `agent-bridge`; `CLAUDE.md` contains both the let-them-talk marker block AND `KG-BRIEFING`.

- [ ] **Step 2: Launch dashboard sanity check**

Run: `node .agent-bridge/launch.js status`
Expected: prints a status snapshot without error.

- [ ] **Step 3: Open Claude Code in the initialized dir, confirm MCP servers load**

Manual: start Claude Code in the directory; confirm `knowledge-graph` and `agent-bridge` MCP servers connect and KG hooks fire on session start.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: finalize AI team start template"
```

- [ ] **Step 5: Mac acceptance (user-driven)**

User clones the repo on a Mac, runs the `init-project` skill, and reports any failures. Treat failures as feedback to fix `initialize.js` / templates — the smoke test (Task 10) should be extended to cover any regression found.

---

## Self-Review

**Spec coverage:** §2 layout → Tasks 1,2,8,11; §2 vendor → Task 2; §2 in-place init → Task 9; §4.1 skill collection → Task 11; §4.2 engine steps 1–9 → Task 9 (`preflight`/`resetGit`/`npmInstalls`/`runLetThemTalk`/`mergeAndRewrite`/`stampMetadata`/`summary`); §4.3 idempotency → Tasks 5,6,9 + smoke Task 10; §5 error handling → Task 7 + `initialize.js` try/catch + `readJsonSafe`; §6 testing → Tasks 3–7,10; §6 Mac acceptance → Task 12 Step 5; §7 (now resolved) → "Resolved Upstream Facts"; §8 YAGNI → no global-skill/degit tasks; auto-capture prompt left as upstream's. All covered.

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to Task N" — every code/test step has complete code and exact commands. The Stop hook `prompt` string is upstream's own verbatim text, explicitly scoped out (spec §8), not a plan placeholder.

**Type consistency:** `parseArgs`→`{name,desc,team,providers,template,resetGit}` consistent across Tasks 3, 9, 11. `ensureMcpServer(file,name,serverDef)`, `ensureBlock(content,start,end,body)`, `substitute(text,map)`, `hasPlaceholders(text)`, `run(cmd,args,label,opts?)` — signatures defined in Tasks 3–7 and used identically in Task 9. `{{PROJECT_ROOT}}` / `{{PROJECT_NAME}}` / `{{PROJECT_DESC}}` consistent across Tasks 8, 9, 10.
