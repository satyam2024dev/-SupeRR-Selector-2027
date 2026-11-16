# External Cricket Data — Acceptance Gate Decision Record

**Project:** SupeRR Selector Season 2  
**Record type:** Formal gate decision record; submitted for project-owner approval  
**Decision dates:** Original acceptance gates remain pending; three clarification decisions approved by project owner on 14 November 2026 (see `docs/external_data_clarification_owner_decision.md`).
**Overall status:** **NO-GO for external data acquisition, download, ingestion, and integration.**

## 1. Authority and scope of this record

This record carries forward all eleven original acceptance-gate requirements from Section 4 of `docs/external_data_governance_decision.md` and the supporting security gate from `docs/external_data_acceptance_gate_approval.md`. Original wording and numeric thresholds are retained. The three clarification rules below were approved by the project owner on 14 November 2026, as recorded in `docs/external_data_clarification_owner_decision.md`; that approval does not approve any gate.

The project owner approved the external-data governance scope and technical boundaries in principle on 14 November 2026, and appointed themself as External Player Identity Reviewer. Those decisions do not approve any gate, clear source rights, accept an identity link, authorize data acquisition, or authorize implementation. **Owner decision for every gate in this record is PENDING.**

The expected-inventory, crosswalk-evidence and freshness-timestamp clarifications in Section 3 are **APPROVED BY PROJECT OWNER** on 14 November 2026. Gates 1 through 12 remain **PENDING**.

## 2. Original acceptance gates

For every gate below, “original requirement” is reproduced verbatim from Section 4 of `docs/external_data_governance_decision.md`, except Gate 12, which is explicitly identified as the supporting control from Section 8 of `docs/external_data_integration_audit.md`.

### Gate 1 — Source and license

**Original requirement:**

> 100% of accepted files have provider, canonical source URL/member, retrieval timestamp, applicable license/terms, required attribution, schema/version, transformation lineage and SHA-256 recorded. Zero accepted records with unresolved rights or attribution.

**Proposed pass condition:** Each accepted file has every listed field and a source-specific review record for the exact format and intended use. No accepted item has unresolved rights or attribution. This does not constitute legal clearance.

**Evidence needed:** Immutable source manifest; SHA-256 verification; provider URL and archive member/document reference; schema/version and transformation history; dated source-rights and attribution review; attribution/notice text.

**Failure consequence:** Exclude and quarantine the source/file; no acquisition, use, or publication while rights or attribution are unresolved.

**Owner decision:** **PENDING**.

### Gate 2 — Snapshot integrity and match-ID uniqueness

**Original requirement:**

> 100% of acquired files pass checksum verification after storage; source snapshot is immutable; every changed, added or removed file is represented in a run diff. Duplicate `(provider, provider_match_id, source_version)` count is zero in accepted data.

**Proposed pass condition:** Every file hash verifies; prior snapshots are immutable; all additions, changes and removals are reported; accepted data has zero duplicate provider match keys. Provider and local match IDs remain namespaced. Conflicting or non-unique match crosswalk candidates are flagged and withheld, not joined by guess.

**Evidence needed:** Run manifests, checksum report, snapshot-diff report, unique-key validation, and a bidirectional match-crosswalk collision report with decision/status and reasons.

**Failure consequence:** Quarantine the affected file or fixture, preserve prior snapshots, and block acceptance until the collision is resolved and documented.

**Owner decision:** **PENDING**.

### Gate 3 — Schema and event quality

**Original requirement:**

> 100% of accepted files parse against the declared provider schema version. Zero unexplained negative run values, run-component equation failures, invalid delivery sequence collisions, or unknown event types used in derived statistics. Unsupported/unknown values remain explicit and are excluded from dependent metrics.

**Proposed pass condition:** All accepted files parse and meet declared field types. The listed failure counts are zero for accepted files and dependent metrics; unsupported values stay explicit and do not enter calculations. Source order and format-specific repeated delivery labels are handled according to the declared schema.

