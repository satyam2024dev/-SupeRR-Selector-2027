# External Cricket Data Governance Decision

**Project:** SupeRR Selector Season 2  
**Decision status:** Proposed governance controls; owner approvals remain pending. This document does not authorize acquisition or implementation.  
**Basis:** `docs/external_data_integration_audit.md`  
**Prepared:** 14 November 2026

## 1. Purpose and proposed scope

This document defines the proposed governance boundary for a future external cricket data layer. Its purpose is to make external match evidence discoverable, attributable, reviewable and independently testable without changing the project’s existing analytics or user experience.

The proposed scope is a separately stored, namespaced evidence layer for selected IPL and men’s T20I match records, with:

1. External Match Centre for accepted fixture and event evidence.
2. Player Evidence Profiles for externally sourced evidence with reviewed identity links.
3. Performance Trends for descriptive, external-only summaries with stated match counts and date windows.
4. Data Provenance Centre for source, license, snapshot, validation and coverage records.

No scope for seasons, gender, public redistribution, automated refresh, or incorporation into existing performance analysis is approved by this document. Those choices remain pending owner approval. Existing Cricsheet pilot artifacts are historical research evidence, not a production source or blanket authorization to ingest more data.

## 2. Proposed source hierarchy and source obligations

### 2.1 Source hierarchy

1. **Cricsheet JSON:** primary candidate for structured ball-by-ball external evidence. Keep provider records separate and preserve its schema/version and identifiers. Published coverage figures are dynamic and do not prove match-level overlap or completeness.
2. **Official IPL publications:** authority for official IPL announcements and for match facts published by IPL, including retention, release, trade, registration/list and final auction information when an official document actually exists. A previous season’s list, general news index, trade or release does not prove 2027 auction availability.
3. **Secondary providers:** discovery or field-level cross-check only when source lineage and reuse rights are documented. A secondary source that republishes Cricsheet is not independent corroboration. Prefer official IPL/BCCI evidence for official IPL match outcomes where available.

### 2.2 Licensing and attribution controls

- For Cricsheet JSON and registers, record and comply with ODC-BY 1.0, including applicable attribution, license notices, and attribution obligations for redistributed adapted databases. Review the full license and current Cricsheet notice before each new use or distribution.
- Do not assume another Cricsheet format has the same license. A format or source change requires a new license review.
- For IPL pages and documents, observe current site terms. Retain only facts and links needed for audit; do not copy protected prose, images, logos, or other material without rights. Scraping or redistribution requires separate rights review and owner approval.
- For every source, record provider, canonical URL, archive/member or document identity, publication date if available, retrieval/check timestamp, license/terms reference, required attribution, file hash where applicable, schema/version, transformations, and any source lineage.
- If rights or attribution requirements are unclear, quarantine the source and do not publish or redistribute its records.

### 2.3 Coverage and update process

The 14 November 2026 audit observed Cricsheet’s published inventory at 1,243 IPL matches and 5,849 T20Is overall, including 3,649 men’s and 2,200 women’s records. These figures are dated source-page observations, not approved scope counts, match overlap, or a guarantee of completeness. Cricsheet documents withheld and unavailable records. An absent record in a snapshot must be labeled “not observed in this source snapshot,” never “match did not occur.”

Proposed update process: operator-initiated, explicit snapshot acquisition only; no background downloader. For every run, create an immutable run ID and manifest, capture source-page coverage and timestamps, hash every file, compare changed/new/removed members to the prior snapshot, validate and quarantine discrepancies, and publish a change report. Do not overwrite prior snapshots. The proposed freshness service level is a check/retrieval within **30 calendar days** for any display labeled “current”; otherwise display the actual last checked date and mark it stale. Historical analyses may use frozen snapshots and must state their exact snapshot and date window.

## 3. Player identity reconciliation policy

### 3.1 Mandatory rules

- Treat local project player IDs, Cricsheet registry IDs and optional third-party IDs as separate namespaces. Never join bare IDs based on apparent numeric/string equality.
- Preserve the provider’s original display name. Conservative Unicode/spacing/case normalization may generate candidates only; it cannot by itself accept an identity.
- Exact name, initials, surname, alias, spelling similarity, team, role or date alone is insufficient for automatic identity acceptance.
- Candidate review must use match-specific context (fixture, roster, team, date and competition) and an authoritative ID or documented human decision. Conflicting evidence blocks acceptance.
- Duplicate names, multiple possible provider IDs, conflicting team/context, many-to-one mapping, similar names, unverified aliases, or any other non-unique match are `ambiguous`. Ambiguous matches must receive mandatory human review and must not be merged, used in player-level statistics or exposed as linked local profiles before approval.
- Unmatched entities stay `unmatched`; no player identity, role, biography or statistic may be invented.
- Keep a versioned, access-controlled crosswalk containing local ID, provider and external ID namespaces, source names, evidence URLs/records, status, reviewer, review date and version. Preserve rejected and ambiguous decisions with reasons.

