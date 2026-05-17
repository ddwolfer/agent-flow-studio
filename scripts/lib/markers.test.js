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
