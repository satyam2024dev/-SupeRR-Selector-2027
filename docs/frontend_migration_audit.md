# SupeRR Selector 2027 - Frontend Migration Architecture Audit

Audit date: 2026-11-13
Scope: read-only inspection and migration planning. No React application or API was implemented in this phase.

## 1. Current architecture

The project is a local Python analytics repository with a Streamlit presentation layer. There is no existing HTTP API. The Streamlit app reads project-relative CSV/Markdown/JSON artifacts and local source tables; analysis and validation logic lives under `src/` and produces versioned report artifacts under `outputs/reports/` and `submission/`.

```text
Streamlit UI (dashboard/app.py, dashboard/auction.py)
                  |
                  +-- validated CSV/JSON/Markdown artifacts
                  |      outputs/reports/
                  |      submission/
                  |      data/external/ipl_2027_player_availability.csv
                  |
                  +-- local source tables when a page needs them
                         data/raw/
                         data/processed/

Python analysis and audit modules: src/
Tests: tests/
```

Top-level areas include `src/`, `dashboard/`, `data/raw/`, `data/processed/`, `data/external/`, `outputs/reports/`, `outputs/charts/`, `submission/`, `notebooks/`, `presentation/`, `tests/`, and a local `venv/`. The inspected data formats are CSV, compressed CSV, JSON, PDF, ZIP, and Jupyter notebooks. There are 133 report files and 19 submission files at audit time. Raw source files include six CSV tables, a source-data ZIP, and the competition brief PDF. Processed data currently contains three compressed CSV artifacts.

The current dashboard is one Streamlit entry point with ten radio-navigation sections: Overview, Player Discovery, Batter Rankings, Bowling Analysis, Player Comparison, Pressure Analysis, Match Explorer, Methodology & Data Quality, Final Submission, and RR Auction Targets. Shared theme and empty-state helpers are in `dashboard/components/ui.py`; the auction view is separated into `dashboard/auction.py`. There is no frontend build system or `package.json`.

## 2. Important files and responsibilities

| Area | Files | Responsibility |
|---|---|---|
| Streamlit shell | `dashboard/app.py` | Navigation, cached artifact/source loading, overview, player exploration, ranking, comparison, pressure, match, methodology, and submission views. |
| Shared UI | `dashboard/components/ui.py` | Theme, shared headings and empty/report states. |
| Auction UI | `dashboard/auction.py` | Displays the frozen performance list and availability-gated auction views; does not score or rank players. |
| Paths and loading | `src/config.py`, `src/data_loader.py` | Project-root paths and local tabular input loading. |
| Pressure and match states | `src/match_state.py`, `src/phase2b_pipeline.py`, `src/pressure_analysis.py`, `src/pressure_methodology.py` | Conservative state reconstruction, pressure features, paired cohorts, and coverage evidence. |
| Eligibility and player evidence | `src/player_eligibility.py`, `src/eligibility.py`, `src/metric_evidence.py`, `src/player_analytics.py`, `src/player_comparison.py` | Exposure eligibility, metric evidence, descriptive profiles, and comparison utilities. |
| Performance rankings | `src/phase5c_final_ranking.py`, `src/phase5g_reconciliation.py`, `src/phase5h_final_audit.py` | Format-level ranking artifacts, overall cross-format list reconciliation, and independent audit. |
| Submission packaging | `src/package_submission.py` | Validates and copies report artifacts into `submission/`; it writes files and must not be called by a read-only API request. |
| Bowling audit | `submission/phase5h_bowling_metric_audit.csv`, `submission/phase5h_bowling_eligibility.csv`, `submission/phase5h_bowling_final_audit.md` | Source-field, denominator, eligibility, and no-ranking evidence. |
| Auction overlay | `src/ipl_2027_availability.py`, `data/external/ipl_2027_player_availability.csv` | Creates an auditable status overlay from eligible IPL profiles, project franchise mapping, and curated official transaction records. Snapshot verification date is 2026-11-13. |
| Tests | `tests/test_*.py` | 113 automated checks across loading, pressure, eligibility, ranking methodology, source validation, and availability safeguards. |
| Configuration | `requirements.txt`, `.env.example`, `.gitignore`, `src/config.py` | Python dependencies, optional local data/date settings, ignore rules, and derived project paths. |

## 3. Existing data sources and source-of-truth mapping

