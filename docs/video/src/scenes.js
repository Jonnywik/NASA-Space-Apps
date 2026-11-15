const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const shot = (n) => 'data:image/png;base64,' + fs.readFileSync(path.resolve('shots', n + '.png')).toString('base64');
const WM = '<div class="wm">SI-generated video (made with AI tools) · screenshots of the real app · real NASA data</div>';
const css = `
*{box-sizing:border-box;margin:0;padding:0}
body{width:1920px;height:1080px;overflow:hidden;font-family:Inter,'DejaVu Sans',sans-serif;background:#16231B}
.bg{position:absolute;inset:0;background-size:cover;background-repeat:no-repeat}
.cap{position:absolute;left:60px;right:60px;bottom:48px;background:rgba(18,59,37,.93);color:#fff;border-radius:22px;padding:26px 38px;font-size:44px;line-height:1.25;font-weight:600;box-shadow:0 10px 40px rgba(0,0,0,.35)}
.cap.top{bottom:auto;top:78px}
.cap small{display:block;font-size:28px;font-weight:500;color:#CDE5D6;margin-top:8px}
.wm{position:absolute;top:18px;left:50%;transform:translateX(-50%);background:rgba(22,35,27,.78);color:#fff;font-size:20px;font-weight:600;padding:7px 16px;border-radius:999px;letter-spacing:.2px}
.card{position:absolute;inset:0;background:linear-gradient(135deg,#1E5B3A 0%,#123B25 60%,#0B2A1A 100%);color:#fff;display:flex;flex-direction:column;justify-content:center;padding:0 140px}
.k{font-size:30px;letter-spacing:6px;color:#9FD3B5;font-weight:700}
h1{font-size:150px;letter-spacing:14px;font-weight:800;margin:10px 0 6px}
h2{font-size:58px;font-weight:600;line-height:1.2;max-width:1500px}
.meta{margin-top:40px;font-size:32px;color:#CDE5D6}
ul{list-style:none;margin-top:34px}
li{font-size:46px;line-height:1.35;margin:14px 0;font-weight:600}
li b{color:#F2C14E}
.url{margin-top:46px;font-size:40px;font-weight:700;color:#fff;background:rgba(255,255,255,.12);display:inline-block;padding:14px 26px;border-radius:14px}
`;
const zoomBg = (img, scale = 1, ox = '50%', oy = '50%') =>
  `<div class="bg" style="background-image:url('${shot(img)}');transform:scale(${scale});transform-origin:${ox} ${oy}"></div>`;
const scenes = {
  s01_title: `<div class="card"><div class="k">NASA SPACE APPS CHALLENGE 2026 · DANCING WITH THE SARs</div><h1>TANAW</h1><h2>What NASA-ISRO's NISAR radar sees of our floods in CAMANAVA, Metro Manila</h2><div class="meta">Project Gravensoft · Metro Manila, Philippines</div></div>${WM}`,
  s02_question: `${zoomBg('rhythm')}<div class="cap">Every rainy season, CAMANAVA floods. Can NISAR see it through clouds and rain?<small>Tanaw: an interactive map of every real NISAR pass, 2026 wet season</small></div>${WM}`,
  s03_p1: `${zoomBg('z_pass_20260705')}<div class="cap">Pass by pass: open water outside the usual water<small>5 Jul 2026 · NISAR L-band radar, 05:30 Manila</small></div>${WM}`,
  s03_p2: `${zoomBg('z_pass_20260810')}<div class="cap">Pass by pass: open water outside the usual water<small>10 Aug 2026 · after 97 mm of rain in 48 h (NASA GPM IMERG)</small></div>${WM}`,
  s03_p3: `${zoomBg('z_pass_20260903')}<div class="cap">Pass by pass: open water outside the usual water<small>3 Sep 2026 · 21 passes from two NISAR orbits</small></div>${WM}`,
  s03_p4: `${zoomBg('z_pass_20261102')}<div class="cap">Pass by pass: open water outside the usual water<small>2 Nov 2026 · end of the wet season</small></div>${WM}`,
  s04_sees: `${zoomBg('z_rhythm')}<div class="cap">It sees: recurring open water at the city's edge<small>Fishponds, paddies and the Bulacan coast · about 0.4 km² on half or more of the passes</small></div>${WM}`,
  s05_valid: `${zoomBg('validation', 1.35, '100%', '561px')}<div class="cap">Two NISAR orbits find the same water (99% within 30 m)<small>Sentinel-1 OPERA agrees 97% of the time when NISAR says water</small></div>${WM}`,
  s06_cant: `${zoomBg('radar')}<div class="cap">It can't see flooded streets: water between buildings looks bright, not dark<small>We show this limit openly, with every source and caveat in the app</small></div>${WM}`,
  s07_spot: `${zoomBg('spot', 1.25, '0%', '100%')}<div class="cap top">Search your barangay: pass history, rain, exposure, briefing<small>In English and Filipino</small></div>${WM}`,
  s08_end: `<div class="card"><div class="k">TANAW · WHAT WE FOUND</div><ul><li>✓ NISAR <b>sees</b> recurring open water at the city's edge</li><li>✓ <b>Confirmed</b> by a second NISAR orbit and by Sentinel-1</li><li>⚠ It <b>cannot yet see</b> flooded city streets</li></ul><div class="url">github.com/Jonnywik/tanaw-nasa-space-apps-2026</div></div>${WM}`,
};
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  fs.mkdirSync('scenes', { recursive: true });
  for (const [name, body] of Object.entries(scenes)) {
    await p.setContent(`<html><head><style>${css}</style></head><body>${body}</body></html>`, { waitUntil: 'load' });
    await p.waitForTimeout(300);
    await p.screenshot({ path: `scenes/${name}.png` });
    console.log('scene', name);
  }
  await b.close();
})();
