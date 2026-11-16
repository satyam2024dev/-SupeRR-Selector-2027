# External Cricket Data Governance Approval Draft

**Project:** SupeRR Selector Season 2  
**Status:** **PROPOSED — AWAITING PROJECT OWNER APPROVAL**  
**Decision:** **NO-GO** for external data download, ingestion, or integration until all required approvals and gates below are resolved.  
**Prepared:** 14 November 2026  
**Related records:** `docs/external_data_integration_audit.md`; `docs/external_data_governance_decision.md`

## Purpose

This draft records a proposed scope and implementation posture for a future external cricket evidence layer. It is not an approval, authorization to acquire data, or implementation instruction. The project owner must explicitly approve the applicable proposals. Pending items remain pending unless a later decision record identifies the approver and decision date.

The existing audit found an earlier isolated Cricsheet pilot, but its match and identity results are not production acceptance. The audit reports unresolved player and venue namespaces, incomplete independent scorecard validation, and no accepted production deliveries. This draft does not change or reinterpret those findings.

## Proposed scope — awaiting owner approval

| Topic | Proposed decision | Status |
|---|---|---|
| Competition scope | IPL and **men’s T20I only**. Specific seasons and date range remain to be selected. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Data use | Local-only; no public redistribution of source records or derived external data under this proposal. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Source hierarchy | Cricsheet JSON as the primary candidate for external ball-by-ball evidence; official IPL publications for official IPL announcements and published match facts. Use either subject to source license and rights review. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Secondary sources | Optional discovery or cross-check only after lineage and rights review. A redistribution of Cricsheet is not independent corroboration. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Refresh | Operator-initiated snapshots only. No scheduled/background retrieval under this proposal. Preserve each snapshot and its manifest; do not overwrite prior source records. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Freshness | A view may be labeled “current” only if its source check/retrieval is no more than **30 calendar days** old. Older snapshots must show the last checked date and a stale label. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| API boundary | Localhost-only, read-only, and separately namespaced (proposed `/api/v1/external-cricket`). Existing routes and response schemas remain unchanged. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| UI boundary | Four isolated sections: External Match Centre; Player Evidence Profiles; Performance Trends; Data Provenance Centre. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Implementation approach | Prefer a new, isolated external-data implementation. Before implementation, document a review of the existing `src/cricsheet_pilot.py`, pilot files, manifests and prior reconciliation findings; decide explicitly whether any component can be reused. Do not operate competing downloaders. | **PROPOSED — AWAITING PROJECT OWNER APPROVAL** |
| Existing project outputs | Existing analytics, rankings, eligibility, auction availability overlay, APIs and validated PDF remain unchanged. | **PROPOSED PRESERVATION REQUIREMENT — AWAITING PROJECT OWNER APPROVAL** |

## Proposed source, licensing, and provenance controls

- Cricsheet JSON/registers require a documented license review, including ODC-BY 1.0 attribution and applicable notice obligations. Do not assume other Cricsheet formats share the same license.
- Official IPL site content is subject to its current terms. Retain only necessary factual references and links; do not copy protected material or scrape/redistribute without a rights review.
- Before accepting any source, record provider, canonical URL, source/member identity, publication date when available, retrieval/check timestamp, license and required attribution, schema/version, SHA-256, transformations, and source lineage.
- If applicable rights or attribution remain unclear, the source remains excluded/quarantined.
- Coverage figures are time-sensitive and do not prove that any particular fixture is available or complete. Record the source snapshot and its observed coverage. “Not in this snapshot” must not be described as “match did not occur.”
- Updates, if later approved, are operator-initiated. Each run should produce an immutable manifest and a change report listing added, changed, removed, invalid and quarantined records.

## Proposed player identity and review controls

Local player IDs, Cricsheet registry IDs, and optional third-party identifiers remain separate namespaces. Bare numeric/string equality is not a join rule. Name normalization, exact-name matches, initials, aliases, surname matches and similarity matches may generate candidates only; they do not automatically establish identity.

