# External Cricket Data — Clarification Owner Decision Record

**Project:** SupeRR Selector Season 2  
**Owner decision date:** 14 November 2026  
**Decision:** **APPROVED — ALL THREE CLARIFICATIONS**  
**Scope:** The three clarification proposals in Section 3 of `docs/external_data_acceptance_gate_decision.md` only.  
**Overall project status:** **NO-GO for external data acquisition, download, ingestion, and integration.**

## Decision

The project owner approves all three clarifications below as governance requirements. This approval does **not** approve Gate 1 through Gate 12, any source rights, data acquisition or implementation, or any individual player identity link. All original acceptance gate requirements and numeric thresholds remain unchanged and pending separate approval.

## 1. Expected match inventory — APPROVED

Maintain a dated expected match inventory for IPL and men’s T20I, seasons 2022–2026 inclusive. Report expected, available, missing, incomplete and quarantined fixture counts by competition and season. Define mutually exclusive fixture statuses and ensure the counts reconcile to the expected total.

The inventory must make its scope, as-of date/version, source basis, and fixture status definitions auditable. This is a requirement for a future authorized process; this decision creates no inventory, asserts no counts, and authorizes no external data acquisition.

## 2. Accepted player crosswalk evidence — APPROVED

Every accepted player crosswalk must include source evidence, match/player context, reviewer decision, decision reason and crosswalk version. Preserve provider/local ID namespaces and audit information.

Approval of this clarification does **not** approve any individual player identity link. The project owner’s appointment as External Player Identity Reviewer does not itself approve identities. Individual links remain unaccepted until a separately authorized review workflow and its controls are implemented, and the applicable identity acceptance gate is separately approved and passed.

## 3. Freshness timestamps — APPROVED

Track source publication date, last successful retrieval date and last verification date separately. Use successful verification of the specifically identified retrieved snapshot as the controlling freshness timestamp. Failed retrievals and unverified checks must not reset the freshness clock. Preserve the original 30-calendar-day current/stale threshold.

For clarity, the controlling timestamp is the recorded successful verification time for a snapshot that has a specific identity (such as a snapshot/run ID and source hash) and whose retrieval succeeded. The retrieval and verification dates remain separately visible in provenance; the source publication date remains a distinct source attribute. A failed retrieval or a check that does not verify that identified retrieved snapshot cannot advance the controlling timestamp.

This clarification preserves the original requirement: a view labeled “current” must use a controlling source check/retrieval timestamp no older than 30 calendar days; older evidence must be visibly marked stale with its last checked date; snapshot history is never overwritten. This approval does not approve Gate 7 or any data refresh/acquisition.

## Effect on acceptance gates and authorization

- All three clarifications are approved as stated above.
- Gates 1 through 12 in `docs/external_data_acceptance_gate_decision.md` remain **PENDING**. This decision is not approval of any acceptance gate or test result.
- Cricsheet, official IPL and any secondary-provider rights reviews remain pending; no legal clearance is granted.
- Historical Cricsheet pilot review, protected baseline hashes and regression fixtures remain pending.
- No player identity link is accepted by this decision.
- No external data is authorized to be downloaded, ingested, integrated, or used in existing project outputs.

**Overall status remains NO-GO for external data acquisition, download, ingestion, and integration.** A future change to that status requires completion of the pending gates and a separate explicit owner authorization.

## Documentation-only regression verification

| Suite | Result |
|---|---|
| Project Python | **PASS — 113 passed** (`.\venv\Scripts\python.exe -m pytest -q tests -p no:cacheprovider`, project root) |
| API | **PASS — 14 passed** (`.\api\.venv\Scripts\python.exe -m pytest -q api\tests -p no:cacheprovider`, project root) |
| Frontend | **PASS — 11 passed across 3 files** (`npm.cmd test -- --run`, `frontend/`) |

No external data was downloaded or ingested, and no downloader/ingestion process was run. No application code, datasets, analytics, rankings, APIs, UI, auction overlay, or PDF was changed.
