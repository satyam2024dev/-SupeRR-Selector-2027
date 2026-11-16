# Phase 1 — Verified External Cricket Data Integration Audit

**Project:** SupeRR Selector Season 2  
**Audit date / research cut-off:** 14 November 2026  
**Status:** Architecture and source assessment only. No external data was downloaded, refreshed, merged, or accepted during this audit. No application, analytics, dataset, ranking, overlay, or report files were changed.

## Executive summary

Cricsheet JSON is a practical primary candidate for an independently stored ball-by-ball evidence layer: it documents structured match events, typed extras, outcomes, registry identifiers, and an ODC-BY 1.0 licensing model. Its published coverage is substantial, but coverage counts are dynamic and do not establish availability or completeness for any particular match. Official IPL publications are the appropriate authority for official IPL announcements, including franchise transactions and any published auction registration/list. Secondary distributors are useful only when their provenance is clear; a repackaged Cricsheet record is not independent corroboration.

The project already contains a historical, isolated Cricsheet pilot under `data/external/cricsheet/pilot/`. It has four JSON controls, registers and provenance records. Existing reports say the four controls were not accepted; a later reconciliation diagnosis records 0 accepted, 1 rejected, and 19 unresolved match decisions. The 16 local no-delivery candidates remain unresolved against the archive index and are locally recorded as abandoned. This audit did not run a downloader or alter pilot files. The processed `accepted_external_deliveries.csv.gz` scaffold has zero rows. These are pilot findings, not permission to integrate data.

**Recommendation:** Treat Cricsheet as an optional, namespaced evidence source in a new external-data boundary. First approve licensing, scope, identity review ownership, and acceptance policy; then implement a read-only, manifest-led isolated pilot. Keep every existing Phase 5 result and API route as-is. Do not use external values in rankings, eligibility, auction status, or methodology without a separate future review and explicit change control.

## 1. Existing architecture and data findings

### 1.1 Repository and pipeline

The project is a local Python analytics repository with a Streamlit dashboard, a separate React + TypeScript frontend, and a local FastAPI read-only adapter. The main areas are `data/raw/`, `data/processed/`, `data/external/`, `src/`, `api/`, `dashboard/`, `frontend/`, `tests/`, `outputs/reports/`, and `submission/`.

The Python pipeline loads project CSVs through `src/config.py` and `src/data_loader.py`; source validation and conservative event-state work are in `src/cricket_data_validation.py`, `src/match_state.py`, and `src/phase2b_pipeline.py`. Phase 5 analytics and frozen evidence live in `src/phase5a_analysis.py` through `src/phase5h_final_audit.py` and preserved output/submission artifacts. These are out of scope for this integration. `src/cricsheet_pilot.py`, `src/cricsheet_offline_audit.py`, and `src/identity_crosswalk_research.py` already contain research/pilot functionality; the pilot module includes network retrieval capability and must not be invoked as part of this documentation-only phase.

`api/app.py` is a flat FastAPI application. It exposes a read-only set of existing artifact-backed endpoints, restricts CORS to local frontend origins, and does not accept client paths. `frontend/src/App.tsx` wires the current application pages to `frontend/src/api/`; the current routes and ranking source of truth must remain unchanged. New external routes and UI are a proposal only.

### 1.2 Local schemas and coverage

Inspection of the existing source tables found:

| Artifact | Observed fields relevant to a future boundary | Current observation |
|---|---|---|
| `data/raw/ball_by_ball.csv` | `match_id`, innings/over/ball coordinates, striker/non-striker/bowler IDs and names, `runs`, wicket/dismissal fields, locally defined extras fields | 200,999 rows; 867 distinct match IDs. Local event semantics are not equivalent to Cricsheet fields by assumption. |
| `data/raw/matches.csv` | `match_id`, `comp_id`, `match_date`, team IDs/names, opaque `venue_id`, revised overs/target, result | 883 rows; local dates 2022-01-22 through 2026-11-01. |
| `data/raw/competitions.csv` | `comp_id`, competition name, match format, season | IPL and T20I are represented among other competition records. |
| `data/raw/teams.csv` | local team IDs and names | Local identifiers remain in their own namespace. |
| `data/raw/playing_eleven.csv` | match/team/player IDs and player names | Match-scoped roster evidence; not a global identity key. |
| `data/raw/competition_team_player_mapping.csv` | competition/team/player IDs and names | 1,217 distinct local player IDs and 1,210 distinct names in the inspected inventory; several names associate with multiple local IDs. |
| `data/processed/accepted_external_deliveries.csv.gz` | external/local match coordinates, event values, source and hash fields, acceptance state | Zero rows; a schema scaffold, not accepted external data. |