**Evidence needed:** Version-pinned parser/schema report; data-type and range checks; arithmetic invariant report; sequence validation; unknown-value and quarantine report; tested validator version.

**Failure consequence:** Quarantine affected records and block dependent metrics. Do not coerce unknown values to zero or silently repair the source.

**Owner decision:** **PENDING**.

### Gate 4 — Match completeness and score/result reconciliation

**Original requirement:**

> For a match accepted for a metric, all required innings/events are present or explicitly accounted for; delivery totals and outcome reconcile with an authoritative scorecard where available. Zero unexplained score/result differences. Unavailable independent corroboration must be stated and blocks any metric whose acceptance policy requires it.

**Proposed pass condition:** For every accepted match/metric, all required innings and events are present or explicitly accounted for, and available authoritative scorecard comparisons have zero unexplained differences. Missing, incomplete, quarantined and available matches are distinguishable. Do not interpret missing external records as proof a match did not occur. The expected-inventory clarification is approved, but Gate 4 remains pending.

**Evidence needed:** Dated expected match inventory by competition and season; source coverage manifest; match-level reconciliation report; official scorecard URL/document and check date where available; list and counts of expected, available, missing, incomplete and quarantined fixtures; criteria for each status; source hashes and metric/rule version.

**Failure consequence:** Keep the affected match or metric unavailable/unaccepted; quarantine unexplained score/result differences; report coverage gaps without filling them by inference.

**Owner decision:** **PENDING**.

**Threshold note:** The original specifies zero unexplained score/result differences, but no numeric completeness percentage, minimum source overlap, or coverage target. No additional threshold is approved here.

### Gate 5 — Player identity and crosswalk quality

**Original requirement:**

> 100% of linked player records have a documented accepted crosswalk version and reviewer decision. Zero ambiguous, unmatched, name-only, or namespace-unverified links in linked/player-level outputs. Reviewer appointment must be recorded before any approval.

**Proposed pass condition:** Every linked player output uses a versioned crosswalk with an accepted reviewer decision; zero ambiguous, unmatched, name-only, or namespace-unverified records appear as linked. Duplicate names, conflicting teams/roles, multiple external IDs and many-to-many candidates remain blocked as ambiguous until human review. The accepted-crosswalk evidence clarification is approved, but Gate 5 remains pending. No individual player identity link is approved by that clarification.

**Evidence needed:** Accepted crosswalk version; source evidence; match/player context; reviewer decision and reason; reviewer identity; crosswalk version; duplicate/collision report; test evidence showing ambiguous candidates cannot reach linked outputs.

**Failure consequence:** Do not link or expose the identity as resolved; retain it as ambiguous/unmatched and block dependent player-level metrics. Reviewer appointment alone does not accept any identity link.

**Owner decision:** **PENDING**.

**Threshold note:** The original specifies 100% accepted crosswalk coverage and zero prohibited identity states in linked outputs. It does not specify a numeric minimum number of evidence items for a decision.

### Gate 6 — Provenance of statistics

**Original requirement:**

> 100% of exposed statistics identify provider, run/source hashes, accepted match IDs or reproducible match set, exact date window, metric/rule version, sample count, and validation state. Zero statistic without a resolvable lineage path.

**Proposed pass condition:** Every exposed statistic supplies all listed fields and can be traced back to the identified provider files, accepted match set, metric version, and validation result. Zero untraceable statistics are exposed.

**Evidence needed:** Run manifest; hashes; accepted match IDs or reproducible match set; date-window query/report; metric/rule specification and version; sample count; validation state; lineage test report.

**Failure consequence:** Withhold the statistic and report a provenance failure; do not display it as verified or substitute another source silently.

**Owner decision:** **PENDING**.

### Gate 7 — Freshness

**Original requirement:**

> A view labeled “current” has a source check/retrieval timestamp no older than 30 calendar days. Older evidence is visibly marked stale with its last checked date. Snapshot history is never overwritten.