### 3.2 Identity-review role and appointment

**Required role:** External Player Identity Reviewer, responsible for reviewing evidence and recording accept/reject/ambiguous decisions for player crosswalk entries. The reviewer must be able to assess cricket roster and match context and must not approve a link solely because an automated similarity or numeric ID match suggests it.

**Appointment status: PENDING.** No reviewer has been appointed in the audit or this decision document. The project owner must name the person or accountable role before any identity candidate is accepted. The project owner retains final authority to approve the governance policy and any change that could affect existing project outputs.

## 4. Measurable acceptance criteria

The following are proposed hard gates. A match or metric that misses a gate remains quarantined/unavailable; thresholds must not be weakened to increase coverage. The project owner must approve these thresholds before implementation begins.

| Area | Proposed acceptance gate |
|---|---|
| Source and license | 100% of accepted files have provider, canonical source URL/member, retrieval timestamp, applicable license/terms, required attribution, schema/version, transformation lineage and SHA-256 recorded. Zero accepted records with unresolved rights or attribution. |
| Snapshot integrity | 100% of acquired files pass checksum verification after storage; source snapshot is immutable; every changed, added or removed file is represented in a run diff. Duplicate `(provider, provider_match_id, source_version)` count is zero in accepted data. |
| Schema and event quality | 100% of accepted files parse against the declared provider schema version. Zero unexplained negative run values, run-component equation failures, invalid delivery sequence collisions, or unknown event types used in derived statistics. Unsupported/unknown values remain explicit and are excluded from dependent metrics. |
| Match completeness | For a match accepted for a metric, all required innings/events are present or explicitly accounted for; delivery totals and outcome reconcile with an authoritative scorecard where available. Zero unexplained score/result differences. Unavailable independent corroboration must be stated and blocks any metric whose acceptance policy requires it. |
| Identity quality | 100% of linked player records have a documented accepted crosswalk version and reviewer decision. Zero ambiguous, unmatched, name-only, or namespace-unverified links in linked/player-level outputs. Reviewer appointment must be recorded before any approval. |
| Provenance of statistics | 100% of exposed statistics identify provider, run/source hashes, accepted match IDs or reproducible match set, exact date window, metric/rule version, sample count, and validation state. Zero statistic without a resolvable lineage path. |
| Freshness | A view labeled “current” has a source check/retrieval timestamp no older than 30 calendar days. Older evidence is visibly marked stale with its last checked date. Snapshot history is never overwritten. |
| API isolation | 100% of new external routes are under a separate `/api/v1/external-cricket` prefix/router; only read methods are exposed; zero client-supplied filesystem paths; fixed artifact allowlist; bounded query inputs; local loopback binding and local CORS only. Existing endpoint paths and schemas remain unchanged. |
| UI separation | All four external areas are visibly labeled external; every player link displays accepted identity state; all statistics show window, sample and provenance. No external route/data import feeds current ranking, eligibility, auction, pressure, or PDF components. |
| Regression testing | Before each release, project Python, API, and frontend suites all pass. Baseline at this decision: 113 project Python tests, 14 API tests, 11 frontend tests across 3 files. Add tests for external router isolation, read-only behavior, path denial, validation, identity ambiguity, provenance, freshness and no cross-layer writes; zero failures and zero changed existing ranking outputs. |
| Existing analytics protection | Hash-compare protected source datasets and frozen analytical artifacts before/after implementation; all protected hashes must match. Compare Phase 5G ranks/player IDs/scores, Phase 5H eligibility evidence, existing API ranking responses and auction overlay rows/statuses; all must be exactly unchanged. Any difference is a release blocker. |

If a required official scorecard is unavailable, the record may remain available as explicitly **unverified external evidence** only if a separately approved display policy permits it; it cannot be described as verified or accepted under the scorecard gate. This exception cannot waive source identity, schema, provenance or license requirements.

## 5. Explicit preservation protections

The following are protected and must not be modified, regenerated, overwritten, reinterpreted or used as an implicit destination for external data under this governance decision:

