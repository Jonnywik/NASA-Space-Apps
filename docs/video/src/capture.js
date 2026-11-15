const { chromium } = require('playwright');
const B = 'http://localhost:3000/';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
  const p = await ctx.newPage();
  const shot = async (url, name, after) => {
    await p.goto(B + url, { waitUntil: 'networkidle' });
    await p.waitForTimeout(3500);
    if (after) { await after(); await p.waitForTimeout(2500); }
    await p.screenshot({ path: `shots/${name}.png` });
    console.log('ok', name);
  };
  await shot('?mode=rhythm', 'rhythm');
  for (const d of ['20260705', '20260810', '20260903', '20261102']) await shot(`?mode=season&pass=${d}`, `pass_${d}`);
  await shot('?mode=rhythm&lon=120.957&lat=14.665', 'spot');
  await shot('?mode=rhythm', 'validation', async () => {
    const el = await p.$('[data-testid="cross-track-block"]'); if (el) await el.scrollIntoViewIfNeeded();
  });
  await shot('?mode=rhythm', 'radar', async () => { await p.click('[data-testid="open-radar"]'); });
  await shot('?mode=rhythm&lang=fil', 'fil');
  await b.close();
})();