**Proposed pass condition:** Retain the original 30-calendar-day limit and stale-label rule. Separately record source publication date, last successful retrieval date, and last verification date. Use successful verification of the specifically identified retrieved snapshot as the controlling freshness timestamp; failed retrievals and unverified checks must not reset the freshness clock. Keep all snapshot history immutable. This clarification is approved, but Gate 7 remains pending.

**Evidence needed:** Snapshot manifest with the three distinct dates; date/time semantics and controlling-timestamp selection; freshness tests at, inside and beyond the 30-day boundary; displayed current/stale result and last-checked date; immutable snapshot test.

**Failure consequence:** Do not label a view current when the controlling timestamp exceeds 30 calendar days or cannot be established. Mark stale/unavailable with the relevant last-checked date; preserve prior snapshots.

**Owner decision:** **PENDING**.

**Threshold note:** The original 30-calendar-day threshold is unchanged. The controlling timestamp definition is approved as a clarification; Gate 7 itself remains pending.

### Gate 8 — API isolation

**Original requirement:**

> 100% of new external routes are under a separate `/api/v1/external-cricket` prefix/router; only read methods are exposed; zero client-supplied filesystem paths; fixed artifact allowlist; bounded query inputs; local loopback binding and local CORS only. Existing endpoint paths and schemas remain unchanged.

**Proposed pass condition:** Every new external route uses the separate prefix and read-only methods; zero client-supplied filesystem paths are accepted; artifact reads use a fixed allowlist; query inputs are bounded; service binding and CORS remain local-only; existing endpoint paths and schemas are unchanged.

**Evidence needed:** Route/OpenAPI inventory; method/path tests; path-denial and query-bound tests; fixed allowlist; loopback/CORS configuration; before/after existing API schema and response comparison.

**Failure consequence:** Block route release; disable or correct the failing route. Any change to existing endpoint paths, schemas, or behavior blocks release.

**Owner decision:** **PENDING**.

**Threshold note:** The original requires zero client paths and 100% route-prefix coverage. It does not specify numeric query bounds; those must be proposed and approved before implementation.

### Gate 9 — UI separation

**Original requirement:**

> All four external areas are visibly labeled external; every player link displays accepted identity state; all statistics show window, sample and provenance. No external route/data import feeds current ranking, eligibility, auction, pressure, or PDF components.

**Proposed pass condition:** Each of the four external areas is visibly labeled; every player link displays its recorded identity state; every statistic displays its window, sample and provenance; no external route or data dependency reaches any listed existing component.

**Evidence needed:** Route/component dependency map; UI tests for labels, identity status, window, sample and provenance; request/state-flow audit; rendered review of all four external areas and protected existing sections.

**Failure consequence:** Block UI release; remove any cross-layer data flow and correct missing labels or evidence fields. Do not expose external values in existing sections.

**Owner decision:** **PENDING**.

### Gate 10 — Regression testing

**Original requirement:**

> Before each release, project Python, API, and frontend suites all pass. Baseline at this decision: 113 project Python tests, 14 API tests, 11 frontend tests across 3 files. Add tests for external router isolation, read-only behavior, path denial, validation, identity ambiguity, provenance, freshness and no cross-layer writes; zero failures and zero changed existing ranking outputs.

**Proposed pass condition:** Before a release, all three existing suites pass at the stated baseline unless a separately documented owner decision changes the suite baseline; all listed new test categories are implemented and pass; zero failures and zero changed existing ranking outputs. Baseline hashes and regression fixtures must exist before implementation, as separately pending in the owner decision.

**Evidence needed:** Timestamped commands and test reports; test inventory/collection output; external isolation test results; ranking comparison output; baseline fixture and hash-manifest references once authorized and created. This draft does not create those hashes or fixtures.

**Failure consequence:** Block release. Investigate failures or output changes; do not waive a test or redefine the baseline without explicit owner decision and documentation.

**Owner decision:** **PENDING**.

### Gate 11 — Existing analytics protection

**Original requirement:**

