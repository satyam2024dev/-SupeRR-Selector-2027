# SupeRR Selector 2027 — Final Application Quality Audit

Audit date: 2026-11-14  
Project: `D:\ipl\SUPERR_SELECTOR_2027`

## Scope and outcome

Reviewed the seven React sections, route shell, read-only FastAPI adapter, source artifacts, local availability overlay handling, Streamlit entry point, frontend build configuration, API configuration, and available submission/PDF artifacts. The React application is an additive interface; Streamlit and the analytical pipeline remain intact.

### Section review

| Section | Routes and source | Audit result |
|---|---|---|
| Overview | `/`; `/overview`, `/rankings/batters/overall`, `/auction/availability`, `/auction/targets` | Uses confirmed-scope counts, format coverage, stored Phase 5G top three, bowling status and dated availability. Loading/error/empty states exist. Availability and ranking are shown as separate evidence. |
| Batter Rankings | `/rankings`; overall Phase 5G and Phase 5C supporting lists | Stored order and scores render directly. IPL and T20I support remain separate, with no frontend score computation. |
| Player Discovery | `/discovery`, `/discovery/:playerId`; player search and profile endpoints | Name/ID search, role/format filters, exposure cards, profile metrics, missing-field states and image fallbacks are data-backed. The profile route breadcrumb incorrectly showed Overview; fixed and covered by a UI test. |
| Player Comparison | `/comparison`; comparison candidate and compare endpoints | Same-format candidate filtering and stored comparisons are intact; incomplete profiles render unavailable fields. It states the contextual proxy is not verified scoreboard or psychological pressure. |
| Bowling Intelligence | `/bowling`; Phase 5H evidence | Preserves 0 competition-ready and 414 exploratory profiles, lists calculable descriptive evidence and blocked conventional metrics. Fixed the misleading “Verified pressure” column label to “Verified-chase cohort.” No bowling recommendations are generated. |
| RR Auction Targets | `/auction`; Phase 5G plus availability/target endpoints | Frozen performance list and availability status remain independent. Sources, publication/verification dates, empty states and the official-registration gate are surfaced. Unknown or future unrecognized statuses are retained in the unconfirmed section. |
| Methodology | `/methodology`; approved Phase 5H reports | Shows concise definitions and source reports, including ranking, contextual-proxy and bowling limits. Long report text is collapsed by default. |

All routes are React Router routes with lazy-loaded page modules; unknown routes redirect to Overview. Mobile navigation exposes the same seven sections. Screenshot capture now exercises all seven routes at 1440, 768 and 390 CSS pixels and checks for horizontal document overflow.

## Data integrity and source mapping

- Overall Batter Top 10 is read from `submission/phase5g_overall_batter_top10.csv`; format supporting lists are the submitted IPL/T20I artifacts. Phase 5H independently validates Phase 5G. No TypeScript ranking calculation or score sorting was found.
- Player profiles, exposure, comparison and discovery use existing report artifacts through the API. Missing biography, images and optional values are not filled with inferred values.
- Contextual wicket/phase groupings are described as contextual cohorts/proxies. They are not represented as verified scoreboard pressure or psychological pressure.
- Bowling status remains 0 competition-ready / 414 exploratory; the UI does not display an exploratory ranking as a recommendation.
- Auction target qualification is server-side status gating over the existing availability overlay and batter eligibility. Availability status does not alter Phase 5G performance order. The current overlay contains 252 role records (107 batters, 145 bowlers); 245 have `unknown_unverified` and 7 role rows (6 distinct player IDs) have `traded_to_other_franchise`. The 245 unverified rows have no publication date and link to a general IPL news index, not a player-specific announcement; the player-level state is therefore correctly unknown. The six traded IDs have dated official announcement URLs. No official registration/final-register target is present in the snapshot.
- The overlay is local and operator-managed by the approved decision. Its contents, ignore rule and source classifications were not modified. There is no Git metadata at the project root in this workspace, so ignore status could not be checked with `git check-ignore`; the `.gitignore` rule was reviewed directly.
- No raw supplied data or analytical output was edited. Final raw-data hashes and ranking verification are reported after validation below.

