# External Cricket Data Governance — Owner Decision Record

**Project:** SupeRR Selector Season 2  
**Decision date supplied by project owner:** 14 November 2026  
**Record status:** Governance scope and technical boundaries approved in principle; acquisition and implementation remain not approved.  
**Overall decision:** **NO-GO for external data acquisition, download, ingestion, or integration.**

## 1. Decision authority and scope

The project owner supplied the decisions recorded below for this decision record, dated 14 November 2026. The project owner approves the proposed governance scope and technical boundaries **in principle**. This approval is limited to the governance direction and does not authorize external data acquisition or implementation. It does not close any pending rights, acceptance, pilot-review, or baseline-validation item.

This record is to be read with:

- `docs/external_data_integration_audit.md`
- `docs/external_data_governance_decision.md`
- `docs/external_data_governance_approval_draft.md`

Where a proposal is approved below but a related gate is explicitly pending in Section 4, the pending gate remains a blocker. This record does not revise historical pilot findings.

## 2. Decisions supplied by the project owner

| Decision | Owner decision | Status / boundary |
|---|---|---|
| Project-owner approval | Approves the proposed governance scope and technical boundaries in principle. | **APPROVED — IN PRINCIPLE.** This is not approval to acquire or integrate data. |
| Competition scope | IPL and men’s T20I only. | **APPROVED.** |
| Season range | 2022–2026 inclusive. | **APPROVED.** This defines intended scope, not source completeness or coverage. |
| Data usage | Local-only; no public redistribution. | **APPROVED.** Subject to the pending source-specific license and rights reviews below. |
| Source hierarchy | Cricsheet JSON is the primary candidate for ball-by-ball evidence; official IPL publications are the authority for official IPL announcements and published match facts. | **APPROVED IN PRINCIPLE.** Use remains subject to pending license and rights review. |
| Refresh process | Operator-initiated snapshots only. | **APPROVED.** No automated/background refresh is authorized. |
| Freshness | A view may be labeled “current” only when the source check/retrieval is no more than 30 calendar days old. | **APPROVED.** Older snapshots must show the check date and be labeled stale. |
| API boundary | Localhost-only, read-only, separately namespaced. | **APPROVED IN PRINCIPLE.** No API implementation is authorized by this record. |
| UI boundary | Four isolated external sections: External Match Centre; Player Evidence Profiles; Performance Trends; Data Provenance Centre. | **APPROVED IN PRINCIPLE.** No UI implementation is authorized by this record. |
| Implementation preference | Prefer a new isolated external-data implementation, subject to review of the historical Cricsheet pilot and a documented reuse decision. | **APPROVED AS PREFERENCE.** Pilot review and reuse decision remain pending; no implementation is authorized. |
| Protected project outputs | Existing project analytics, datasets, rankings, eligibility, auction overlay, API behavior and validated PDF remain protected and unchanged. | **APPROVED PRESERVATION REQUIREMENT.** |

## 3. External Player Identity Reviewer appointment

**Role:** External Player Identity Reviewer.  
**Appointment:** The project owner appoints themself to this role.  
**Recorded role identity:** **Project owner / self-appointed reviewer.** No separate person, name, or credential is assigned by this record.

The appointment establishes responsibility for future human identity review only. It does **not** approve any player identity candidate or crosswalk entry. No identity link may be accepted until the review process, evidence requirements, audit trail, and acceptance controls are implemented and the applicable acceptance gates are approved. Ambiguous identity matches remain blocked pending human review; unmatched and namespace-unverified identities remain unmatched/unverified.

## 4. Explicitly pending approvals and blockers

The following remain **PENDING**. They are not treated as approved or complete by the decisions in Section 2.