Local inventory identified 371 IPL match rows (seasons 2022–2026), of which 367 have delivery rows; 482 T20I rows, of which 470 have delivery rows. There are also 30 non-IPL T20 matches. These counts describe the current local tables, not expected external coverage. Local T20I season labels include calendar and split-season forms; normalize only in an external reporting layer while retaining the supplied competition and season labels. Do not infer that an external match is equivalent from the local integer match ID.

The existing processed match-state and pressure research files are local derived evidence. Their uncertainty rules and meanings are not changed by this plan. In particular, contextual wicket/phase evidence must not be relabeled as verified scoreboard pressure merely because an external event feed exists.

### 1.3 Existing Cricsheet pilot and boundary

The existing pilot files are under `data/external/cricsheet/pilot/`, including `matches/`, `register/`, selection/download manifests, checksums and `ATTRIBUTION.txt`. Four downloaded control JSONs and people/venue registers were previously recorded with ODC-BY attribution and retrieval provenance. Do not relocate or overwrite them as part of a future implementation without a separate migration decision.

`outputs/reports/cricsheet_pilot_report.md` records 20 selected fixtures, 0 accepted, and 20 unresolved in that report version; four controls were partial and 16 candidates unresolved. `outputs/reports/cricsheet_reconciliation_diagnosis.md` is a later diagnostic of the evidence: 0 accepted, 1 rejected, 19 unresolved; 965 aligned delivery rows, 961 partial and 4 mismatched in that diagnostic version. The version difference should be preserved with report timestamps and not collapsed into one result. The diagnosis identifies unresolved player/venue namespaces and missing independent totals/bowling validation; it notes the retired-hurt semantics and extras-category mismatches requiring adjudication. `outputs/reports/identity_crosswalk_report.md` labels name-based candidates conservatively and records ambiguous names. None of these reports establishes an accepted production join.

The local 16-match no-delivery cohort is recorded as `Match Abandoned`; no candidate in the examined Cricsheet metadata index was found in that prior pilot, and the report explicitly leaves archive absence unresolved. No delivery recovery is demonstrated. The evidence supports neither asserting that Cricsheet has the 16 records nor treating them as recoverable innings.

## 2. Source assessment

### 2.1 Cricsheet (primary external candidate)