## API and security review

- `api/app.py` computes the project root from its own file location and reads only code-whitelisted reports/submission/external paths. The API accepts no client-supplied file paths and does not expose raw source tables or environment variables.
- All application routes are GET. CORS allows only `localhost:5173` and `127.0.0.1:5173`, GET/OPTIONS, and no credentials. The documented startup binds Uvicorn to `127.0.0.1`.
- Player comparison is bounded to 2–4 distinct IDs; list limits and format/role enums are bounded. Added maximum lengths for player search, comparison ID query and availability status inputs.
- Missing required artifacts return HTTP 503; missing optional availability is explicitly represented as unavailable. Unknown player evidence returns 404. Validation errors use FastAPI 422 responses.
- OpenAPI docs are locally reachable, and no write/update/delete route exists. There is no authentication: this is suitable only for the documented local trusted-user setup. Do not bind the API to a public interface or reverse proxy without a separately reviewed access-control requirement.
- The health endpoint returns service status plus artifact-presence checks; it does not itself turn a missing artifact into a non-200 health response. Clients should continue using page-level unavailable/error states.

## Performance, rendering and accessibility review

- Each section is imported with `React.lazy`; charting is in a separate build chunk. Initial JavaScript output is measured in the production build below; the current initial bundle is below Vite's 500 kB warning threshold. Further splitting the common shell/dependency graph was not justified by this local audit.
- Responsive screenshots are generated at desktop, tablet and mobile widths; the capture script fails if document-level horizontal overflow is detected. Screenshots are stored in `frontend/screenshots/`.
- Current images use initials as accessible fallbacks; no external player-image dependency exists.
- Mobile drawer exposes open/close controls and route links. A focus trap and automated browser-based keyboard/focus audit are not implemented; keyboard and assistive-technology testing remains a limitation.
- No real-device performance trace or external network performance test was run. This is a local evidence application.

### Screenshot set

All captures are fresh full-page browser screenshots produced at 1440×1200 desktop, 768×1024 tablet and 390×844 mobile CSS viewports. Each capture passed the document-width overflow check.

| Section | Desktop | Tablet | Mobile |
|---|---|---|---|
| Overview | [PNG](../frontend/screenshots/overview-desktop.png) | [PNG](../frontend/screenshots/overview-tablet.png) | [PNG](../frontend/screenshots/overview-mobile.png) |
| Batter Rankings | [PNG](../frontend/screenshots/rankings-desktop.png) | [PNG](../frontend/screenshots/rankings-tablet.png) | [PNG](../frontend/screenshots/rankings-mobile.png) |
| Player Discovery | [PNG](../frontend/screenshots/discovery-desktop.png) | [PNG](../frontend/screenshots/discovery-tablet.png) | [PNG](../frontend/screenshots/discovery-mobile.png) |
| Player Comparison | [PNG](../frontend/screenshots/comparison-desktop.png) | [PNG](../frontend/screenshots/comparison-tablet.png) | [PNG](../frontend/screenshots/comparison-mobile.png) |
| Bowling Intelligence | [PNG](../frontend/screenshots/bowling-desktop.png) | [PNG](../frontend/screenshots/bowling-tablet.png) | [PNG](../frontend/screenshots/bowling-mobile.png) |
| RR Auction Targets | [PNG](../frontend/screenshots/auction-desktop.png) | [PNG](../frontend/screenshots/auction-tablet.png) | [PNG](../frontend/screenshots/auction-mobile.png) |
| Methodology | [PNG](../frontend/screenshots/methodology-desktop.png) | [PNG](../frontend/screenshots/methodology-tablet.png) | [PNG](../frontend/screenshots/methodology-mobile.png) |

## Controlled fixes made

