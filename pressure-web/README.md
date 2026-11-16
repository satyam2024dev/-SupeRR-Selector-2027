# Under Pressure: Who Delivers When It Matters?

An interactive single-page web application that reveals which batters and bowlers deliver most reliably in the highest-pressure moments of T20 cricket (IPL and T20I, 2022–2026). Built as a submission for SupeRR Selector Season 2, Round 1 (Rajasthan Royals).

Live site: <add URL after deploy>

---

## What the Site Shows (5 Sections)

1. **Hero**: Headline scope metrics (788 matches, 188,151 deliveries analyzed, with the top 20% of balls flagged as high pressure).
2. **Feel the Pressure**: An interactive chase leverage simulator with 3 real-time sliders (runs needed, balls left, wickets lost) demonstrating how situational pressure and win probability swing on every delivery.
3. **The Pressure Rankings**: Top 10 batters and top 10 bowlers with horizontal rating bars, statistical confidence badges (Secure, Likely, Close call), and an instant raw vs. shrunk rating toggle.
4. **Player Drawer**: Slide-over drawer comparing normal vs. high-pressure performance (Strike Rate or Economy Rate), IPL vs. T20I tournament splits, sample sizes, and plain-English verdicts.
5. **How Sure Are We?**: Bootstrap rank stability chart showing median rank and 80% confidence interval across 150 resamples, accompanied by an expandable methodology and limitations accordion.

---

## How the Ratings Were Made (Methodology)

- **Win-Probability Model**: Innings-specific logistic models cross-fitted by match, predicting match outcome from current state (chase log-loss: 0.402 vs. 0.692 baseline).
- **Pressure Index**: Expected absolute win-probability swing across 9 possible outcomes on the next delivery. High pressure is defined as the top 20% of balls within each context (IPL vs. T20I, innings 1 vs. 2).
- **Situational Comparison**: Every ball is compared with how an average player would perform in the exact same state, calculating win probability added per 100 high-pressure balls.
- **Shrinkage**: Empirical-Bayes shrinkage (DerSimonian-Laird) pulls small-sample raw ratings toward the league mean to prevent small-sample flukes from topping the table.
- **Final Composite Score**: Weighted composite of 50% pressure performance, 25% uplift over the player's own normal baseline, and 25% game-to-game consistency.
- **Eligibility Floor**: Strict qualification threshold of at least 100 high-pressure balls, 15 high-pressure innings, and 150 normal-situation balls.
- **Bootstrap Validation**: 150 match-clustered bootstrap resamples with replacement to assess rank stability.

---

## Top 10 Rankings

### Top 10 Batters
1. **Vaibhav Sooryavanshi** (Score: 2.06, Shrunk: +38.4) — Aggressive powerplay hitter maintaining rapid boundary tempo.
2. **Heinrich Klaasen** (Score: 2.05, Shrunk: +34.1) — Elite middle-order finisher (+50.5 SR under pressure).
3. **Rovman Powell** (Score: 1.59, Shrunk: +28.7) — Power hitter whose strike rate leaps 64 points in critical moments.
4. **Kusal Mendis** (Score: 1.55, Shrunk: +26.5) — Top-order anchor who absorbs pressure and limits dismissals.
5. **Mohammad Nawaz** (Score: 1.54, Shrunk: +28.2) — Reliable spin all-rounder with strong boundary-scoring in chases.
6. **Daryl Mitchell** (Score: 1.52, Shrunk: +30.0) — Middle-order consolidator who accelerates when matches tighten.
7. **Matthew Wade** (Score: 1.44, Shrunk: +27.7) — Finisher with exceptional wicket preservation in close finishes.
8. **Rinku Singh** (Score: 1.35, Shrunk: +25.6) — Elite raw strike rate (+166.6), adjusted for a concentrated 30-inning sample.
9. **Dinesh Karthik** (Score: 1.27, Shrunk: +25.9) — Veteran death-overs specialist scoring at 189 strike rate.
10. **Prabhsimran Singh** (Score: 1.26, Shrunk: +20.3) — Fast-scoring opener putting bowling attacks under immediate pressure.

