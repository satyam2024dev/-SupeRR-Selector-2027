import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "../frontend/node_modules/playwright-core/index.mjs";

const [htmlArgument, pdfArgument] = process.argv.slice(2);
if (!htmlArgument || !pdfArgument) {
  throw new Error("Usage: node scripts/render_ipl_2027_report.mjs <source.html> <output.pdf>");
}

const htmlPath = path.resolve(htmlArgument);
const pdfPath = path.resolve(pdfArgument);
const edgePath = process.env.EDGE_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const browser = await chromium.launch({ executablePath: edgePath, headless: true, args: ["--no-sandbox"] });
try {
  const page = await browser.newPage({ viewport: { width: 1240, height: 1754 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: pdfPath,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    displayHeaderFooter: true,
    margin: { top: "17mm", bottom: "18mm", left: "16mm", right: "16mm" },
    headerTemplate: '<div style="width:100%;margin:0 16mm;border-bottom:.5px solid #bdc9d8;color:#63748a;font:7pt Arial,sans-serif;letter-spacing:1px;text-transform:uppercase;padding:0 0 4px">Rajasthan Royals IPL 2027 | Evidence report | Data cut-off 13 November 2026</div>',
    footerTemplate: '<div style="width:100%;margin:0 16mm;border-top:.5px solid #bdc9d8;color:#63748a;font:7pt Arial,sans-serif;padding:4px 0 0;display:flex;justify-content:space-between"><span>SupeRR Selector | Source-led analysis</span><span>Page <span class="pageNumber"></span></span></div>',
    tagged: true,
  });
  console.log(`Rendered ${pdfPath}`);
} finally {
  await browser.close();
}
