# External Cricket Data — Acceptance-Gate Approval Draft

**Project:** SupeRR Selector Season 2  
**Status:** **DRAFT — ALL GATES PENDING PROJECT-OWNER APPROVAL**  
**Overall decision:** **NO-GO for external data acquisition, download, ingestion, and integration.**  
**Basis:** Exact gate wording below is transcribed from Section 4 of `docs/external_data_governance_decision.md`. Related control wording is identified where drawn from the audit or other governance records.

## 1. Purpose and status

This draft turns each of the eleven Section 4 acceptance gates into a reviewable pass/fail proposal with a test method, evidence artifact, and failure response. It does not approve a gate, grant rights clearance, authorize implementation, or permit external data acquisition. Every gate’s owner-approval status is **PENDING**.

“Original requirement” entries are quoted verbatim from the named governance document. Proposed pass conditions restate how a future test could demonstrate that requirement. Any new numerical threshold or interpretation not stated in the original is explicitly marked **PROPOSED** and requires owner approval. No existing threshold is weakened.

## 2. Gate approval matrix

### Gate 1 — Source licensing and attribution

**Exact original requirement (Section 4, Source and license):**

> 100% of accepted files have provider, canonical source URL/member, retrieval timestamp, applicable license/terms, required attribution, schema/version, transformation lineage and SHA-256 recorded. Zero accepted records with unresolved rights or attribution.

**Proposed measurable pass condition:** Every accepted file has all nine listed provenance/license fields populated and evidence-linked; all intended source rights and attribution obligations have documented review decisions; zero accepted files have unresolved rights or attribution. For Cricsheet, confirm exact file/register format and applicable license before use. For IPL or any secondary source, rights review must be separately completed. No extra numeric threshold is introduced.

**How tested:** Automated manifest completeness and hash verification, plus documented human review of the exact current license/terms and intended acts (acquisition, local storage, transformation, API/UI use). The human review must not be represented as legal clearance unless an authorized legal determination exists.

**Evidence/artifact required:** Immutable source manifest; file checksum report; license/terms URLs and versions; dated review record; required attribution/notices; reviewer and decision; transformation lineage.

**Failure action:** Block acceptance and quarantine the source/file. No download or use until the project owner’s pending source-rights reviews are closed.

**Owner approval status:** **PENDING**.

### Gate 2 — Snapshot, match-ID uniqueness and collision handling

**Exact original requirement (Section 4, Snapshot integrity):**

> 100% of acquired files pass checksum verification after storage; source snapshot is immutable; every changed, added or removed file is represented in a run diff. Duplicate `(provider, provider_match_id, source_version)` count is zero in accepted data.

**Proposed measurable pass condition:** All acquired files verify against recorded SHA-256; prior snapshots cannot be overwritten; all changes appear in a run diff; zero duplicate provider match keys occur in accepted data. Local and external IDs remain namespaced. Candidate fixture collisions (including multiple provider records for one local fixture, or one provider ID mapping to multiple local fixtures) are explicitly detected and marked ambiguous; zero unresolved collisions may enter accepted data.

**How tested:** Hash all manifest members after storage; compare each run manifest to its predecessor; enforce a unique database/table key on `(provider, provider_match_id, source_version)`; run fixture-crosswalk collision checks in both directions; test same-ID/different-version and same-fixture/multiple-provider-ID cases with synthetic fixtures. Duplicate-check coverage must include accepted and quarantined records so collisions are visible, not silently filtered.

**Evidence/artifact required:** Immutable per-run manifest, checksums, run diff, uniqueness/collision report, and versioned match crosswalk with status/reason for each collision.

**Failure action:** Reject or quarantine conflicting records and stop the affected match from acceptance. Preserve prior snapshots and report the collision; never resolve it by overwriting or guessing.

**Owner approval status:** **PENDING**.

**Threshold note:** The original explicitly sets zero duplicate provider match keys in accepted data. It gives no standalone numerical rate for collision detection coverage; the proposed test coverage and bidirectional crosswalk checks are **PROPOSED** operational interpretation, not existing policy.

### Gate 3 — Schema, types and event quality

**Exact original requirement (Section 4, Schema and event quality):**

> 100% of accepted files parse against the declared provider schema version. Zero unexplained negative run values, run-component equation failures, invalid delivery sequence collisions, or unknown event types used in derived statistics. Unsupported/unknown values remain explicit and are excluded from dependent metrics.