The React client should consume the existing artifacts through a read-only API. The API should not reproduce formulas, eligibility filters, ordering, or ranking tie breaks in TypeScript.

| Frontend data | Current source of truth | Notes |
|---|---|---|
| Executive coverage | `outputs/reports/confirmed_scope_coverage_summary.csv`; supporting inventory in `outputs/reports/dataset_inventory.csv` | Use confirmed IPL/T20I scope totals, not the full raw-table row count. The raw tables include out-of-scope records. |
| Overall Batter Top 10 | `submission/phase5g_overall_batter_top10.csv`; matching report source `outputs/reports/phase5g_overall_batter_top10.csv` | Ten-row frozen order. `src/phase5h_final_audit.py:verify_overall_batters()` independently rebuilds the list from eligible Phase 5C rows and checks the percentile values. The package copy is the appropriate presentation artifact. |
| IPL/T20I format rankings | `outputs/reports/phase5c_batter_rankings.csv`; supporting package lists `submission/supporting_IPL_batter_top10.csv` and `submission/supporting_T20I_batter_top10.csv` | Phase 5C rows carry rank, score, pressure/baseline evidence, exposure, consistency, and limitations. Supporting Top 10 files are not additional overall lists. |
| Player profiles | `outputs/reports/batter_performance_profile.csv`, `bowler_performance_profile.csv`, `player_exposure_summary.csv` | Descriptive cohorts and exposure, not a second set of pressure scores or rankings. `outputs/reports/player_analytics_limitations.md` defines interpretation limits. |
| Discovery and comparison | The profile/exposure artifacts above; `src/player_comparison.py` | There is no separate discovery database or API. IDs are local provider IDs. Keep format and cohort distinctions intact. |
| Bowling evidence | `outputs/reports/phase5c_bowler_rankings.csv`, `submission/phase5h_bowling_metric_audit.csv`, `submission/phase5h_bowling_eligibility.csv`, `submission/phase5h_bowling_final_audit.md` | 0 competition-ready candidates and 414 exploratory profiles. Do not render the Phase 5C exploratory order as a recommended bowling ranking. Economy and conventional bowling strike rate are blocked by source semantics/denominators. |
| Auction availability | `data/external/ipl_2027_player_availability.csv`; generated by `src/ipl_2027_availability.py` | 252 player-role records: 107 eligible IPL batter profiles and 145 IPL bowler profiles for availability-only display. Six distinct analyzed IDs have official trade records. No record was marked registered or included in the final auction register in the 2026-11-13 snapshot. |
| Methodology and evidence | `submission/phase5h_methodology_report.md`, `submission/phase5h_submission_readiness.md`, reports under `outputs/reports/` | Serve approved summaries and/or source Markdown; avoid exposing the full development report history as navigation. |
| Data quality | `outputs/reports/data_quality_report.csv`, `dataset_inventory.csv`, `confirmed_scope_coverage_summary.csv`, `outputs/reports/accepted_data_dictionary.md` | These describe dataset-level checks, scope, and field semantics. They do not certify every row as a complete scorecard. |

The overall list uses the validated mean within-format percentile reconciliation of Phase 5C scores. Scores are already affected by the existing exposure and match-consistency adjustments. Formats are not pooled as raw scores. The independent Phase 5H result for the current package is: 305 eligible player-format rows, 10 unique overall IDs, ranks 1-10, exact order reproduction, and maximum percentile difference 0.0.

The source files behind the local pipeline are `data/raw/ball_by_ball.csv`, `matches.csv`, `competitions.csv`, `teams.csv`, `playing_eleven.csv`, and `competition_team_player_mapping.csv`. `data/processed/` contains reconstructed or accepted event layers. Raw and processed records must remain server-side; frontend access should be limited to approved derived fields.

## 4. Existing API availability

No FastAPI, Flask, route decorators, API routers, or Uvicorn entry point were found in `src/`, `dashboard/`, or `requirements.txt`. Current access is through Streamlit and filesystem artifacts. `requirements.txt` contains Streamlit and analytics packages but no API or Node/React dependencies.

A future minimal FastAPI adapter can be introduced in a separate `api/` directory. It should read whitelisted artifacts and return typed JSON only. Do not invoke pipeline `main()` functions from request handlers: ranking, packaging, and analysis entry points write reports or derived files. The API should not accept filesystem paths from clients and should bind locally by default; authentication and deployment exposure need a separate decision.

