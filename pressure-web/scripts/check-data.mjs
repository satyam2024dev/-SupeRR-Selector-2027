import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
let dataPath = path.resolve(__dirname, '../src/data/pressureData.json');
if (!fs.existsSync(dataPath)) {
  dataPath = path.resolve(__dirname, '../pressure-web/src/data/pressureData.json');
}

const raw = fs.readFileSync(dataPath, 'utf-8');
const data = JSON.parse(raw);

let allPassed = true;
function check(description, condition, details = '') {
  if (condition) {
    console.log(`[PASS] ${description}`);
  } else {
    console.error(`[FAIL] ${description} ${details}`);
    allPassed = false;
  }
}

console.log('--- Running pressureData.json Data Integrity Audit ---\n');

// 1. Batters count and ranks
const batters = data.top10Batters;
check('Batters count is exactly 10', batters && batters.length === 10, `Found: ${batters?.length}`);
const batterRanks = batters.map(b => b.rank);
check('Batter ranks are 1 to 10 without duplicates', 
  JSON.stringify(batterRanks) === JSON.stringify([1,2,3,4,5,6,7,8,9,10]),
  `Ranks: ${JSON.stringify(batterRanks)}`
);

// 2. Bowlers count and ranks
const bowlers = data.top10Bowlers;
check('Bowlers count is exactly 10', bowlers && bowlers.length === 10, `Found: ${bowlers?.length}`);
const bowlerRanks = bowlers.map(b => b.rank);
check('Bowler ranks are 1 to 10 without duplicates',
  JSON.stringify(bowlerRanks) === JSON.stringify([1,2,3,4,5,6,7,8,9,10]),
  `Ranks: ${JSON.stringify(bowlerRanks)}`
);

// 3. Confidence badge check
const allPlayers = [...batters, ...bowlers];
let confidenceMatches = true;
const confidenceErrors = [];

for (const p of allPlayers) {
  let expected = 'Close call';
  if (p.pTop10 >= 0.75) expected = 'Secure';
  else if (p.pTop10 >= 0.45) expected = 'Likely';

  if (p.confidence !== expected) {
    confidenceMatches = false;
    confidenceErrors.push(`${p.name}: pTop10=${p.pTop10}, confidence='${p.confidence}' (expected '${expected}')`);
  }
}
check('Confidence badges match P(top 10) threshold for all 20 players', confidenceMatches, confidenceErrors.join('; '));

// 4. Rinku Singh raw 166.6 and shrunk 25.6
const rinku = batters.find(b => b.name === 'Rinku Singh');
check('Rinku Singh exists in top 10 batters', !!rinku);
if (rinku) {
  check('Rinku Singh raw rating is 166.6', rinku.rawRating === 166.6, `Found: ${rinku.rawRating}`);
  check('Rinku Singh shrunk rating is 25.6', rinku.shrunkRating === 25.6, `Found: ${rinku.shrunkRating}`);
}

// 5. Sunil Narine P(top 10) 0.99
const narine = bowlers.find(b => b.name === 'Sunil Narine');
check('Sunil Narine exists in top 10 bowlers', !!narine);
if (narine) {
  check('Sunil Narine P(top 10) is 0.99', narine.pTop10 === 0.99, `Found: ${narine.pTop10}`);
}

console.log('\n--- Audit Complete ---');
if (!allPassed) {
  process.exit(1);
} else {
  console.log('All data checks passed cleanly!\n');
}