**Proposed measurable pass condition:** Every accepted source file parses against its declared provider schema/version; all documented required fields and data types pass validation; zero unexplained negative run components, batter-plus-extras/total equation failures, invalid event-order collisions, or unknown event types contribute to a derived statistic. Unknown/unsupported values are retained as unknown and excluded from dependent measures.

**How tested:** Version-pinned schema validation; type/range checks; arithmetic invariants; delivery-order validation that preserves array order and allows repeated `actual_delivery` labels where the source format documents them; tests for extras, wickets, multiple events, nulls, and unsupported keys. Do not coerce invalid values to zero or silently repair them.

**Evidence/artifact required:** Schema-validation report by file/schema version; typed-field and invariant results; exception/quarantine list; validator version and tests/fixtures.

**Failure action:** Quarantine the affected record or file and block every dependent metric until the discrepancy is understood and the rule is documented. Preserve the source value.

**Owner approval status:** **PENDING**.

### Gate 4 — Dataset and match completeness; scorecard and delivery-stat reconciliation

**Exact original requirement (Section 4, Match completeness):**

> For a match accepted for a metric, all required innings/events are present or explicitly accounted for; delivery totals and outcome reconcile with an authoritative scorecard where available. Zero unexplained score/result differences. Unavailable independent corroboration must be stated and blocks any metric whose acceptance policy requires it.

**Proposed measurable pass condition:** For every match/metric accepted, the required innings, deliveries, termination and event flags are either complete or explicitly accounted for; available official scorecard totals/outcome reconcile with zero unexplained difference. Where independent corroboration is unavailable, record that limitation and block each metric for which the approved policy requires corroboration. Publish coverage counts by competition/season and distinguish expected gaps, unavailable source records, incomplete innings and rejected records.

**How tested:** Compare delivery-derived innings totals/outcomes and applicable score/bowling figures against an identified authoritative scorecard; reconcile only semantically comparable fields; run completeness checks for innings, event sequences, targets, revised targets, penalties, DLS, ties, forfeits and Super Overs. Validate expected fixture coverage against a dated source inventory without treating absent files as proof that a match did not occur.

**Evidence/artifact required:** Match acceptance record; source scorecard URL/document and checked date; field-by-field reconciliation output; competition/season coverage manifest; list of missing, incomplete, quarantined and unresolved matches; rule/version and source hashes.

**Failure action:** Keep the match or affected metric unaccepted/unavailable; quarantine unexplained discrepancies. Never correct a source by guess or promote partial agreement to a full match acceptance.

**Owner approval status:** **PENDING**.

**Threshold note:** The original sets zero unexplained score/result differences. It does not give a numeric completeness percentage or define a count threshold for unavailable corroboration. No additional numeric threshold is claimed here.

### Gate 5 — Player identity matching, uniqueness and human review

**Exact original requirement (Section 4, Identity quality):**

> 100% of linked player records have a documented accepted crosswalk version and reviewer decision. Zero ambiguous, unmatched, name-only, or namespace-unverified links in linked/player-level outputs. Reviewer appointment must be recorded before any approval.

**Related exact identity rule (`docs/external_data_integration_audit.md`, Section 4, Player IDs):**

> Duplicate display names, multiple external IDs, conflicting teams/roles, or many-to-many mappings are `ambiguous` and block merge.

**Proposed measurable pass condition:** Every local-to-external player link shown in a linked output has an accepted, versioned crosswalk, evidence, and human reviewer decision. Zero ambiguous, unmatched, name-only, or namespace-unverified links appear in linked/player-level outputs. Every detected duplicate-name, multiple-ID, conflicting-context or many-to-many candidate is explicitly blocked as ambiguous until reviewed. The appointed reviewer’s decision is recorded; appointment does not itself accept any identity.

**How tested:** Verify each linked output against the accepted crosswalk version; assert that only `accepted` rows are eligible; run uniqueness and collision checks by provider ID, local ID, name, team and match context; exercise duplicate display names, aliases, initials, surname-only, exact-name collisions and conflicting roster cases using synthetic fixtures; inspect reviewer identity, decision, timestamp, evidence and reason. Automated similarity may generate candidates only.

**Evidence/artifact required:** Versioned player crosswalk; candidate/collision report; reviewer audit trail; source roster and match-context references; test report covering ambiguous and unmatched scenarios.

**Failure action:** Block the link and affected player-level output; mark the candidate ambiguous/unmatched and retain its reason. No fuzzy or numeric-ID override, automatic merge, or invented identity is allowed.

**Owner approval status:** **PENDING**.