> Hash-compare protected source datasets and frozen analytical artifacts before/after implementation; all protected hashes must match. Compare Phase 5G ranks/player IDs/scores, Phase 5H eligibility evidence, existing API ranking responses and auction overlay rows/statuses; all must be exactly unchanged. Any difference is a release blocker.

**Proposed pass condition:** All protected hashes match exactly before and after implementation; Phase 5G ranks/player IDs/scores, Phase 5H eligibility evidence, existing API ranking responses and auction overlay rows/statuses are exactly unchanged. Preserve the validated PDF and associated source artifacts as protected outputs. No baseline hash or fixture is created by this draft.

**Evidence needed:** Approved protected-artifact inventory; baseline and post-change hashes; Phase 5G/5H comparisons; API response fixtures; auction overlay comparison; PDF/source-artifact comparison and reviewer sign-off.

**Failure consequence:** Release blocker. Stop and isolate or revert the change; no difference may be waived as cosmetic without separate explicit owner approval and a complete impact review.

**Owner decision:** **PENDING**.

### Gate 12 — Supporting security and proprietary-data exclusion

**Original supporting requirement (`docs/external_data_integration_audit.md`, Section 8):**

> Keep downloaded records local and read-only after acquisition; never upload proprietary raw tables, player mapping tables, API payloads or report artifacts to external services. Public-source player names/IDs remain subject to source terms; local crosswalks reveal the project’s proprietary ID relationships and should be access-controlled and excluded from public responses. Do not store credentials or secrets in manifests. Log run IDs and status, not unnecessary player-search text. Limit API file access to a fixed allowlist, use no client path parameters, bind only to loopback for local use, and restrict CORS to the local frontend. No public deployment is proposed.

**Proposed pass condition:** Retain all exclusions and local-only controls above. Zero proprietary raw tables, player mappings, restricted crosswalks, credentials/secrets, or protected report artifacts appear in public outputs or external-service uploads; crosswalks are access-controlled; API reads use only the fixed allowlist; deployment is loopback-only. These zero-count checks operationalize the supporting language and are not a separately approved numeric threshold.

**Evidence needed:** Data classification and allowlist; response/output review; secret and protected-data scan; API path/access tests; bind/CORS/deployment configuration; log and manifest review. A scan does not establish legal clearance.

**Failure consequence:** Block publication, deployment, and integration; restrict/remove exposure, investigate, and retain NO-GO until resolved.

**Owner decision:** **PENDING**.

## 3. Owner-approved clarifications (not acceptance-gate approvals)

These three clarifications add operational detail to existing gates. The project owner approved them on **14 November 2026** in `docs/external_data_clarification_owner_decision.md`. They do not replace, weaken, or approve any original acceptance gate.

### Clarification 1 — Dated expected match inventory

**APPROVED BY PROJECT OWNER — 14 November 2026.** Maintain a dated expected match inventory for IPL and men’s T20I, seasons 2022–2026 inclusive. The inventory should identify its source basis, scope, version/as-of date, and one row per expected fixture. For each inventory snapshot, report expected, available, missing, incomplete, and quarantined match counts by competition and season. Define mutually exclusive per-fixture status definitions that make the counts reconcile to the expected total. This approval creates no inventory and asserts no current counts.

**Evidence if approved:** Dated inventory and its source references; versioned status definitions; count/reconciliation report showing category totals match expected fixtures; change log between inventory versions.

### Clarification 2 — Required accepted-crosswalk evidence

**APPROVED BY PROJECT OWNER — 14 November 2026.** Every accepted player crosswalk must include source evidence, match/player context, reviewer decision, decision reason, and crosswalk version. Preserve provider/local ID namespaces, source display names, review timestamp, and unresolved/conflict status as needed to make the decision auditable. This approves evidence requirements only; it does not accept any player link or change the owner/reviewer appointment already recorded in the owner decision document.

**Evidence if approved:** Crosswalk schema; field-completeness validation; sample review records only after a separately authorized workflow exists; tests proving ambiguous/unmatched identities cannot appear as accepted links.