| Pending item | Status | Required next evidence/decision |
|---|---|---|
| Cricsheet ODC-BY 1.0 license and attribution review for intended local use | **PENDING** | Document review of the full license, source notices, attribution wording, and intended acquisition/storage/display. No legal clearance is claimed. |
| Official IPL site terms and rights review | **PENDING** | Review current terms for the proposed factual references and intended local use. No legal clearance is claimed. |
| Rights review for any secondary provider | **PENDING** | Review source lineage, license/terms, and intended use before consulting or retaining secondary-provider material. A Cricsheet redistribution is not independent evidence. |
| Project-owner approval of every measurable acceptance gate in Section 4 of `docs/external_data_governance_decision.md` | **PENDING** | The project owner must explicitly accept or revise every gate. No gate is approved by this record. |
| Historical Cricsheet pilot review and documented reuse decision | **PENDING** | Review the existing pilot files and versioned reconciliation findings; document whether any component is reusable. New isolated implementation remains the preference pending that review. |
| Baseline protected hashes and regression comparison fixtures | **PENDING** | Capture and retain before any implementation; cover protected data/artifacts, Phase 5G ranks/IDs/scores, Phase 5H evidence, API behavior, overlay and validated PDF. |

Prior pilot findings remain as reported in the audit and its referenced reports, including unresolved/rejected cases and the distinction between report versions. This decision does not reclassify any match, delivery, player identity, or statistic as accepted.

## 5. Preservation requirements

The owner-approved governance boundary requires that the following remain unchanged by any future external-data work unless a separate explicit change request is approved:

- Existing raw and processed datasets.
- Existing analytics and methodology, including Phase 5A–5H.
- Phase 5G rankings, player IDs, order, and stored scores.
- Eligibility rules, thresholds, and evidence.
- Phase 5H bowling eligibility and evidence.
- Existing API endpoints and response behavior.
- Existing React and Streamlit application behavior.
- Auction availability overlay, records, classifications, and rules.
- Validated PDF report and its source artifacts.

Any future external-data store, processing, API and UI must remain separately namespaced. External values must not be written into existing datasets, used to change an existing ranking or eligibility result, or silently alter API/UI/PDF behavior. A future proposal to use external evidence in a protected output requires a separate owner decision, impact audit, reproducibility checks, and revalidation.

## 6. Status distinction

**Approved in principle:** governance scope and technical boundaries listed in Section 2, subject to the explicit pending gates in Section 4.

**Not approved:** external data acquisition, download, ingestion, processing, acceptance, API implementation, UI implementation, or integration with existing project analytics.

**Overall decision remains: NO-GO for external data acquisition, download, ingestion, or integration.** Owner approval of governance direction does not override pending rights reviews, acceptance-gate approval, historical pilot review, or baseline preparation. The reviewer appointment does not authorize identity merges or accept any player links.

## 7. Go/no-go checklist

### Required before any acquisition or implementation can be reconsidered

- [ ] Cricsheet ODC-BY 1.0 license/attribution review for intended use documented.
- [ ] Official IPL site terms and rights review documented.
- [ ] Rights review documented for every secondary provider, if any is proposed.
- [ ] Project owner has explicitly approved every measurable acceptance gate in Section 4 of `docs/external_data_governance_decision.md`.
- [ ] Historical Cricsheet pilot and prior report versions reviewed; reuse decision documented.
- [ ] Baseline protected hashes and regression comparison fixtures captured and stored.
- [ ] Identity-review workflow, evidence requirements, audit trail, and controls are implemented and validated before any identity link is accepted.
- [ ] A separate implementation authorization is recorded after all preceding gates are satisfied.

Until every applicable item is complete and a separate authorization is recorded, retain **NO-GO**. No unresolved item may be inferred as complete from this decision record.

## 8. Verification record

This document was checked against the three related governance documents listed in Section 1. It records the owner-supplied decisions without changing or superseding the audit’s historical findings. In particular, it preserves the existing distinction between a historical pilot observation and accepted production data, and it retains all explicitly pending blockers above.

No external data was downloaded or ingested, and no downloader or ingestion process was run while preparing this record. No application code, analytics, dataset, ranking, API, UI, auction overlay, or PDF was modified.

### Regression suites

| Suite | Baseline | Result |
|---|---:|---|
| Project Python tests | 113 | **PASS — 113 passed** (`.\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider`, project root) |
| API tests | 14 | **PASS — 14 passed** (`.\api\.venv\Scripts\python.exe -m pytest -q api\tests -p no:cacheprovider`, project root) |
| Frontend tests | 11 across 3 files | **PASS — 11 passed across 3 files** (`npm.cmd test -- --run`, `frontend/`) |