**Threshold note:** The original requires 100% accepted crosswalks and zero disallowed identity states in linked outputs. It does not specify a numeric minimum evidence count for a human identity decision; this draft does not invent one. The owner-appointed reviewer role is recorded in `docs/external_data_governance_owner_decision.md`, but identity controls and individual approvals remain unimplemented/unapproved.

### Gate 6 — Provenance, timestamps and statistic lineage

**Exact original requirement (Section 4, Provenance of statistics):**

> 100% of exposed statistics identify provider, run/source hashes, accepted match IDs or reproducible match set, exact date window, metric/rule version, sample count, and validation state. Zero statistic without a resolvable lineage path.

**Proposed measurable pass condition:** Every statistic made available through a future external API or UI includes all listed provenance fields, resolves to source files and an accepted reproducible match set, and reports an exact date window and validation state. Zero exposed statistics lack lineage. Every source/run also records retrieval/check timestamps and source publication date where available.

**How tested:** Automated response/schema validation for required provenance fields; trace each displayed statistic back through metric version, match set, provider IDs and file hashes to its manifest; attempt lineage resolution for every output row/aggregate; validate timestamps and date-window boundaries.

**Evidence/artifact required:** Run manifest, source hashes, accepted match set, metric specification/version, validation report, timestamped API/UI sample payloads and lineage test report.

**Failure action:** Withhold the statistic/response and report a provenance error. Do not show an untraceable value as verified or silently substitute a different source.

**Owner approval status:** **PENDING**.

### Gate 7 — Freshness and stale-data labeling

**Exact original requirement (Section 4, Freshness):**

> A view labeled “current” has a source check/retrieval timestamp no older than 30 calendar days. Older evidence is visibly marked stale with its last checked date. Snapshot history is never overwritten.

**Proposed measurable pass condition:** At render/request time, a “current” view’s relevant source timestamp is at most 30 calendar days old; if older, the view states its last checked date and is marked stale. Every snapshot remains available under its original run ID. No new threshold is introduced.

**How tested:** Unit tests at timestamps exactly 30 calendar days old, just inside and just outside the boundary; verify source timestamp selection, stale label, visible last-checked date and immutable snapshot references. Date/time calculation and timezone handling must be specified in the implementation tests before release.

**Evidence/artifact required:** Timestamped source/run manifest; automated freshness test output including boundary cases; rendered stale/current UI/API examples; snapshot immutability test result.

**Failure action:** Do not label the view current. Mark it stale or unavailable with the last checked date; retain the snapshot and block overwrite.

**Owner approval status:** **PENDING**.

### Gate 8 — API read-only behavior and localhost isolation

**Exact original requirement (Section 4, API isolation):**

> 100% of new external routes are under a separate `/api/v1/external-cricket` prefix/router; only read methods are exposed; zero client-supplied filesystem paths; fixed artifact allowlist; bounded query inputs; local loopback binding and local CORS only. Existing endpoint paths and schemas remain unchanged.

**Proposed measurable pass condition:** All new endpoints use the separate prefix; only GET/OPTIONS needed for read access are available; zero endpoints accept a client filesystem path; all artifacts resolve through a fixed allowlist; all query inputs have explicit bounds; service binds only to loopback and CORS is restricted to approved local origins; existing endpoint paths/schemas compare unchanged.

**How tested:** Inspect route inventory/OpenAPI methods and prefixes; automated tests for rejected path parameters and query bounds; bind-address and CORS configuration tests; verify no write methods or file mutations; compare pre/post OpenAPI schemas and existing endpoint response fixtures.

**Evidence/artifact required:** Route/OpenAPI inventory; security test report; binding/CORS configuration evidence; artifact allowlist; before/after existing API schema and response comparison.

**Failure action:** Block API release and remove/disable the failing route until all isolation conditions pass. Any change to existing API schema/behavior is a regression blocker.

**Owner approval status:** **PENDING**.

**Threshold note:** The original requires zero client-supplied paths and 100% route prefix coverage. It does not specify a numeric query length/page-size value; those bounds must be set and documented in implementation review rather than invented here.

### Gate 9 — External UI separation

**Exact original requirement (Section 4, UI separation):**

> All four external areas are visibly labeled external; every player link displays accepted identity state; all statistics show window, sample and provenance. No external route/data import feeds current ranking, eligibility, auction, pressure, or PDF components.

**Proposed measurable pass condition:** All four approved external sections are visibly identified as external evidence; every player link shows its accepted identity state; every statistic displays date window, sample count and provenance; zero imports, requests, state updates or data dependencies from external endpoints feed existing ranking, eligibility, auction, pressure or PDF components.