## 5. Proposed React architecture

Keep the current Streamlit app available while adding an isolated Vite project under `frontend/`:

```text
frontend/
  src/
    app/                 router, query client, route guards
    api/                 typed fetch client and response schemas
    components/          cards, badges, tables, charts, loading/error states
    layout/               ScoutShell, desktop sidebar, mobile navigation
    features/
      overview/
      recommendations/
      batters/
      players/
      comparison/
      bowling/
      auction/
      evidence/
    styles/               Tailwind entry, tokens, responsive rules
    test/                 component and API contract tests
  package.json
  vite.config.ts
  tailwind.config.ts
  tsconfig.json
```

Use React and TypeScript with Vite, Tailwind CSS, Framer Motion, and Recharts. A shared shell should provide a premium deep-navy canvas, restrained pink/blue accents, accessible contrast, stable typography, and desktop/tablet/mobile navigation. Use Framer Motion only for short transitions; respect reduced-motion preferences. Recharts should visualize API-provided values, not derive new scores.

Reusable view components: `ScoutShell`, `DesktopSidebar`, `MobileNav`, `MetricCard`, `PlayerRankingTable`, `PlayerCard`, `PlayerProfilePanel`, `EvidencePair`, `ExposureBadge`, `AvailabilityBadge`, `BowlingEvidenceNotice`, `ComparisonTable`, and shared loading/empty/error states. Feature routes can map to Executive Overview, Final Player Recommendations, Batter Scouting, Bowler Scouting, Player Comparison, RR Squad Fit, Methodology & Evidence, and RR Auction Targets. Use an explicit not-available state for evidence that the backend does not contain.

## 6. Recommended read-only API endpoints

| Endpoint | Source and response intent |
|---|---|
| `GET /api/v1/health` | Service version, artifact snapshot date, and readiness only. |
| `GET /api/v1/overview` | Confirmed-scope match/delivery counts, eligible batter count, bowling readiness counts, and source snapshot metadata. |
| `GET /api/v1/rankings/batters/overall` | Read `submission/phase5g_overall_batter_top10.csv` in stored rank order; return the original ID, score, formats, evidence and limitations. |
| `GET /api/v1/rankings/batters?format=IPL` | Read existing Phase 5C rows or the corresponding supporting artifact; filter to the requested allowed format without rescoring. |
| `GET /api/v1/players?query=&format=&role=` | Search only whitelisted profile/exposure rows with bounded pagination. |
| `GET /api/v1/players/{player_id}/profiles?format=` | Return existing descriptive profile, exposure and eligibility evidence; preserve cohort and format labels. |
| `GET /api/v1/players/compare?ids=...` | Read-only comparison of a bounded list of player IDs from stored profiles. Use a bounded ID list; this is a read-only query. |
| `GET /api/v1/bowling/evidence` | Read readiness counts, metric audit and eligibility evidence; explicitly state no validated bowler ranking. |
| `GET /api/v1/auction/availability?status=&role=` | Read the dated availability overlay and source records. |
| `GET /api/v1/auction/targets` | Return only performance-eligible batters whose status is `officially_registered_for_auction` or `included_in_final_auction_register`; keep all others in separate status groups. This is status filtering, not score calculation. |
| `GET /api/v1/methodology` | Curated definitions and limits from the current approved methodology artifacts. |
| `GET /api/v1/data-quality` | Scope, inventory, field-quality evidence, and data snapshot metadata. |

Define Pydantic response models and publish an OpenAPI schema before frontend integration. Serialize player IDs as strings to preserve identity; represent missing/unavailable values as JSON `null`, never zero. Include source artifact, `as_of`/verification date, and limitations in responses. Preserve order explicitly and return a versioned contract. The comparison endpoint should not synthesize a common score across formats or unsupported metrics.

## 7. Validation baseline

Commands run without writing project files:

- In-memory compilation of Python files in `src/`, `dashboard/`, and `tests/`: **67 compiled successfully**.
- `python -B -m pytest -q tests -p no:cacheprovider --basetemp=<system-temp>/superrr_frontend_migration_audit_20261113`: **113 passed**, no failures, in 1.81 seconds.
- `src.phase5h_final_audit.verify_overall_batters()`: passed; exact Phase 5G order reproduced and maximum score difference 0.0.

