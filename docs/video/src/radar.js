const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
  const p = await ctx.newPage();
  await p.goto('http://localhost:3000/?mode=rhythm', { waitUntil: 'networkidle' }); await p.waitForTimeout(3000);
  await p.click('[data-testid="open-radar"]'); await p.waitForTimeout(800);
  await p.locator('[data-testid="radar-cards"]').getByText("What NISAR can and can't see", { exact: true }).click(); await p.waitForTimeout(1500);
  await p.screenshot({ path: 'shots/radar.png' }); console.log('ok');
  await b.close();
})();