1. Fixed the profile route breadcrumb so `/discovery/:playerId` remains labeled Player Discovery.
2. Replaced the misleading bowling “Verified pressure” heading with “Verified-chase cohort.”
3. Preserved unrecognized availability statuses in the explicit unconfirmed group rather than hiding them from status sections.
4. Bounded API search, comparison-ID and status query lengths.
5. Expanded screenshot automation from three pages to all seven, with 3 viewport widths and overflow checks.
6. Updated frontend documentation to reflect the approved local/operator-managed overlay decision and its safe update procedure.
7. Repaired corrupted replacement glyphs in visible React copy where the source contained U+FFFD.

These fixes do not change scores, ranking order, eligibility criteria, analytical thresholds or source-data classifications.

## Validation record

| Check | Result |
|---|---|
| Existing analytics tests | **113 passed** |
| API tests | **14 passed**, including bounds, CORS and status-gate checks |
| Frontend tests | **11 passed** across 3 test files |
| TypeScript check and production build | **Passed** (`tsc -b`; Vite build successful) |
| Phase 5H vs Phase 5G | **Passed**: exact order, 305 eligible rows, 10 unique IDs, max percentile difference 0.0; IPL/T20I support APIs also match stored ranks, IDs and scores |
| API startup smoke test | **Passed**: localhost health endpoint returned `status: ok` and all four artifact checks true |
| React startup and navigation smoke test | **Passed**: all seven direct routes loaded; mobile drawer navigation to Batter Rankings worked |
| Streamlit startup smoke test | **Passed**: `dashboard/app.py` returned HTTP 200; process was stopped after the check |
| Desktop/tablet/mobile screenshots | **Passed**: 21 captures (7 sections × 3 viewport sizes); each passed document overflow check |
| In-memory Python compilation | **Passed**: 1,374 Python files across `src/`, `api/`, `dashboard/` and `tests/` |

The final production bundle contains a 399.62 kB initial JavaScript chunk (127.92 kB gzip), plus lazy-loaded route chunks and a separate 368.87 kB chart chunk (105.95 kB gzip). No Vite chunk-size warning was emitted. The generated ranking package hash is SHA-256 `c4be291e1eeb456984f1299132aa257449b2e9075b2abe75e8d62a7b7f74a630`; the local availability overlay hash is `b705925a1595e8358e324aedf8eec5ec033f0a7f80dfeb66efa9974127c03109`.

Raw files were not written by this audit. Their final SHA-256 inventory was recorded: `ball_by_ball.csv` `a3926f49d2c684dca2a5d2de535a02c5ee46ea654ca1e79dd31c69e7544e9889`; `competition_team_player_mapping.csv` `1ded4e42a933618572d6e2c3a521c3257eb1844fab4456d567d77cbb2d3bbb12`; `competitions.csv` `507ceb7189f972d4e4f299ddcfc97f3c3247af1913f6291106f161fa8353fd9b`; `matches.csv` `bb100ab84b8b9a15160c1f2315cf675210131a30e779ec5079fd5403dcf56eef`; `playing_eleven.csv` `7517c73722a28d5d61c808ccf0cbed315a8780586d02e946eb9a7f5daf011c27`; `teams.csv` `a65e5922a9b3bf49247b24fc9471782e700efb31f8dcc5042923238b87c50a5d`; source data ZIP `788f681b538ba95fb61bcaba7b7280e59a7789d043e7964ac3472c3d08291853`; original brief PDF `8f7965c616d4a64b779e770a6b2c17dde2a6d2ccbf7de12a58b04db792162489`.

## Remaining limitations

- The official 2027 retention/release schedule, RR squad state, auction pool/final register and available purse/slots are not included in the local verified overlay. It therefore reports no confirmed auction targets.
- The requested reference 2026 Rajasthan Royals auction strategy PDF was not found in the project submission, presentation, docs or raw-data PDF inventory; only the original project brief PDF was present. The report readiness audit describes this as an unavailable reference, not as a reviewed document.
- API authentication is intentionally out of scope for the local-only setup.
- Screenshot and automated overflow checks do not replace manual browser/assistive-technology review on actual devices.
