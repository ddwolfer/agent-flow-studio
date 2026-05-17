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