Every accepted local-to-external player link must have match-specific roster/team/date/competition evidence and an auditable crosswalk entry. Duplicate names, multiple possible IDs, conflicting context, many-to-one mappings, fuzzy or alias-only candidates, and other non-unique cases are **ambiguous** and must receive mandatory human review. An ambiguous, unmatched, or namespace-unverified identity must not be merged, used for linked player metrics, or represented as a local player profile.

**External Player Identity Reviewer: PENDING.** No person or role is appointed by this draft. The project owner must appoint the accountable reviewer before any player identity candidate can be accepted. Do not infer or invent an appointee.

## Decisions that remain pending

The following items are not approved by this draft:

1. **Project-owner approval: PENDING.** This includes approval of the proposed scope, local-only use, source hierarchy, refresh/freshness policy, API/UI boundary and implementation preference.
2. **External Player Identity Reviewer: PENDING.** No reviewer has been named.
3. **Source license and rights review: PENDING.** Review must cover Cricsheet JSON/register terms and the intended use of official IPL material before any acquisition or display.
4. **All measurable acceptance gates: PENDING approval.** Section 4 of `docs/external_data_governance_decision.md` contains proposed numerical and behavioral gates; none is approved until the owner explicitly accepts or revises them.
5. **Season/date scope: PENDING.** Only the competition family proposal (IPL and men’s T20I) is stated here; no seasons or date window are approved.
6. **Existing pilot review: PENDING.** The requested implementation preference is a new isolated implementation, but review of the historical pilot must be documented before selecting any reuse or migration.

No pending item becomes approved through silence, test success, this draft, or a later technical implementation proposal.

## Preservation requirements

If a future implementation is approved, it must remain outside the following protected project elements:

- Existing raw and processed datasets.
- Phase 5A–5H analytics, methodology definitions, eligibility rules and evidence.
- Phase 5G ranks, player IDs, order and stored scores.
- Phase 5H bowling eligibility and evidence.
- Existing API ranking endpoints and response behavior.
- Existing React and Streamlit behavior.
- Auction availability overlay, its data and its rules.
- Validated PDF and its source artifacts.

No external evidence may be silently merged into existing data or used to alter ranking, eligibility, auction status, methodology, existing APIs or the validated PDF. Any later proposal to affect a protected element requires a distinct owner-approved change request and a separate impact and validation review.

## Implementation go/no-go checklist

### GO only after every required item has a recorded approval

- [ ] Project owner approves this proposal, including IPL and men’s T20I scope and the local-only/no-redistribution posture.
- [ ] Project owner selects seasons and date bounds.
- [ ] License and rights review is complete for each source and intended use; attribution text and notices are documented.
- [ ] External Player Identity Reviewer is appointed by the project owner.
- [ ] Project owner approves or revises **all** measurable acceptance gates in `docs/external_data_governance_decision.md`.
- [ ] Operator snapshot, manifest, immutable storage, change report and 30-day freshness process are approved.
- [ ] Existing Cricsheet pilot and prior reconciliation are reviewed and that review is documented; new isolated implementation remains the default unless a separately documented decision says otherwise.
- [ ] API is confirmed localhost-only, read-only and separately namespaced; UI is confirmed limited to the four isolated sections.
- [ ] Baseline comparisons are prepared to demonstrate that protected analytics, rankings, eligibility, datasets, API responses, auction overlay and PDF remain unchanged.
- [ ] Existing and new regression tests pass, including isolation, identity ambiguity, provenance, freshness and no-cross-layer-write checks.

### NO-GO remains in force if

Any approval is missing; rights or attribution are unclear; the reviewer is unappointed; any acceptance gate is unapproved or fails; ambiguous identities could be merged; source provenance is incomplete; the historical pilot review is undocumented; or an external route, UI, process or dataset can change a protected project element.

## Current disposition

**Overall decision: NO-GO.** All items in this document are proposed and awaiting project-owner approval except the explicit pending-status statements, which record that the reviewer, owner approval, rights review and acceptance-gate approval have not been completed. No external data may be downloaded, ingested or integrated under this draft.