Cricsheet publishes JSON as its main format, with match data divided by competition and format. As checked 14 November 2026, its download/coverage pages listed 1,243 IPL matches (shown as 100% in the coverage table) and 5,849 T20 internationals overall, including 3,649 men’s and 2,200 women’s records; the downloads page also notes withheld matches. Counts and coverage can change. The published IPL percentage is coverage against Cricsheet’s own stated competition inventory, not proof that a project’s selected seasons, abandoned fixtures, or local feed overlap are complete. T20I records must be explicitly scoped to men’s T20I if that is the intended comparison; do not use an all-gender count as a men’s denominator. See [Cricsheet downloads](https://cricsheet.org/downloads/) and [coverage](https://cricsheet.org/coverage/).

Cricsheet’s JSON documentation currently identifies schema version 1.3.0. The documented model includes match `info`, dates, teams, season/event/venue and outcome metadata, a registry mapping match names to provider identifiers, innings and overs, and delivery events. Events represent batter, bowler, non-striker, runs split between batter/extras/total, typed extras, wickets and their dismissal kinds, and optional replacement/review/target information. The registry IDs are Cricsheet identifiers; selected third-party identifiers may be present but are not guaranteed. `actual_delivery` can repeat after a wide or no-ball, so it is not a unique event sequence number. The wicket array may contain multiple entries, including a retirement event; an event record must not be equated blindly to a team wicket lost or a bowler credit. Schema/version and edge cases must be retained. See [JSON format](https://cricsheet.org/format/json/) and [Cricsheet register](https://cricsheet.org/register/).

Cricsheet explains that some data is unavailable because a competition/period is outside coverage, ball-by-ball records could not be obtained, or a source was considered incorrect and unresolved. Its missing-data listing is not a universal guarantee that a match is absent. A missing archive match is not evidence that no match occurred. Record observed gaps without guessing their cause. See [matches not covered](https://cricsheet.org/missing/) and [coverage notes](https://cricsheet.org/coverage/).

Cricsheet JSON/register content is licensed under Open Data Commons Attribution License 1.0 (ODC-BY 1.0), subject to the full license and the source’s notices. Redistribution/adaptation requires appropriate attribution and license/notice handling. Every acquired file should carry its provider URL, archive/member, retrieval timestamp, SHA-256, schema version, license identifier, required attribution text, and any transformation lineage. Include attribution with any distributed derived database. The separate XML format has a different license; do not switch formats without a fresh review. See [Cricsheet licensing](https://cricsheet.org/licensing/).

### 2.2 Official IPL sources

Use the official [IPL site](https://www.iplt20.com/) and its [news and announcements](https://www.iplt20.com/news) as the authority for official IPL match information and published franchise/league announcements: retention, release, trade, auction registration/list, or final auction results when actually published. Preserve the exact official page/document URL, publication date and verification date. A general news index or a previous-season document is not evidence for a 2027 player’s registration or status. A trade/release announcement alone does not prove auction availability. A franchise’s stated intention is not an official final auction register. If the relevant official record is absent, label the fact unknown/unverified.

Use official IPL match reports/scorecards as match validation evidence where they expose the required field. The official site is not assumed to provide a licensed, complete, bulk event feed. Its [terms](https://www.iplt20.com/terms-and-conditions) govern reuse of site content; store only the facts and links needed for audit, avoid copying protected prose, logos or photographs, and obtain separate rights review before redistribution or scraping.

### 2.3 Secondary sources

Secondary scorecard providers may help discover fixtures or check a specific fact, but they count as independent evidence only when their data lineage is demonstrably independent. A distributor that republishes Cricsheet is the same underlying evidence, not a second source. Record provider, original source, reuse/license terms, retrieval date and the specific field used. Prefer official IPL/BCCI record for IPL official outcomes where available. Do not scrape sites whose terms or reuse rights do not permit it.

## 3. Schema compatibility and preservation boundary

Keep three event representations separate: (1) immutable provider file as acquired, (2) a versioned normalized external schema that preserves source values and event ordering, and (3) an explicit match acceptance/crosswalk layer. Never overwrite local `ball_by_ball.csv` or `matches.csv`; never backfill missing values into them. Retain unknown/missing as unknown, not zero. Do not convert provider labels into local categories unless an approved mapping is versioned and reversible.

Recommended normalized delivery fields include `provider`, `provider_match_id` (string and namespaced), `provider_schema_version`, `innings_number`, `over_index`, `source_delivery_index` (stable array order), `actual_delivery_label`, provider batter/bowler/non-striker IDs and source names, `runs_batter`, `runs_extras`, `runs_total`, typed extras as structured data, wicket events as structured data, `legal_ball_status` with derivation/version, source file/hash, and acceptance state. Match-level data should preserve source dates, competition, teams, venue, outcome, targets/revisions, super-over/forfeiture/missing flags and source metadata. Keep provider records that fail checks in quarantine; never silently “repair” them.

Local fields are not a direct schema match. Local `match_id`, `player_id`, team IDs and venue IDs have undocumented/different namespaces; local `runs` is not safely assumed to mean Cricsheet `runs.total`; local extras categories and legal-ball status have known uncertainties; local match rows do not consistently offer independent innings totals or bowling figures. Only compare fields with a documented semantic crosswalk. The old pilot’s 965 delivery-coordinate alignments did not pass the overall acceptance gate, and must not be presented as fully verified external records.

## 4. Player and match identity reconciliation

### Player IDs

Keep at least these namespaces distinct: local project `player_id`; Cricsheet registry ID; and any optional third-party ID carried by Cricsheet. Never join two bare numeric/string identifiers unless both namespaces are documented and the exact provider field is confirmed. An exact external-ID match can be used only against a separately verified local crosswalk with proven namespace and evidence; current project fields do not establish that link.

Name matching is candidate generation, not identity proof. Normalize Unicode and whitespace/case conservatively for candidate search, while preserving source spelling. Do not strip meaningful tokens or use fuzzy similarity as an automatic join. Resolve candidates using match-specific roster, team, competition and date evidence plus an authoritative identifier or human review. Initials, surname-only matches, aliases and spelling similarity stay pending until reviewed. Duplicate display names, multiple external IDs, conflicting teams/roles, or many-to-one/many-to-many mappings are `ambiguous` and block merge. Unmatched entities stay unmatched; do not invent IDs or biographies.

Maintain a separate, access-controlled crosswalk table with fields such as `local_player_id`, `provider`, `external_player_id`, source names, evidence references, match/context count, status (`proposed`, `reviewed`, `accepted`, `rejected`, `ambiguous`, `unmatched`), reviewer, reviewed timestamp and crosswalk version. Require an auditable reviewer and evidence for `accepted`; prohibit silent automatic promotion. Existing research found candidate and ambiguous cases (including repeated surname candidates and duplicate Cricsheet display names), reinforcing the need for manual review.

### Match and venue IDs

Keep `local_match_id` and provider match ID as separate keys. Match candidates should require exact date (with explicit timezone/date convention), both teams after reviewed team aliases, competition/format and compatible event metadata; venue and official scorecard are corroborators. If there is a double-header/date ambiguity, team alias conflict, abandoned/rescheduled fixture, Super Over ambiguity, or conflicting event, mark ambiguous and do not merge. Store the crosswalk and evidence separately. Local venue IDs are opaque; create no venue join until a local venue name/namespace or independently verified match-level evidence exists.

## 5. Proposed separate directory structure

Adapt the proposal to the existing repository without relocating the historical pilot:

```text
data/external_cricket/
  raw/cricsheet/{ipl,t20i}/              # immutable provider archives/members
  raw/official_ipl/                      # only permitted source extracts/references
  processed/cricsheet-json-v1/           # versioned normalized external records
  quarantine/                            # failed/ambiguous records with reasons
  manifests/                             # run, coverage, checksums, schema versions
  provenance/                            # source/license notices and crosswalks

src/external_cricket/
  __init__.py
  ingestion.py                           # controlled, explicit acquisition only
  validation.py                          # schema and semantic validation
  identity.py                             # candidate generation and review gates
  statistics.py                           # external-only descriptive derivations

api/routes/external_cricket.py            # independent read-only router (future)
docs/external_data_architecture.md        # after separate implementation approval
docs/external_data_dictionary.md
docs/external_data_licensing.md
```

This is a proposal, not a request to create these implementation files now. The existing historical pilot at `data/external/cricsheet/pilot/` remains untouched. During a later implementation, decide whether to harden and reuse `src/cricsheet_pilot.py` or create a clean package; avoid operating two competing downloaders. Keep manifests and provenance even when a match is rejected. Do not put raw external records in `data/raw/` or `data/processed/`.

## 6. API and UI design

### Independent read-only endpoints

Add a separate external router/prefix, for example `/api/v1/external-cricket`, only after implementation approval. It must not change existing ranking paths, models, source files or response semantics. All IDs in responses should be explicitly namespaced strings. Use typed response models and bounded filters/pagination; do not accept filesystem paths or client-provided source URLs. Never expose raw local proprietary datasets or crosswalk review notes publicly.

Proposed endpoints:

| Endpoint | Purpose and constraints |
|---|---|
| `GET /matches` | Filter accepted external fixtures by competition, season, date window and team; paginated, with source completeness indicator. |
| `GET /matches/{provider}/{match_id}` | Match metadata and accepted event summary, including provenance and warnings. |
| `GET /players` | Search only records with accepted external identity; unresolved names do not become local player profiles. |
| `GET /players/{provider}/{player_id}/evidence` | Source-attributed player events/derived evidence and explicit date window/coverage count. |
| `GET /trends` | Descriptive external-only aggregates with metric definition, sample size, seasons, match IDs and source-run version. No ranking or eligibility output. |
| `GET /provenance/sources` and `/provenance/runs/{run_id}` | Provider, license, source file hashes, retrieval/schema versions, validation and acceptance summaries. |
| `GET /quality` | Coverage gaps, quarantine totals and freshness timestamps, without claiming missing records are absent from the real world. |

Return 404 for unknown namespaced IDs, 422 for invalid filters, and a clear unavailable/error response when no accepted fixture/artifact exists. Never silently fall back to current project rankings. Keep the adapter read-only, loopback-bound, with local-only CORS and no write/delete route. Add tests for those boundaries before exposing routes.

### Separate UI areas

1. **External Match Centre:** search/filter external match records; show match ID namespace, date, competition, source status, coverage and match provenance.
2. **Player Evidence Profiles:** provider identity and reviewed crosswalk status; show only accepted identity links, explicit source scope and sample count. Keep an unlinked external profile distinct from an existing local player profile.
3. **Performance Trends:** descriptive, external-only time series with date window, included matches and caveats; do not sort into a new ranking or blend with Phase 5.
4. **Data Provenance Centre:** source/license/citation, version, retrieval date, file hashes, missing coverage, quarantine and validation states.

The current seven sections remain behaviorally unchanged. External surfaces must visually label external evidence and acceptance state, and must not feed Batter Rankings, Bowling Intelligence recommendations, RR Auction Targets or the frozen PDF. No auction status, availability, role or price is inferred from performance data.

## 7. Data quality and traceability design

Each acquisition run should have a unique run ID and record provider, source URL/archive member, UTC retrieval time, SHA-256, license and attribution, JSON/schema version, code version, expected/observed match count, validation summary and accepted/quarantined/rejected counts. Every derived statistic must resolve to source file hashes, accepted match IDs, exact date window, rule/version, and source fields. Store coverage manifests by competition/season and distinguish “not in this source snapshot” from “match did not occur.”

| Check | Proposed rule / handling |
|---|---|
| Duplicate matches | Enforce unique `(provider, provider_match_id, source_version)`; detect duplicate fixture candidates separately; quarantine conflicting versions rather than overwrite. |
| Missing identifiers | Validate required match and participant names/IDs against schema and match registry. Preserve explicit nulls; quarantine records that cannot support the requested statistic. |
| Delivery ordering | Preserve innings/over array order and assign stable source delivery index. Validate over/label formats; repeated `actual_delivery` labels after wides/no-balls are allowed and must not be deduplicated. |
| Negative runs/components | Reject/quarantine invalid negative delivery components unless explicitly documented schema semantics allow them. Validate integer types and `runs.batter + runs.extras == runs.total`; validate typed extras sum against `runs.extras`, with exceptions retained for review, never auto-corrected. |
| Unknown extras | Preserve unknown keys and schema version; mark unsupported and quarantine derived metrics that depend on interpretation. Do not treat absent as zero unless schema says absent means no such extra. |
| Wicket events | Validate kinds against schema version; retain unknown kinds for review. Model event occurrence separately from wicket lost and bowler credit. Treat retired hurt and multiple wicket-array entries as special cases, not generic dismissals. |
| Legal balls | Derive only from versioned cricket rules and documented typed extras (e.g. wides/no-balls), with edge-case validation. Do not use repeated `actual_delivery` as a count or infer ambiguous local legality. |
| Innings/result | Recompute event totals only for accepted complete innings; account for penalty runs, forfeits, DLS/revised targets, innings termination, ties and Super Overs. Compare with official scorecard where available; quarantine unexplained inconsistencies. |
| Missing seasons/fixtures | Compare snapshot against dated provider coverage and explicit expected competition calendar. Flag gaps; absence from a download is not proof of no match or no data. |
| Freshness | Record retrieved and source-publication dates; publish a “checked as of” date. Do not imply real-time coverage. Require a deliberate scheduled/manual refresh and checksum change audit. |
| Completeness | Report match/innings/event/roster coverage, missing flags, score reconciliation, legal-ball confidence and accepted share. Metric responses include included match count and date window. |
| Traceability | Each statistic carries provider, source/run ID, source hashes, match IDs, date bounds, rule version, accepted crosswalk version and validation state. |

Validation separates **schema validity**, **event consistency**, **fixture identity**, **scorecard corroboration**, and **identity acceptance**. Passing one layer does not imply the others passed. Unexplained differences remain quarantined; do not loosen acceptance thresholds to increase coverage.

## 8. Data privacy and operational safeguards

Keep downloaded records local and read-only after acquisition; never upload proprietary raw tables, player mapping tables, API payloads or report artifacts to external services. Public-source player names/IDs remain subject to source terms; local crosswalks reveal the project’s proprietary ID relationships and should be access-controlled and excluded from public responses. Do not store credentials or secrets in manifests. Log run IDs and status, not unnecessary player-search text. Limit API file access to a fixed allowlist, use no client path parameters, bind only to loopback for local use, and restrict CORS to the local frontend. No public deployment is proposed.

## 9. Implementation phases and gates

1. **Phase 1 — Audit (this document):** source/schema/privacy assessment and separate architecture. No integration performed.
2. **Phase 2 — Governance:** approve competition/season scope, redistribution and attribution, refresh cadence, reviewer, accepted-match criteria, and public/private distribution. Verify official IPL page terms for planned use.
3. **Phase 3 — Isolated acquisition:** add explicit operator-run download for selected Cricsheet records to `data/external_cricket/raw/`; immutable checksums and manifests; no local joins, no automated background refresh.
4. **Phase 4 — Validation/quarantine:** schema and semantic checks; produce coverage and discrepancy reports; retain all rejected/unresolved states; no statistics exposed yet.
5. **Phase 5 — Identity review:** candidate match/player crosswalks in a separate review workflow. Human evidence review and approval; ambiguous/unmatched stays blocked. Establish crosswalk version.
6. **Phase 6 — External-only measures:** compute descriptive evidence solely from accepted external matches. Independent scorecard checks and reproducibility audit. Do not modify existing analytics.
7. **Phase 7 — Read-only API and separate UI:** add new router and sections behind explicit external source labels; regression-test that old endpoints and pages remain byte/behaviorally unchanged where practical.
8. **Phase 8 — Re-evaluation gate:** report coverage, limitations, licensing and quality to project owner. Any proposed use in existing rankings, eligibility, PDF, auction logic or methodology requires a separate explicit phase and approval; it is not implied by this plan.

## 10. Risks and unresolved questions

| Risk/question | Required decision or mitigation |
|---|---|
| Cricsheet coverage and freshness can change; published counts do not prove project overlap. | Choose exact seasons and capture snapshot coverage/manifests at each run. |
| Prior pilot has unresolved identity, venue, extras and scorecard issues. | Reuse prior evidence as a blocker list, not as accepted data; independently review every proposed acceptance. |
| Local player ID namespace is undocumented; aliases and duplicate names exist. | Identify the local feed’s ID provider/documentation or require audited manual crosswalks. Never join by integer/name alone. |
| Local match/venue identifiers are opaque and local scores incomplete. | Authoritative match identity and independent scorecard evidence are needed; preserve unmatched state. |
| Secondary feeds may redistribute Cricsheet. | Document data lineage before claiming independent corroboration. |
| License and website terms differ by source/format. | Legal/owner review before redistribution, scraping, or use of protected material; maintain required attribution. |
| Official IPL 2027 registrations/auction outcomes may not yet be published at a given snapshot. | Record unknown/unverified, point to official source checked, and never derive auction availability from trades/releases alone. |
| External evidence could be mistaken for existing rankings or pressure validation. | Separate route, UI labels, namespaces and storage; no ranking endpoint edits or implicit join. |
| Scope and deployment are undecided. | Confirm men’s-only vs wider coverage, API audience, authentication and allowed redistribution before implementation. |

Questions to settle before Phase 2: (a) Which seasons and match formats are in scope? (b) Is this strictly local/operator use or will derived data be distributed? (c) Who can approve player identity links? (d) What constitutes sufficient independent scorecard evidence? (e) What refresh cadence and snapshot policy are required? (f) Is there any future intention to use external records in current methodology, which would require a new separately reviewed change?

## 11. Files inspected

The audit reviewed the following project files and artifacts (among supporting source and tests):

- **Project overview:** `README.md`, `docs/frontend_migration_audit.md`, `docs/final_application_audit.md`, `docs/ipl_2027_pdf_readiness.md`, `docs/ipl_2027_report_final_qa.md`, `docs/final_project_completion_report.md`.
- **Local schemas/data inventory:** `data/raw/ball_by_ball.csv`, `matches.csv`, `competitions.csv`, `teams.csv`, `playing_eleven.csv`, `competition_team_player_mapping.csv`; `data/processed/accepted_external_deliveries.csv.gz` and current match-state/pressure artifacts.
- **Pipeline and pilot:** `src/config.py`, `src/data_loader.py`, `src/cricket_data_validation.py`, `src/match_state.py`, `src/phase2b_pipeline.py`, Phase 5A–5H analysis/audit modules, `src/cricsheet_pilot.py`, `src/cricsheet_offline_audit.py`, `src/identity_crosswalk_research.py`, `src/external_data_feasibility.py`, `src/match_acceptance.py`.
- **External pilot/provenance:** `data/external/cricsheet/pilot/` manifests, attribution, selected JSON/register files; `outputs/reports/external_data_feasibility.md`, `cricsheet_pilot_report.md`, `cricsheet_pilot_progress.md`, `cricsheet_reconciliation_diagnosis.md`, `cricsheet_comparator_correction.md`, `identity_crosswalk_report.md`, and associated crosswalk/reconciliation outputs.
- **Application and validation:** `api/app.py`, `api/tests/test_api.py`, `frontend/src/App.tsx`, `frontend/src/api/`, `frontend/src/pages/`, `tests/` and `frontend` test/build configuration.
- **Current auction/preservation controls:** `data/external/ipl_2027_player_availability.csv`, relevant availability documentation and `submission/` Phase 5G/5H artifacts.

External source pages were checked on 14 November 2026. Dynamic coverage numbers above are dated observations, not permanent guarantees.

## 12. Recommended next step

Approve a bounded Phase 2 governance specification (competition/season scope, license/distribution posture, reviewer, source snapshot policy, and exact acceptance gate). Then build an isolated, manifest-first dry-run against already-present pilot evidence before any new acquisition. Keep existing raw/processed data, Phase 5 analytics, ranking API, React behavior, auction overlay, validated PDF, and methodology definitions untouched throughout.

## 13. Regression checks run for this audit

The audit changed documentation only. Existing test suites passed:

| Suite | Command (from indicated directory) | Result |
|---|---|---|
| Project Python | Project root: ` .\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider ` | 113 passed |
| API | Project root: ` .\api\.venv\Scripts\python.exe -m pytest -q api\tests -p no:cacheprovider ` | 14 passed |
| Frontend | `frontend/`: `npm.cmd test -- --run` | 11 passed across 3 test files |

No external-data downloader, ingestion command, integration test, or data-generating script was run. No external data was fetched during this audit.
