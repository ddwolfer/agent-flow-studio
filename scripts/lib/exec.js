import { spawnSync } from 'node:child_process';

export function run(cmd, args, stepLabel, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', shell: process.platform === 'win32', ...opts });
  if (r.error) throw new Error(`[${stepLabel}] failed to start: ${r.error.message}`);
  if (r.status !== 0) {
    throw new Error(`[${stepLabel}] exited with code ${r.status}. Fix the cause and re-run the init-project skill (steps are idempotent).`);
  }
}
