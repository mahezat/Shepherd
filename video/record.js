// node record.js <page.html> <out.mp4>: records a timeline page at 1920x1080 and trims to the timeline start.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs'), path = require('path');
(async () => {
  const [page_, out] = process.argv.slice(2);
  const dir = fs.mkdtempSync('/tmp/rec-');
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell', args: ['--autoplay-policy=no-user-gesture-required'] });
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir, size: { width: 1920, height: 1080 } } });
  const wall0 = Date.now();
  const p = await ctx.newPage();
  await p.goto('http://localhost:8766/' + page_);
  await p.waitForFunction(() => window.__done === true, null, { timeout: 180000, polling: 250 });
  const start = await p.evaluate(() => window.__t0wall);
  await p.waitForTimeout(300);
  await ctx.close(); await b.close();
  const webm = fs.readdirSync(dir).filter(f => f.endsWith('.webm')).map(f => path.join(dir, f))[0];
  const offset = Math.max(0, (start - wall0) / 1000);
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', String(offset), '-i', webm, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', '-crf', '20', out]);
  console.log('wrote', out, 'trimmed', offset.toFixed(2), 's');
})();
