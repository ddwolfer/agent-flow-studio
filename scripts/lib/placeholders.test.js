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