### Top 10 Bowlers
1. **Sunil Narine** (Score: 3.36, Shrunk: +45.2) — Undisputed #1: 6.3 economy under pressure and doubles wicket rate.
2. **Rashid Khan** (Score: 1.87, Shrunk: +29.4) — High-volume wicket threat keeping economy tight in high-leverage overs.
3. **Mitchell Santner** (Score: 1.80, Shrunk: +32.4) — Economical finger spinner whose output rises when matches are on the line.
4. **Josh Hazlewood** (Score: 1.70, Shrunk: +22.6) — Disciplined seam bowler with heightened strike power at the death.
5. **Mohsin Khan** (Score: 1.51, Shrunk: +22.3) — High-impact wicket-taker in late-inning pressure situations.
6. **Adam Zampa** (Score: 1.30, Shrunk: +18.7) — Aggressive leg-spinner whose wicket frequency increases under stress.
7. **Taskin Ahmed** (Score: 1.28, Shrunk: +19.9) — Frontline pace bowler maintaining control in tight overs.
8. **Shoriful Islam** (Score: 1.18, Shrunk: +19.1) — Left-arm swing and death seamer who lowers economy under pressure.
9. **Maheesh Theekshana** (Score: 1.17, Shrunk: +14.4) — Powerplay and middle-overs mystery spinner with steady control.
10. **Lockie Ferguson** (Score: 1.14, Shrunk: +24.1) — Express pace bowler with elevated strike rate in clutch moments.

*Key Takeaway: Narine is the undisputed top bowling pick; Sooryavanshi and Klaasen are virtually tied for the top batting spot.*

---

## Honest Limitations

- **Estimated Extras Runs**: The raw ball-by-ball feed lacked exact run breakdowns for extras; missing extras were estimated via regression (wide 1.15, no-ball 1.0 + bat runs, bye 2.1, leg-bye 1.3).
- **No Venue or Pitch Data**: Match logs do not record pitch deterioration, boundary dimensions, or dew factors.
- **Situational Pressure Only**: Measures scoreboard leverage and match consequence, not physiological heart rate or biological stress.
- **Noisy Individual Ratings**: Single-season sample sizes have inherent variance (split-half correlation approximately 0.12).
- **Simulator Is Illustrative**: The interactive leverage widget uses a simplified logistic approximation to demonstrate situational dynamics.

---

## Running Locally

From the `pressure-web` directory:

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Run data integrity checks
node scripts/check-data.mjs

# Type check without emitting
npx tsc --noEmit

# Build production bundle (into dist/)
npm run build

# Preview production build locally
npm run preview
```

---

## Deployment

The application is a pure client-side SPA with zero runtime server requirements.

- **Vercel**:
  - Root directory: `pressure-web`
  - Framework preset: `Vite`
  - Build command: `npm run build`
  - Output directory: `dist`
- **Netlify**:
  - Base directory: `pressure-web`
  - Build command: `npm run build`
  - Publish directory: `pressure-web/dist` (or `dist` if root set to `pressure-web`)

---

## Real File Layout

```
pressure-web/
├── public/
│   ├── ranking_batters_all_eligible.csv
│   ├── ranking_bowlers_all_eligible.csv
│   └── report.pdf
├── scripts/
│   └── check-data.mjs
├── src/
│   ├── components/
│   │   ├── BootstrapChart.tsx
│   │   ├── ChaseSimulator.tsx
│   │   ├── Footer.tsx
│   │   ├── HeroSection.tsx
│   │   ├── MethodologySection.tsx
│   │   ├── Navbar.tsx
│   │   ├── PlayerDrawer.tsx
│   │   └── RankingsSection.tsx
│   ├── data/
│   │   └── pressureData.json
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── index.css
│   ├── main.tsx
│   └── vite-env.d.ts
├── index.html
├── package.json
├── postcss.config.js
├── tailwind.config.js
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── .gitignore
└── README.md
```

---

## Verification & Data Integrity

All numbers are served from `src/data/pressureData.json` and validated by `scripts/check-data.mjs`. Downloads for the full methodology report (`report.pdf`) and eligible player CSVs are available directly in the site footer.

Live site: <add URL after deploy>
