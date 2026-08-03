import assert from 'node:assert';
import { askAI } from './ai.js';

globalThis.fetch = async (url, opts) => ({
  ok: true, status: 200,
  json: async () => ({ answer: 'ETF是一种基金', cached: false }),
});
const r = await askAI('什么是ETF', 'faketoken');
assert.equal(r.answer, 'ETF是一种基金');
assert.equal(r.cached, false);

// HTTP 错误应抛带 code 的 Error
globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ error: 'unauthorized' }) });
let threw = false;
try { await askAI('x', 't'); } catch (e) { threw = true; assert.equal(e.code, 'HTTP_401'); }
assert.ok(threw, 'should throw on 401');

console.log('ai.test.mjs OK');
