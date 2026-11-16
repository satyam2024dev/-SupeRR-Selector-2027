import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '../dist');
const outDir = path.resolve(__dirname, '../screenshots');

// Import playwright from frontend
const playwrightPath = path.resolve(__dirname, '../../frontend/node_modules/playwright-core/index.mjs');
const { chromium } = await import(pathToFileURL(playwrightPath).href);

const edgePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

// Simple static server for dist
const mimeTypes = {
  '.html': 'text/html',
  '.js': 'text/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.pdf': 'application/pdf',
  '.csv': 'text/csv',
};

const server = http.createServer((req, res) => {
  let reqPath = req.url.split('?')[0];
  if (reqPath === '/' || reqPath === '') reqPath = '/index.html';
  const filePath = path.join(distDir, reqPath);

  if (fs.existsSync(filePath) && fs.statSync(filePath).isFile()) {
    const ext = path.extname(filePath).toLowerCase();
    const contentType = mimeTypes[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': contentType });
    fs.createReadStream(filePath).pipe(res);
  } else {
    // SPA fallback
    const indexPath = path.join(distDir, 'index.html');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    fs.createReadStream(indexPath).pipe(res);
  }
});

const PORT = 5188;
await new Promise(resolve => server.listen(PORT, '127.0.0.1', resolve));
console.log(`Static server running on http://127.0.0.1:${PORT}`);

try {
  const browser = await chromium.launch({
    executablePath: edgePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const viewports = [
    { name: '1440', width: 1440, height: 900 },
    { name: '390', width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    console.log(`\nTesting viewport ${vp.name}px (${vp.width}x${vp.height})...`);
    const page = await browser.newPage({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
      isMobile: vp.width < 600,
    });

    await page.goto(`http://127.0.0.1:${PORT}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(500);

    // Check horizontal scroll
    const overflowCheck = await page.evaluate(() => {
      return {
        innerWidth: window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        hasOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      };
    });

    console.log(`Overflow check at ${vp.width}px: scrollWidth=${overflowCheck.scrollWidth}, innerWidth=${overflowCheck.innerWidth} (Overflow: ${overflowCheck.hasOverflow ? 'FAIL' : 'PASS'})`);

    // 1. Hero Screenshot
    const heroEl = await page.locator('#hero');
    await heroEl.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(outDir, `hero-${vp.name}.png`),
      clip: await heroEl.boundingBox(),
    });
    console.log(`Captured hero-${vp.name}.png`);

    // 2. Simulator Screenshot
    const simEl = await page.locator('#pressure');
    await simEl.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(outDir, `simulator-${vp.name}.png`),
      clip: await simEl.boundingBox(),
    });
    console.log(`Captured simulator-${vp.name}.png`);

    // 3. Rankings Screenshot
    const rankEl = await page.locator('#rankings');
    await rankEl.scrollIntoViewIfNeeded();
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(outDir, `rankings-${vp.name}.png`),
      clip: await rankEl.boundingBox(),
    });
    console.log(`Captured rankings-${vp.name}.png`);

    // 4. Drawer Screenshot
    // Click on player row (first player)
    const firstRow = page.locator('#rankings .cursor-pointer').first();
    await firstRow.click();
    await page.waitForTimeout(400); // Wait for drawer spring animation
    await page.screenshot({
      path: path.join(outDir, `drawer-${vp.name}.png`),
      fullPage: false,
    });
    console.log(`Captured drawer-${vp.name}.png`);

    // Close drawer
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);

    await page.close();
  }

  await browser.close();
  console.log('\nAll 8 screenshots successfully captured without errors!');
} finally {
  server.close();
}
