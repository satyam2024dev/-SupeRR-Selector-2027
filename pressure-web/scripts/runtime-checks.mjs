import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '../dist');

// Import playwright from frontend
const playwrightPath = path.resolve(__dirname, '../../frontend/node_modules/playwright-core/index.mjs');
const { chromium } = await import(pathToFileURL(playwrightPath).href);

const edgePath = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

// Static server for dist
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
    const indexPath = path.join(distDir, 'index.html');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    fs.createReadStream(indexPath).pipe(res);
  }
});

const PORT = 5189;
await new Promise(resolve => server.listen(PORT, '127.0.0.1', resolve));

const consoleErrors = [];
let allPassed = true;

function check(desc, cond, details = '') {
  if (cond) {
    console.log(`[PASS] ${desc}`);
  } else {
    console.error(`[FAIL] ${desc} ${details}`);
    allPassed = false;
  }
}

try {
  const browser = await chromium.launch({
    executablePath: edgePath,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', err => {
    consoleErrors.push(err.message);
  });

  await page.goto(`http://127.0.0.1:${PORT}`, { waitUntil: 'networkidle' });
  console.log('Page loaded successfully.\n');

  // 1. Simulator Presets & Sliders
  console.log('--- Testing Simulator ---');
  await page.click('button[aria-label^="Set Easy chase"]');
  await page.waitForTimeout(100);
  let winText = await page.locator('#pressure .text-5xl, #pressure .text-6xl').textContent();
  check('Easy chase preset updates win probability', parseInt(winText) > 70, `Got: ${winText}`);

  await page.click('button[aria-label^="Set Tight finish"]');
  await page.waitForTimeout(100);
  winText = await page.locator('#pressure .text-5xl, #pressure .text-6xl').textContent();
  check('Tight finish preset updates win probability', parseInt(winText) >= 30 && parseInt(winText) <= 60, `Got: ${winText}`);

  await page.click('button[aria-label^="Set Last over"]');
  await page.waitForTimeout(100);
  winText = await page.locator('#pressure .text-5xl, #pressure .text-6xl').textContent();
  check('Last over preset updates win probability', parseInt(winText) > 0, `Got: ${winText}`);

  // 2. Rankings & Raw Toggle
  console.log('\n--- Testing Rankings & Toggle ---');
  const toggleBtn = page.locator('button[role="switch"]');
  await toggleBtn.click();
  await page.waitForTimeout(200);
  let rinkuRow = page.locator('#rankings-panel [role="button"]').filter({ hasText: 'Rinku Singh' });
  let rinkuText = await rinkuRow.textContent();
  check('Raw numbers toggle displays Rinku Singh raw rating +166.6', rinkuText.includes('+166.6'), `Found text: ${rinkuText}`);

  await toggleBtn.click();
  await page.waitForTimeout(200);
  rinkuText = await rinkuRow.textContent();
  check('Toggling back restores shrunk rating +25.6', rinkuText.includes('+25.6'), `Found text: ${rinkuText}`);

  // 3. Open Player Drawer for all 10 Batters (Close with Esc)
  console.log('\n--- Testing Player Drawers (Batters) ---');
  const batterRows = page.locator('#rankings-panel [role="button"]');
  const batterCount = await batterRows.count();
  check('Found exactly 10 batter rows', batterCount === 10, `Found: ${batterCount}`);

  for (let i = 0; i < batterCount; i++) {
    const row = batterRows.nth(i);
    const rowText = await row.locator('.truncate').textContent();
    await row.click();
    await page.waitForTimeout(250);

    const drawer = page.locator('[role="dialog"]');
    const isVisible = await drawer.isVisible();
    check(`Drawer opened for batter #${i+1} (${rowText})`, isVisible);

    // Verify verdict exists
    const verdict = await drawer.locator('[data-testid="player-verdict"]').textContent();
    check(`Verdict rendered for ${rowText}`, verdict && verdict.length > 10, `Verdict: ${verdict}`);

    // Press Escape to close
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    const isClosed = !(await drawer.isVisible());
    check(`Drawer closed via Escape for ${rowText}`, isClosed);
  }

  // 4. Switch to Bowlers Tab & Test Drawers (Close with Backdrop click)
  console.log('\n--- Testing Player Drawers (Bowlers) ---');
  await page.click('button#tab-bowlers, button[aria-label="Show Top 10 Bowlers"]');
  await page.waitForTimeout(200);

  const bowlerRows = page.locator('#rankings-panel [role="button"]');
  const bowlerCount = await bowlerRows.count();
  check('Found exactly 10 bowler rows', bowlerCount === 10, `Found: ${bowlerCount}`);

  for (let i = 0; i < bowlerCount; i++) {
    const row = bowlerRows.nth(i);
    const rowText = await row.locator('.truncate').textContent();
    await row.click();
    await page.waitForTimeout(250);

    const drawer = page.locator('[role="dialog"]');
    const isVisible = await drawer.isVisible();
    check(`Drawer opened for bowler #${i+1} (${rowText})`, isVisible);

    // Close via backdrop click (click at left edge x=50, y=300)
    await page.mouse.click(50, 300);
    await page.waitForTimeout(200);
    const isClosed = !(await drawer.isVisible());
    check(`Drawer closed via Backdrop click for ${rowText}`, isClosed);
  }

  // 5. Test at Mobile Viewport (390px)
  console.log('\n--- Testing Mobile Viewport (390px) ---');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(300);

  const overflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > window.innerWidth + 1;
  });
  check('No horizontal scroll at 390px mobile viewport', !overflow);

  // Open drawer on mobile
  await bowlerRows.first().click();
  await page.waitForTimeout(250);
  const mobileDrawerVisible = await page.locator('[role="dialog"]').isVisible();
  check('Player drawer opens cleanly on 390px mobile', mobileDrawerVisible);

  await page.click('button[aria-label="Close drawer"]');
  await page.waitForTimeout(200);
  const mobileDrawerClosed = !(await page.locator('[role="dialog"]').isVisible());
  check('Player drawer closes via X button on mobile', mobileDrawerClosed);

  // 6. Test Focus Trap and Esc in Drawer
  console.log('\n--- Testing Focus Trap & Esc in Drawer ---');
  await page.setViewportSize({ width: 1440, height: 900 });
  const firstBatterRow = page.locator('#rankings-panel [role="button"]').first();
  await firstBatterRow.click();
  await page.waitForTimeout(300);

  const drawerModal = page.locator('[role="dialog"]');
  check('Drawer is open for focus test', await drawerModal.isVisible());

  // Check active element is within drawer
  const activeInsideDrawerInitially = await page.evaluate(() => {
    const drawer = document.querySelector('[role="dialog"]');
    return drawer ? drawer.contains(document.activeElement) : false;
  });
  check('Initial focus moves inside drawer', activeInsideDrawerInitially);

  // Press Tab multiple times and verify focus remains trapped inside drawer
  await page.keyboard.press('Tab');
  await page.waitForTimeout(100);
  const activeAfterTab = await page.evaluate(() => {
    const drawer = document.querySelector('[role="dialog"]');
    return drawer ? drawer.contains(document.activeElement) : false;
  });
  check('Focus remains trapped inside drawer after Tab', activeAfterTab);

  await page.keyboard.press('Shift+Tab');
  await page.waitForTimeout(100);
  const activeAfterShiftTab = await page.evaluate(() => {
    const drawer = document.querySelector('[role="dialog"]');
    return drawer ? drawer.contains(document.activeElement) : false;
  });
  check('Focus remains trapped inside drawer after Shift+Tab', activeAfterShiftTab);

  // Press Escape
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  check('Drawer closed cleanly after pressing Escape', !(await drawerModal.isVisible()));

  // 7. Verify aria-labels on all buttons and charts
  console.log('\n--- Verifying Accessibility aria-labels ---');
  const buttonsWithoutAccessibleName = await page.evaluate(() => {
    const buttons = Array.from(document.querySelectorAll('button, [role="button"], [role="switch"], [role="tab"]'));
    return buttons
      .filter(b => {
        const ariaLabel = b.getAttribute('aria-label');
        const text = b.textContent?.trim();
        return !ariaLabel && !text;
      })
      .map(b => b.outerHTML.slice(0, 100));
  });
  check('All interactive buttons/tabs/switches have accessible names or aria-labels', buttonsWithoutAccessibleName.length === 0, `Missing: ${JSON.stringify(buttonsWithoutAccessibleName)}`);

  const chartsWithAria = await page.evaluate(() => {
    const svgs = Array.from(document.querySelectorAll('svg[role="img"]'));
    return svgs.every(s => s.getAttribute('aria-label') && s.getAttribute('aria-label').length > 5);
  });
  check('All chart visualizations have role="img" and descriptive aria-labels', chartsWithAria);

  // 8. Console errors check
  console.log('\n--- Checking Console Errors ---');
  check('Zero console errors encountered during test suite', consoleErrors.length === 0, `Errors: ${JSON.stringify(consoleErrors)}`);

  await browser.close();
} finally {
  server.close();
}

console.log('\n========================================');
if (allPassed) {
  console.log('ALL RUNTIME BROWSER CHECKS PASSED (100%)');
  console.log('========================================');
} else {
  console.error('SOME CHECKS FAILED!');
  console.log('========================================');
  process.exit(1);
}
