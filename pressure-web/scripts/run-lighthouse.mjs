import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const distDir = path.resolve(__dirname, '../dist');

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
    res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' });
    fs.createReadStream(filePath).pipe(res);
  } else {
    const indexPath = path.join(distDir, 'index.html');
    res.writeHead(200, { 'Content-Type': 'text/html' });
    fs.createReadStream(indexPath).pipe(res);
  }
});

const PORT = 4173;
server.listen(PORT, '127.0.0.1', async () => {
  console.log(`Server listening at http://127.0.0.1:${PORT}`);
  process.env.CHROME_PATH = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

  const runLH = (preset, name) => {
    console.log(`\n=== Running Lighthouse for ${name} ===`);
    const outputPath = path.resolve(__dirname, `../lighthouse-${name}.json`);
    const flags = preset === 'desktop'
      ? `--preset=desktop --chrome-flags="--headless=new --no-sandbox --disable-gpu"`
      : `--form-factor=mobile --screenEmulation.mobile --chrome-flags="--headless=new --no-sandbox --disable-gpu"`;

    const cmd = `npx.cmd --yes lighthouse http://127.0.0.1:${PORT} ${flags} --output=json --output-path="${outputPath}" --only-categories=performance,accessibility,best-practices,seo --no-enable-error-reporting`;
    
    execSync(cmd, { stdio: 'inherit', env: process.env });

    const raw = fs.readFileSync(outputPath, 'utf-8');
    const result = JSON.parse(raw);
    const scores = {
      performance: Math.round((result.categories.performance?.score || 0) * 100),
      accessibility: Math.round((result.categories.accessibility?.score || 0) * 100),
      bestPractices: Math.round((result.categories['best-practices']?.score || 0) * 100),
      seo: Math.round((result.categories.seo?.score || 0) * 100),
    };
    
    fs.unlinkSync(outputPath);
    return scores;
  };

  try {
    const desktopScores = runLH('desktop', 'desktop');
    console.log('\n--- Desktop Scores ---');
    console.log(`Performance:    ${desktopScores.performance}`);
    console.log(`Accessibility:  ${desktopScores.accessibility}`);
    console.log(`Best Practices: ${desktopScores.bestPractices}`);
    console.log(`SEO:            ${desktopScores.seo}`);

    const mobileScores = runLH('mobile', 'mobile');
    console.log('\n--- Mobile Scores ---');
    console.log(`Performance:    ${mobileScores.performance}`);
    console.log(`Accessibility:  ${mobileScores.accessibility}`);
    console.log(`Best Practices: ${mobileScores.bestPractices}`);
    console.log(`SEO:            ${mobileScores.seo}`);

    console.log('\nLighthouse audit complete successfully.');
  } catch (err) {
    console.error('Lighthouse run failed:', err);
  } finally {
    server.close();
  }
});
