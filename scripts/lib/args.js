const PROVIDERS = new Set(['all', 'claude', 'gemini', 'codex']);
const TEMPLATES = new Set(['pair', 'team', 'review', 'debate', 'managed']);

function takeValue(argv, i, flag) {
  const v = argv[i];
  if (v === undefined || v.startsWith('--')) throw new Error(`Missing value for ${flag}`);
  return v;
}

export function parseArgs(argv) {
  const o = { name: '', desc: '', team: true, providers: 'all', template: 'team', resetGit: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--name') o.name = takeValue(argv, ++i, '--name');
    else if (a === '--desc') o.desc = takeValue(argv, ++i, '--desc');
    else if (a === '--no-team') o.team = false;
    else if (a === '--providers') o.providers = takeValue(argv, ++i, '--providers');
    else if (a === '--template') o.template = takeValue(argv, ++i, '--template');
    else if (a === '--reset-git') o.resetGit = true;
    else throw new Error(`Unknown argument: ${a}`);
  }
  if (!PROVIDERS.has(o.providers)) {
    throw new Error(`Invalid --providers: ${o.providers} (expected: ${[...PROVIDERS].join(', ')})`);
  }
  if (!TEMPLATES.has(o.template)) {
    throw new Error(`Invalid --template: ${o.template} (expected: ${[...TEMPLATES].join(', ')})`);
  }
  return o;
}
