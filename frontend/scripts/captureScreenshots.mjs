import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright-core";

const directory = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(directory, "../screenshots");
const edgePath = process.env.EDGE_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const baseUrl = process.env.FRONTEND_URL ?? "http://127.0.0.1:5173";
const pages = [
  { page: "overview", route: "/", ready: ".hero-panel" },
  { page: "rankings", route: "/rankings", ready: ".player-evidence-card" },
  { page: "discovery", route: "/discovery", ready: ".discovery-toolbar" },
  { page: "comparison", route: "/comparison", ready: ".comparison-layout" },
  { page: "bowling", route: "/bowling", ready: ".bowling-status-grid" },
  { page: "auction", route: "/auction", ready: ".auction-status-grid" },
  { page: "methodology", route: "/methodology", ready: ".method-grid" },
];
const sizes = [
  { name: "desktop", width: 1440, height: 1200 },
  { name: "laptop", width: 1024, height: 1000 },
  { name: "tablet", width: 768, height: 1024 },
  { name: "mobile", width: 390, height: 844 },
];

await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: edgePath, headless: true, args: ["--no-sandbox"] });
let mobileNavigationChecked = false;
try {
  for (const size of sizes) {
    for (const view of pages) {
      const page = await browser.newPage({ viewport: { width: size.width, height: size.height }, deviceScaleFactor: 1, isMobile: size.width < 600 });
      await page.goto(`${baseUrl}${view.route}`, { waitUntil: "networkidle" });
      await page.waitForSelector(view.ready, { timeout: 15_000 });
      if (size.name === "mobile" && !mobileNavigationChecked) {
        await page.locator(".mobile-menu-button").click();
        await page.locator(".mobile-drawer").waitFor();
        await page.locator(".mobile-drawer .nav-link").filter({ hasText: "Batter Rankings" }).click();
        await page.waitForURL("**/rankings");
        mobileNavigationChecked = true;
        await page.goto(`${baseUrl}${view.route}`, { waitUntil: "networkidle" });
        await page.waitForSelector(view.ready, { timeout: 15_000 });
      }
      if (view.page === "comparison") {
        const choices = page.locator(".player-choice input");
        if (await choices.count() >= 2) {
          await choices.nth(0).check();
          await choices.nth(1).check();
          await page.waitForSelector(".comparison-player-grid", { timeout: 15_000 });
        }
      }
      const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }));
      if (dimensions.width !== size.width) throw new Error(`${view.page}: expected viewport ${size.width}px, got ${dimensions.width}px`);
      if (dimensions.scrollWidth > dimensions.width + 1) throw new Error(`${view.page}: horizontal overflow ${dimensions.scrollWidth}px in ${dimensions.width}px viewport`);
      const filename = `${view.page}-${size.name}.png`;
      await page.screenshot({ path: path.join(output, filename), fullPage: true });
      await page.close();
      process.stdout.write(`Captured ${filename} (${dimensions.width}px, no horizontal overflow)\n`);
    }
  }
} finally {
  await browser.close();
}
