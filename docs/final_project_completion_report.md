# SupeRR Selector Season 2 — Project Completion Report

**Project:** Rajasthan Royals IPL 2027 scouting and evidence dashboard  
**Report date:** 14 November 2026  
**Data / availability cut-off:** 13 November 2026 for the local availability overlay; performance artifacts are the frozen project artifacts currently served by the API.

## Architecture

- **React + TypeScript frontend:** Vite application in `frontend/`, with seven lazy-loaded React Router sections and shared navigation, data cards, tables, loading/error/empty states, and Recharts visualizations.
- **FastAPI adapter:** `api/app.py` serves read-only `GET` endpoints over validated project artifacts. It binds to `127.0.0.1:8000`; the frontend defaults to `http://127.0.0.1:8000/api/v1`. CORS is limited to the local Vite origins.
- **Analytics and artifacts:** Python analysis, source data, Phase 5G/5H submission artifacts, and existing Streamlit dashboard remain separate from the React presentation layer. The React UI reads scores/order and evidence from the API; it does not calculate or sort rankings.
- **Streamlit:** The existing dashboard remains available and unchanged.

## Completed features

- Updated the shared dashboard to a consistent light palette, clearer contrast, larger page and section headings, readable controls, visible focus states, and more distinct cards/statuses.
- Improved chart axis and tooltip contrast and typography.
- Preserved search, filters, profile navigation, comparison selection, status distinctions, source links, loading/error/empty states, and the mobile navigation drawer.
- Fixed mobile content sizing at the tablet-to-mobile breakpoint and wrapped long artifact source labels to prevent horizontal overflow.
- Kept ranking, eligibility, methodology, source data, and availability values unchanged.
- Saved fresh full-page screenshots for every section at desktop, tablet, and mobile widths in `frontend/screenshots/`.

## Dashboard sections

1. **Overview** — analyzed scope, source coverage, stored Phase 5G preview, bowling readiness, and dated availability summary.
2. **Batter Rankings** — frozen Phase 5G Overall Top 10 and separate stored IPL and T20I supporting Top 10s.
3. **Player Discovery** — API-backed name/ID search, format/role filters, and available player evidence/profile views.
4. **Player Comparison** — same-format eligible batter selection and side-by-side stored evidence; comparison does not create a new score.
5. **Bowling Intelligence** — Phase 5H evidence and eligibility limitations, with **0 competition-ready candidates and 414 exploratory profiles**; no Bowler Top 10 or recommendation is presented.
6. **RR Auction Targets** — performance and dated availability shown as independent inputs; official registration/final-register gate remains explicit.
7. **Methodology** — ranking, contextual evidence, bowling limitations, and availability method explanations with linked local reports.

## Data and methodology summary

- Overall batter order is the authoritative frozen Phase 5G mean-within-format-percentile order. IPL and T20I supporting lists remain separate and retain their stored scores.
- The API and dashboard do not duplicate ranking calculations in TypeScript. Source rank, player ID, name, and score reconciliation passed for all 30 Top 10 rows.
- Wicket/phase evidence is a documented contextual proxy or cohort. It is not verified scoreboard pressure or psychological pressure.
- Phase 5H supports no competition-ready bowlers. Its 414 profiles are exploratory, not recommendations.
- Auction availability comes from the local, operator-managed overlay, with the verified snapshot dated **13 November 2026**. A trade, release, prior franchise, or performance rank does not establish auction registration or availability.
- No Phase 5I artifacts are represented as existing. The application does not invent player imagery, biographies, roles, prices, purse, squad needs, or an XI.

## Validation and testing

- Root Python suite: **113 passed** (`.\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider`).
- API suite: **14 passed** (`.\api\.venv\Scripts\python.exe -m pytest -q api\tests`).
- Frontend suite: **11 passed** (`npm.cmd test`).
- TypeScript check: passed (`npm.cmd run typecheck`).
- Production build: passed (`npm.cmd run build`).
- Local API smoke check: `/api/v1/health` returned HTTP 200.
- Direct API-to-source reconciliation: overall, IPL, and T20I lists each matched all 10 rows exactly on rank, player ID, name, and stored score. Bowling endpoint returned 0 / 414; availability endpoint returned 252 rows dated 2026-11-13.
- Route and browser smoke check: all seven routes loaded; mobile navigation opened and navigated; the comparison capture selected two players and displayed evidence.
- Screenshot capture: `npm.cmd run capture:screenshots` completed successfully for all 28 images at 1440×1200, 1024×1000, 768×1024, and 390×844. The capture script reported no horizontal overflow on any section/viewport. Each page was visually reviewed at desktop and mobile widths; no clipped layout, overlapping content, or blank section was found. Narrow ranking evidence values now wrap instead of truncating.
- The prior validated PDF and HTML report were not modified.

## Known limitations and auction dependencies

- The availability overlay is a dated local snapshot, not a live feed or a complete auction register. Current official registered/final-register target count is zero.
- Official IPL 2027 squad/retention state, player registration/final register, purse/auction resources, and resulting squad requirements are not established by the project artifacts. **Auction strategy is deferred** until these inputs are verified.
- Bowling source semantics and legal-ball/conceded-run denominators remain incomplete. No player-level bowling recommendation is supported.
- Contextual wicket/phase metrics do not verify scoreboard state or psychological pressure. Some player profile fields and exposure records are unavailable or sparse and remain labeled as such.
- The API is intentionally local and read-only and has no authentication. Do not bind it to a public interface.
- Automated screenshots and tests do not replace real-device assistive-technology or keyboard focus-trap testing. No focus trap is implemented for the mobile drawer.

## Start the applications

From `D:\ipl\SUPERR_SELECTOR_2027`, start the backend:

```powershell
.\api\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend:

```powershell
cd frontend
npm.cmd run dev
```

The frontend is served at `http://127.0.0.1:5173`. The existing Streamlit dashboard can be started separately from the project root with:

```powershell
.\venv\Scripts\streamlit.exe run dashboard/app.py
```

## Final submission checklist

- [x] All seven frontend sections render and browser route smoke checks pass.
- [x] Light-theme responsive screenshots saved for desktop, tablet, and mobile.
- [x] Root, API, and frontend test suites pass; TypeScript and production build pass.
- [x] Phase 5G Overall Top 10 and separate format lists reconcile to source artifacts.
- [x] Bowling is stated as 0 competition-ready / 414 exploratory, without a fabricated Bowler Top 10.
- [x] Availability snapshot date and unknown/unverified status limits remain explicit.
- [x] Existing analytics, ranking artifacts, source datasets, overlay, React/API/Streamlit logic, and final validated PDF were not changed as part of the visual update.
- [ ] Obtain official 2027 squad, registration/final-register, purse, and auction information before preparing a team-specific auction strategy.

## Screenshot paths

Screenshots use the `{section}-{viewport}.png` naming pattern under `frontend/screenshots/`; for example `frontend/screenshots/overview-desktop.png`, `frontend/screenshots/overview-laptop.png`, `frontend/screenshots/overview-tablet.png`, and `frontend/screenshots/overview-mobile.png`. The same four captures exist for all seven sections.