Authoritative overall Batter Top 10 at audit time:

| Rank | Player ID | Player |
|---:|---:|---|
| 1 | 25534 | Chad Bowes |
| 2 | 25669 | Priyansh Arya |
| 3 | 3282 | Mehidy Hasan Miraz |
| 4 | 6574 | Alick Athanaze |
| 5 | 27469 | Aryansh Sharma |
| 6 | 167 | Ajinkya Rahane |
| 7 | 6819 | Yashasvi Jaiswal |
| 8 | 24887 | Innocent Kaia |
| 9 | 6272 | William Jacks |
| 10 | 3635 | Jason Smith |

Bowling baseline from `outputs/reports/phase5c_bowler_rankings.csv`: 414 profiles; 0 competition-ready; 414 exploratory. No test or compile warnings were reported in this run. The project also contains historical audit reports; the frontend should use current Phase 5G/5H artifacts rather than treating superseded Phase 5F reports as current submission truth.

## 8. Migration risks and decisions

1. **Availability artifact packaging:** `.gitignore` excludes `data/external/*`, including the current IPL 2027 overlay. Decide how a deployment receives this dated, auditable artifact: a governed release artifact, a controlled generation step, or a narrowly scoped ignore exception. Do not silently omit it or expose it publicly.
2. **Local proprietary data:** raw/processed files are local and should not be copied into the browser bundle, public static assets, or API responses. Decide API hosting, access control, and permitted network boundary before deployment.
3. **Artifact versioning and staleness:** CSV schemas and snapshot dates are not formal API contracts. Add schema/version and freshness checks in the adapter; do not refresh availability from rumors or request-time scraping.
4. **Numerical/null semantics:** CSV blanks, booleans, IDs, and mixed status values need explicit conversion. Preserve IDs as strings and missing values as null. Do not coerce missing bowling metrics to zero.
5. **Ranking drift:** sorting on scores in React, recomputing percentiles, or comparing raw IPL/T20I scores can change the official list. Render stored rank order and add contract tests against the Phase 5G file.
6. **Pressure interpretation:** the validated batter ranking uses a contextual wicket/phase proxy, not proof of psychological pressure. Preserve the precise caveat in labels and profiles.
7. **Bowling standard:** no competition-ready bowling candidates exist; an exploratory order must never become a recommendation through UI sorting.
8. **Read/write coupling:** some Python `main()` functions write outputs or package files. API handlers must use pure read functions or read-only artifact loaders, not those entry points.
9. **Static presentation assets:** current package includes SVG charts; decide whether to serve these as static assets or re-render from API evidence. Do not regenerate analytical values in the browser.
10. **Responsive/accessibility assurance:** App/API tests do not validate actual viewport rendering. Plan browser-based checks at desktop, tablet, and mobile widths, keyboard navigation, and reduced-motion behavior.

## 9. Recommended implementation sequence

1. Freeze and record the current artifact snapshot; retain Streamlit as the working fallback.
2. Agree on the API schema, access boundary, availability artifact packaging, and refresh ownership.
3. Add a separate read-only FastAPI adapter that loads only approved artifacts through project-root-relative paths. Do not alter analytical modules or score calculations.
4. Add API contract tests for schemas, null handling, status filters, source dates, and access restrictions. Assert `/rankings/batters/overall` matches the package CSV by rank, ID, and score.
5. Bootstrap `frontend/` with Vite, React, TypeScript, Tailwind, Framer Motion, and Recharts; keep its dependency lock/config isolated from Python.
6. Build the responsive shell and data states, then migrate Overview and the frozen recommendations list first.
7. Add player profiles/discovery/comparison using API-returned records; preserve format/cohort distinctions and all limitations.
8. Add bowling evidence and auction status views with explicit empty/unconfirmed states; gate auction targets on verified registration/final-register statuses.
9. Add methodology/data quality, then run API, frontend, responsive-browser, and ranking-parity checks.
10. Run Streamlit and React side-by-side through acceptance. Switch the entry URL only after parity review; retain Streamlit as the rollback path until the new frontend is accepted.

## 10. Preservation confirmation

This audit created only `docs/frontend_migration_audit.md` (and the required `docs/` directory). Existing analytics code, rankings, raw/processed datasets, availability data, Streamlit files, reports, submission files, configuration, and dependencies were not modified. No packages were installed, no rankings were generated, and no API or React application was created.