- Existing raw datasets and processed datasets.
- Phase 5A–5H analytics and methodology definitions.
- Frozen Phase 5G Batter Rankings, player IDs, rank order and stored scores.
- Phase 5C eligibility evidence and thresholds.
- Phase 5H bowling evidence and eligibility decision.
- Existing API ranking endpoints and response behavior.
- Existing React application routes and behavior.
- Streamlit application behavior.
- Auction availability overlay and its classifications/rules.
- Validated PDF report and its source/output files.

External raw files, normalized records, crosswalks, manifests, validation products, endpoints and UI must remain separately namespaced. No external statistic may silently become local source evidence. Any future proposal to use external data in a protected output requires a new, explicit owner-approved change request, impact audit, reproducibility evidence, and revalidation of affected artifacts. This document itself grants no such permission.

## 6. Decisions requiring project-owner approval

All items below are **PENDING** unless the owner records a decision in a later revision. None is approved by the audit or this document.

| Decision | Current status | Approval needed |
|---|---|---|
| Exact competitions, gender scope, seasons and date range | PENDING | Confirm IPL and men’s T20I only, or specify another scope. |
| Cricsheet and official-source use/redistribution posture | PENDING | Local-only use vs distribution; approve rights review and license handling. |
| External Player Identity Reviewer appointment | PENDING | Name the accountable person/role. |
| Acceptance thresholds in Section 4 | PENDING | Approve or revise the measurable gates before implementation. |
| Refresh cadence and 30-day “current” threshold | PENDING | Approve operator process and freshness service level. |
| Official corroboration requirements | PENDING | Define when independent official scorecard validation is mandatory or unavailable. |
| API audience/deployment and authentication boundary | PENDING | Confirm localhost-only use or commission a separate security design. |
| External UI visibility and user audience | PENDING | Approve whether the four proposed sections are in-scope for implementation. |
| Reuse/hardening of existing `src/cricsheet_pilot.py` vs a new implementation | PENDING | Choose after reviewing technical and operational separation. |
| Any future effect on existing rankings, eligibility, analytics, auction decisions, methodology or PDF | NOT AUTHORIZED | Requires a separate request and explicit approval; no implied approval here. |

## 7. Implementation go/no-go checklist

### GO only when every applicable item is checked and owner-approved

- [ ] Project owner has approved scope (competition, format/gender, seasons and date range).
- [ ] Project owner has approved local-use/distribution posture and the source rights plan.
- [ ] Cricsheet ODC-BY 1.0 attribution and any official/secondary source terms have been reviewed for intended use.
- [ ] External Player Identity Reviewer is appointed and the review/audit record format is agreed.
- [ ] Project owner has approved the measurable acceptance gates in Section 4.
- [ ] Source snapshot and update cadence are approved; immutable manifest/hash/change-diff process is specified.
- [ ] Separate storage, quarantine and provenance paths are approved; historical pilot is preserved.
- [ ] API and UI isolation design is approved; no external data path into existing outputs is present.
- [ ] Baseline protected hashes and Phase 5G/5H/API/overlay comparison fixtures are captured before implementation.
- [ ] Existing regression suites pass before work begins; new isolation and quality tests are planned.
- [ ] All unresolved records and identity conflicts have an explicit quarantine path and cannot be silently accepted.

### NO-GO conditions

Do not download or implement if any approval above is missing, source rights are unclear, identity reviewer is unappointed, manifest/provenance is incomplete, acceptance criteria fail, ambiguous identities could be merged, the external boundary can write into existing data or API results, or regression comparisons alter protected output. Keep the state pending and request a decision; do not treat lack of an answer as approval.

## 8. Current decision

**Decision: NO-GO for external data acquisition or integration at this time.** This is a governance status pending the approvals listed above, not a rejection of the source assessment. The only authorized next activity under the current task is documentation and regression verification. No download, ingestion, merge, API/UI implementation, analytics change, or dataset change is authorized by this document.

## 9. Regression tests for this document-only change

The governance document is the only file created for this task. No downloader, ingestion script or data-generating command was run.

| Suite | Command | Result |
|---|---|---|
| Project Python | From project root: `python -m pytest -q tests -p no:cacheprovider` using `venv` | **PASS — 113 passed** |
| API | From project root: `python -m pytest -q api\tests -p no:cacheprovider` using `api\.venv` | **PASS — 14 passed** |
| Frontend | From `frontend/`: `npm.cmd test -- --run` | **PASS — 11 passed across 3 test files** |
