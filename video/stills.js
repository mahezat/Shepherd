// node stills.js: renders every still frame of the video to frames/<id>.png (deterministic, no screen recording)
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('http://localhost:8766/frames.html');
  await p.evaluate(() => document.fonts.ready);
  const ids = ['i1','i2','split','i4','i5','a1','a2','a3','a4','a5','a6','a7','a8','end'];
  for (const id of ids) {
    await p.evaluate(i => window.render(i), id);
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(150);
    await p.screenshot({ path: `frames/${id}.png`, omitBackground: id === 'split' });
    if (id === 'a3') { const r = await p.evaluate(() => { const b = document.querySelector('.hole').getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); });
      require('fs').writeFileSync('frames/hole.json', JSON.stringify(r)); }
  }
  await b.close(); console.log('stills done');
})();
