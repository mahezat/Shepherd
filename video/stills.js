// node stills.js: renders backgrounds (2400x1080) and transparent foregrounds (1920x1080) to frames/
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell' });
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  await p.goto('http://localhost:8766/frames.html');
  await p.evaluate(() => document.fonts.ready);
  for (const id of ['bg-hay', 'bg-hay-chickens', 'bg-fence', 'bg-cow']) {
    await p.setViewportSize({ width: 2400, height: 1080 });
    await p.evaluate(i => window.render(i), id); await p.waitForTimeout(100);
    await p.screenshot({ path: `frames/${id}.png` });
  }
  await p.setViewportSize({ width: 1920, height: 1080 });
  const ids = ['i1','i3','iw','split','split_hot','fightzoom','phone','ask','ask_ans','i4','i5','i6','a1','a2','a3','a4','a5','a6','a7','a8','end'];
  for (const id of ids) {
    await p.evaluate(i => window.render(i), id);
    await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(120);
    await p.screenshot({ path: `frames/${id}.png`, omitBackground: true });
    if (id === 'i5') { const r = await p.evaluate(() => { const b = document.querySelector('.hole3').getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); });
      fs.writeFileSync('frames/hole_gallery.json', JSON.stringify(r)); }
    if (id === 'ask_ans') { const r = await p.evaluate(() => { const b = document.querySelector('.hole2').getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); });
      fs.writeFileSync('frames/hole_ask.json', JSON.stringify(r)); }
    if (id === 'a3') { const r = await p.evaluate(() => { const b = document.querySelector('.hole').getBoundingClientRect(); return [b.x, b.y, b.width, b.height].map(Math.round); });
      fs.writeFileSync('frames/hole.json', JSON.stringify(r)); }
  }
  await b.close(); console.log('stills done');
})();
