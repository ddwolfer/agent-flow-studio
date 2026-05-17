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

test('rejects unknown argument', () => {
  assert.throws(() => parseArgs(['--bogus']), /Unknown argument/);
});

test('trailing value-less flag throws', () => {
  assert.throws(() => parseArgs(['--name']), /Missing value/);
});

test('value-flag followed by another flag throws', () => {
  assert.throws(() => parseArgs(['--name', '--reset-git']), /Missing value/);
});

test('rejects unknown template', () => {
  assert.throws(() => parseArgs(['--template', 'bogus']), /template/);
});

test('--no-team alone sets only team:false, other defaults intact', () => {
  const o = parseArgs(['--no-team']);
  assert.equal(o.team, false);
  assert.equal(o.name, '');
  assert.equal(o.desc, '');
  assert.equal(o.providers, 'all');
  assert.equal(o.template, 'team');
  assert.equal(o.resetGit, false);
});

test('--reset-git alone sets only resetGit:true, other defaults intact', () => {
  const o = parseArgs(['--reset-git']);
  assert.equal(o.resetGit, true);
  assert.equal(o.team, true);
  assert.equal(o.name, '');
  assert.equal(o.desc, '');
  assert.equal(o.providers, 'all');
  assert.equal(o.template, 'team');
});
