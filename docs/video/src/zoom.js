const { chromium } = require('playwright');
const B = 'http://localhost:3000/';
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1.2 });
  const p = await ctx.newPage();
  const zoomShot = async (url, name, x, y, steps) => {
    await p.goto(B + url, { waitUntil: 'networkidle' }); await p.waitForTimeout(3000);
    await p.mouse.move(x, y);
    for (let i = 0; i < steps; i++) { await p.mouse.wheel(0, -120); await p.waitForTimeout(900); }
    await p.waitForTimeout(1500);
    await p.mouse.move(330, 230); await p.mouse.down(); await p.mouse.move(500, 340, { steps: 12 }); await p.mouse.move(600, 420, { steps: 12 }); await p.mouse.up();
    await p.mouse.move(1150, 450); // cursor off the map (over the side panel)
    await p.waitForTimeout(4500);
    await p.screenshot({ path: `shots/${name}.png` }); console.log('ok', name);
  };
  // NW fishponds / Bulacan coast ~ (120.89, 14.80): about x=430, y=270 in the 1600x900 viewport
  await zoomShot('?mode=rhythm', 'z_rhythm', 395, 256, 3);
  for (const d of ['20260705', '20260810', '20260903', '20261102']) await zoomShot(`?mode=season&pass=${d}`, `z_pass_${d}`, 395, 256, 3);
  await b.close();
})();