**How tested:** Route/component dependency inspection; UI tests for labels, identity states, date window, sample and provenance; network/API mock tests to verify external data is consumed only by external sections; component import and state-flow audit for prohibited existing sections.

**Evidence/artifact required:** UI route/component map; automated UI test output; dependency/import report; screenshots or rendered review of each external section and the existing protected sections; API-call audit.

**Failure action:** Block UI release; remove the cross-layer dependency or correct missing labels/provenance. No external value may appear in an existing section while the issue remains.

**Owner approval status:** **PENDING**.

### Gate 10 — Regression testing and baseline fixtures

**Exact original requirement (Section 4, Regression testing):**

> Before each release, project Python, API, and frontend suites all pass. Baseline at this decision: 113 project Python tests, 14 API tests, 11 frontend tests across 3 files. Add tests for external router isolation, read-only behavior, path denial, validation, identity ambiguity, provenance, freshness and no cross-layer writes; zero failures and zero changed existing ranking outputs.

**Proposed measurable pass condition:** Before each release, all three existing suites pass; the baseline recorded in the original requirement remains 113/14/11 across 3 frontend test files unless a separately documented test-suite change updates the baseline. All listed new test categories are present and pass. Zero existing ranking output changes. Baseline protected hashes and comparison fixtures exist before implementation begins.

**How tested:** Run the project Python, API and frontend test commands; verify required new tests are collected; compare test counts/results with the approved baseline; run ranking output regression comparisons and confirm zero changed outputs. Capture pre-implementation protected hashes and immutable comparison fixtures.

**Evidence/artifact required:** Timestamped test reports and commands; test inventory; baseline hash manifest; ranking comparison fixture/output; regression summary identifying any added/removed tests or baseline updates.

**Failure action:** Block release. Diagnose failures; do not waive a failure or redefine the baseline without a separately documented owner decision. Any ranking output change is a blocker.

**Owner approval status:** **PENDING**.

**Threshold note:** “Zero failures” and “zero changed existing ranking outputs” are original thresholds. Hash fixture scope must cover the protected artifacts listed in Gate 11; no hash baseline has been approved as captured.

### Gate 11 — Existing analytics, rankings and outputs remain unchanged

**Exact original requirement (Section 4, Existing analytics protection):**

> Hash-compare protected source datasets and frozen analytical artifacts before/after implementation; all protected hashes must match. Compare Phase 5G ranks/player IDs/scores, Phase 5H eligibility evidence, existing API ranking responses and auction overlay rows/statuses; all must be exactly unchanged. Any difference is a release blocker.

**Proposed measurable pass condition:** Every artifact designated protected before implementation has a pre-change hash and matching post-change hash. Phase 5G ranks/player IDs/scores, Phase 5H eligibility evidence, existing API ranking responses and auction overlay rows/statuses are exactly equal to baseline. Include validated PDF/report/source artifacts in the protected inventory in accordance with the owner decision. No changes are allowed in the protected list.

**How tested:** Generate a signed/versioned pre-change hash manifest and deterministic response/data comparison fixtures; after each implementation change, recalculate hashes and compare rows, IDs, scores, order, eligibility fields, API payloads, overlay classifications and PDF hashes. Fail on any difference. Do not regenerate protected analytics merely to create a baseline.

**Evidence/artifact required:** Approved protected-artifact inventory; pre/post SHA-256 manifests; deterministic Phase 5G/5H/API/overlay comparison reports; validated PDF hash comparison; review sign-off.

**Failure action:** Release blocker. Stop and investigate; revert or isolate the external change. Do not accept a difference as cosmetic or expected without a separate owner-approved change request and full impact validation.

**Owner approval status:** **PENDING**.

### Gate 12 — Security and proprietary-data exclusion (supporting control)

This supporting gate operationalizes existing privacy/security constraints. It is not an additional approved Section 4 threshold.

**Exact related original requirement (`docs/external_data_integration_audit.md`, Section 8):**

> Keep downloaded records local and read-only after acquisition; never upload proprietary raw tables, player mapping tables, API payloads or report artifacts to external services. Public-source player names/IDs remain subject to source terms; local crosswalks reveal the project’s proprietary ID relationships and should be access-controlled and excluded from public responses. Do not store credentials or secrets in manifests. Log run IDs and status, not unnecessary player-search text. Limit API file access to a fixed allowlist, use no client path parameters, bind only to loopback for local use, and restrict CORS to the local frontend. No public deployment is proposed.

