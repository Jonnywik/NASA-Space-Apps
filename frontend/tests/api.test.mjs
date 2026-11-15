import { readFile } from 'node:fs/promises';
import assert from 'node:assert/strict';
import { test } from 'node:test';

// Load this dependency-free client as ESM without changing Next's package type.
const source = await readFile(new URL('../utils/api.js', import.meta.url), 'utf8');
const api = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

test('spot and bilingual briefing requests preserve coordinates, language and format', async () => {
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(new URL(url));
    return new Response(JSON.stringify({ dataKind: 'derived', streams: {} }), { status: 200 });
  };
  await api.getSpotCheck(120.957, 14.665);
  await api.getPlaceBriefing(120.957, 14.665, 'fil');
  assert.equal(urls[0].pathname, '/api/v1/spot-check');
  assert.equal(urls[0].searchParams.get('lon'), '120.957');
  assert.equal(urls[0].searchParams.get('lat'), '14.665');
  assert.equal(urls[1].searchParams.get('lang'), 'fil');
});

test('CSV exports retain bytes; missing validation and export data use the normal unavailable state', async () => {
  globalThis.fetch = async (url) => {
    assert.equal(new URL(url).searchParams.get('format'), 'csv');
    return new Response('field,value\nplace,Malabon\n', { status: 200 });
  };
  const blob = await api.exportPlaceBriefing(120.957, 14.665, 'en', 'csv');
  assert.equal(await blob.text(), 'field,value\nplace,Malabon\n');
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: { code: 'data_unavailable', message: 'No independent comparison' } }), { status: 404 });
  for (const load of [() => api.getValidation(), () => api.exportPlaceBriefing(120.957, 14.665, 'fil', 'html')]) {
    await assert.rejects(load, (error) => error instanceof api.ApiError && api.classifyError(error) === 'unavailable' && error.detail.message === 'No independent comparison');
  }
});

test('fixture maps never mix with backend spot facts, exports or accuracy scores', async () => {
  for (const mode of ['1', 'nisar']) {
    const previous = process.env.NEXT_PUBLIC_USE_FIXTURES;
    let fixtures;
    try {
      process.env.NEXT_PUBLIC_USE_FIXTURES = mode;
      fixtures = await import(`data:text/javascript;base64,${Buffer.from(source + `\n// fixture scope ${mode}`).toString('base64')}`);
    } finally {
      if (previous === undefined) delete process.env.NEXT_PUBLIC_USE_FIXTURES;
      else process.env.NEXT_PUBLIC_USE_FIXTURES = previous;
    }
    globalThis.fetch = async () => { throw new Error('Must not call backend'); };
    for (const load of [() => fixtures.getSpotCheck(120.957, 14.665), () => fixtures.getPlaceBriefing(120.957, 14.665, 'fil'), () => fixtures.exportPlaceBriefing(120.957, 14.665, 'en', 'csv'), () => fixtures.getValidation()]) {
      await assert.rejects(load, (error) => fixtures.classifyError(error) === 'unavailable' && error.message.includes('fixtures'));
    }
  }
});