### Clarification 3 — Distinct source freshness timestamps

**APPROVED BY PROJECT OWNER — 14 November 2026.** Keep three separate dates: (1) source publication date, (2) last successful retrieval date, and (3) last verification date. Use successful verification of the specifically identified retrieved snapshot as the controlling freshness timestamp, recorded only after both retrieval and verification have succeeded. Retain retrieval and verification dates separately; do not let a publication date, failed retrieval, or an unverified page check reset the 30-calendar-day clock. The existing 30-calendar-day threshold and stale-label requirement remain unchanged.

**Evidence if approved:** Snapshot record containing the three distinct timestamps, snapshot ID/hash, explicit controlling timestamp field and derivation; boundary tests at and around 30 calendar days; UI/API evidence showing current versus stale state. No date is to be fabricated when a source does not provide a publication date.

## 4. Thresholds and approval state

Original numeric requirements remain exactly as written in Section 2: 100% where the original specifies it; zero for the stated failure categories; and no more than 30 calendar days for a view labeled current. This document does not lower or reinterpret those thresholds as approved policy.

Where an original requirement has no standalone numeric threshold (including expected-inventory completeness percentage, a minimum number of identity evidence items, or query-size bounds), none is represented as an existing numeric threshold. The three clarifications in Section 3 are approved, but this does not approve Gates 1–12 or invent additional numeric thresholds. Any future new numerical threshold must be explicitly labeled PROPOSED and separately approved by the project owner.

| Gate / clarification | Owner decision | Approval date / notes |
|---|---|---|
| Gate 1 — Source and license | **PENDING** | — |
| Gate 2 — Snapshot and match-ID uniqueness | **PENDING** | — |
| Gate 3 — Schema and event quality | **PENDING** | — |
| Gate 4 — Match completeness and reconciliation | **PENDING** | — |
| Gate 5 — Player identity and crosswalk quality | **PENDING** | — |
| Gate 6 — Statistic provenance | **PENDING** | — |
| Gate 7 — Freshness | **PENDING** | — |
| Gate 8 — API isolation | **PENDING** | — |
| Gate 9 — UI separation | **PENDING** | — |
| Gate 10 — Regression testing | **PENDING** | — |
| Gate 11 — Existing analytics protection | **PENDING** | — |
| Gate 12 — Supporting security/data exclusion | **PENDING** | — |
| Clarification 1 — Dated expected match inventory | **APPROVED BY PROJECT OWNER** | 14 November 2026; `docs/external_data_clarification_owner_decision.md` |
| Clarification 2 — Accepted crosswalk evidence fields | **APPROVED BY PROJECT OWNER** | 14 November 2026; `docs/external_data_clarification_owner_decision.md`; no individual identity link approved |
| Clarification 3 — Freshness timestamp definition | **APPROVED BY PROJECT OWNER** | 14 November 2026; `docs/external_data_clarification_owner_decision.md`; original 30-day threshold retained |

## 5. Overall status and blockers

**NO-GO for external data acquisition, download, ingestion, and integration.** No gate has been approved by this record. Source-rights reviews remain pending; no legal clearance is claimed. The owner-appointed identity reviewer does not establish that any identity link has been reviewed or accepted. Historical pilot review, protected baseline hashes, and regression fixtures remain pending and are not created by this document.

No external data was downloaded or ingested, and no downloader or ingestion process was run. No code, analytics, datasets, rankings, APIs, UI, auction overlay, or PDF was modified.

## 6. Documentation-only regression verification

Run the existing regression suites after this documentation-only update:

| Suite | Existing baseline | Result |
|---|---:|---|
| Project Python | 113 tests | **PASS — 113 passed** (`.\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider`, project root) |
| API | 14 tests | **PASS — 14 passed** (`.\api\.venv\Scripts\python.exe -m pytest -q api\tests -p no:cacheprovider`, project root) |
| Frontend | 11 tests across 3 files | **PASS — 11 passed across 3 files** (`npm.cmd test -- --run`, `frontend/`) |