**Proposed measurable pass condition:** Zero proprietary raw tables, player mappings, local crosswalks, credentials/secrets, or unapproved report artifacts appear in public outputs, external service uploads, or public API responses; local crosswalks are access-controlled; API file access is limited to the allowlist; no public deployment is configured. These “zero” checks are proposed interpretations of the quoted exclusions, not a separately approved Section 4 threshold.

**How tested:** Inventory files and response schemas; scan generated public artifacts for protected filenames/fields and secret patterns; test API responses and file-path denial; inspect deployment/bind/CORS configuration and data egress configuration; review manifest contents and logging fields. A scan alone is not proof of legal or security clearance.

**Evidence/artifact required:** Data classification/allowlist; response and artifact scan report; API path/access tests; deployment and CORS configuration evidence; manifest/log review; documented reviewer sign-off.

**Failure action:** Block publication/deployment and remove or restrict the exposed material; investigate possible disclosure and follow the project’s incident process. Maintain NO-GO for integration until resolved.

**Owner approval status:** **PENDING**.

## 3. Numeric thresholds and proposed interpretations

The following numeric thresholds already appear in the original Section 4 and are repeated without weakening: **100%** metadata/schema/provenance/identity coverage where specified; **zero** unresolved rights, duplicate accepted match keys, listed unexplained quality failures, disallowed identity links, untraceable statistics, client paths, regression failures, and changed existing ranking outputs; **30 calendar days** for a view labeled current. Exact language is retained under each gate above.

The original does **not** specify a numeric completeness percentage, minimum identity evidence count, query-length/page-size bounds, collision-detection recall percentage, or scan false-positive/false-negative tolerance. No such threshold is represented here as existing policy. Where a future test needs one, the proposed number or test criterion must be separately labeled **PROPOSED** and approved by the owner before it becomes a gate. Nothing in this draft relaxes an original threshold.

## 4. Cross-document status and blockers

The owner decision record approves the governance scope and technical boundaries in principle, but explicitly keeps all acceptance-gate approvals pending. The source-rights review is preliminary and grants no legal clearance. The existing audit’s historical Cricsheet pilot findings remain unchanged. The owner-appointed External Player Identity Reviewer does not imply that review controls are implemented or that any identity link is accepted.

The following prerequisites remain pending and block any acquisition or implementation:

- Source-specific Cricsheet, official IPL, and any secondary-provider rights reviews.
- Project-owner approval of every measurable gate in Section 4 of `docs/external_data_governance_decision.md`.
- Historical Cricsheet pilot review and documented reuse decision.
- Baseline protected hashes and regression comparison fixtures.
- Implementation of identity, provenance, freshness, API isolation, UI separation, security and non-regression controls, followed by verification.
- Separate explicit authorization to proceed after gates are approved.

**Overall status remains: NO-GO for external data acquisition, download, ingestion, and integration.**

## 5. Approval record

| Gate | Owner approval status | Approval date / note |
|---|---|---|
| 1. Source licensing and attribution | **PENDING** | — |
| 2. Snapshot, match-ID uniqueness and collision handling | **PENDING** | — |
| 3. Schema, types and event quality | **PENDING** | — |
| 4. Dataset/match completeness and reconciliation | **PENDING** | — |
| 5. Player identity and human review | **PENDING** | — |
| 6. Provenance and statistic lineage | **PENDING** | — |
| 7. Freshness and stale labeling | **PENDING** | — |
| 8. API isolation | **PENDING** | — |
| 9. UI separation | **PENDING** | — |
| 10. Regression testing and baseline fixtures | **PENDING** | — |
| 11. Existing analytics/output protection | **PENDING** | — |
| 12. Security and proprietary-data exclusion (supporting control) | **PENDING** | — |

## 6. Regression verification for this documentation-only draft

No external data was downloaded or ingested; no downloader or ingestion process was run. No code, dataset, analytics, ranking, API, UI, auction overlay, or PDF was modified. The following existing regression suites are run as documentation-only verification:

| Suite | Baseline | Result |
|---|---:|---|
| Project Python | 113 tests | **PASS — 113 passed** (`.\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider`, project root) |
| API | 14 tests | **PASS — 14 passed** (`.\api\.venv\Scripts\python.exe -m pytest -q api\tests -p no:cacheprovider`, project root) |
| Frontend | 11 tests across 3 files | **PASS — 11 passed across 3 files** (`npm.cmd test -- --run`, `frontend/`) |
