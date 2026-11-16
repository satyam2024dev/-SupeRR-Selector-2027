# External Cricket Data Source Rights Review

**Project:** SupeRR Selector Season 2  
**Review date:** 14 November 2026  
**Status:** Preliminary source-rights review for governance planning; **not legal advice and not final legal clearance**.  
**Current authorization:** NO-GO for external data acquisition, download, ingestion, or integration.

## 1. Scope and governance context

This review examines the four source references listed below for a proposed local-only, no-public-redistribution evidence layer covering IPL and men’s T20I, seasons 2022–2026. The project owner approved that governance scope and technical boundaries in principle on 14 November 2026. The owner’s decision explicitly leaves source-specific rights review pending and does not authorize acquisition or implementation.

The review is based on the source pages as accessed on 14 November 2026. Website terms and source notices can change. This document summarizes relevant language to identify issues for a future rights decision; it does not determine the legal effect of any term, establish that a planned act is permitted, or replace advice from qualified counsel.

### References reviewed

1. [Cricsheet licensing](https://cricsheet.org/licensing/)
2. [Open Data Commons Attribution License (ODC-BY) 1.0](https://opendatacommons.org/licenses/by/1.0/) (the page redirects to the full text at `/by/1-0/`)
3. [IPL website Terms & Conditions](https://www.iplt20.com/terms-and-conditions)
4. [IPL Documents](https://www.iplt20.com/documents)

## 2. Preliminary findings

### A. Cricsheet: distinguish the data format and license

Cricsheet’s licensing page says its data uses two licenses: most data is under the Open Data Commons Attribution License, and **XML match data alone** is under the Creative Commons Attribution 4.0 International License. Therefore, the proposed JSON source is expected to fall under ODC-BY 1.0, while XML must not be treated as ODC-BY. The actual archive/member, registers, and any derivative material intended for use must be checked against the live source notice and the exact offered license before acquisition. A format change requires a fresh review. [Cricsheet licensing](https://cricsheet.org/licensing/)

The ODC-BY text grants database rights subject to its conditions. If a database or derivative database is publicly conveyed, the license requires conveying it under ODC-BY, including the license copy or URI with the database and relevant documentation, preserving copyright/database-right/license notices, and putting notices where users can find them if they cannot be embedded. For a produced work publicly used, a notice must make users aware that the content came from the database and that the database is available under ODC-BY. The license text also restricts imposing further restrictions on rights granted by that license. The project’s approved local-only/no-public-redistribution posture avoids an assumption of public distribution, but does **not** establish that every internal use or acquisition method is authorized. Whether any project output counts as a covered produced work or conveyance is a matter for the pending rights review. [ODC-BY 1.0, §§ 4.2–4.4](https://opendatacommons.org/licenses/by/1.0/)

The ODC-BY license is not a blanket clearance of all rights in database contents. The text says it governs rights in the database, not necessarily independent rights in each item, and identifies possible rights outside its scope, including privacy/data-protection, personality/publicity, copyright in individual contents, patents, trademarks, and private contractual rights. It also disclaims warranties as to accuracy, completeness, title and non-infringement. The precise rights attached to any particular match record, person-related information, names, or other content must not be inferred solely from the database license. [ODC-BY 1.0, §§ 2.3–2.4, 7.1](https://opendatacommons.org/licenses/by/1.0/)

**Required before use:** confirm that the exact intended format is Cricsheet JSON (not XML), identify the exact dataset/register items and version, verify the license and source notices applying to each, and obtain a documented rights review for the planned local acquisition, storage, transformation, API access and UI display. Do not describe this review as legal clearance.

### B. Official IPL website and documents

The IPL Terms & Conditions state that website materials—including text, photographs, images, artwork, designs, graphics, logos, video/audio and software—are owned or controlled by BCCI and/or related entities/content suppliers and protected by intellectual-property laws. They describe the website and content as intended solely for users’ personal use, prohibit copying or modifying content and removing proprietary notices, and prohibit reproducing, publishing, distributing, displaying, modifying, creating derivative works from, selling or otherwise exploiting site content or the website without prior written BCCI authorization. They also state that trademarks, service marks and trade names are proprietary unless otherwise stated, with no use without prior written authorization. [IPL Terms & Conditions](https://www.iplt20.com/terms-and-conditions)

The terms do not state an internal-project or local-only exception in the reviewed provisions. **Local-only use must not be assumed to override or satisfy these terms.** The general distinction between recording a factual reference (such as an announcement date or a source URL) and copying protected expression, a document, image, graphic, logo, or other site content does not itself establish permission to extract, retain, transform, or display facts at scale. The exact method and amount of use remain subject to the pending rights review. Do not copy protected website prose or assets into the proposed data layer, API, or UI unless written authorization or another documented basis is confirmed.

The IPL Documents page is a directory of Governing Council, playing-condition, code, image-use, media, ticket, policy and other materials. It is not, by itself, a blanket data license or permission to copy all linked documents. Individual documents may have their own conditions and scope; the site terms also remain relevant. Review the specific document and linked policy applicable to each intended use. The directory’s presence of an official document does not establish that it can be republished or ingested as a dataset. [IPL Documents](https://www.iplt20.com/documents)

The site terms also reserve the ability to change terms and state that website information can be incomplete, inaccurate, or out of date. Preserve the exact source URL and the date checked for any factual reference; independently validate facts when the use requires it. This is a source-quality observation, not permission to copy site content. [IPL Terms & Conditions](https://www.iplt20.com/terms-and-conditions)

**Required before use:** review the current terms and the specific IPL announcement/document; determine whether the intended factual referencing and any automated or manual retrieval, local storage, transformation, API display or UI display are permitted; obtain prior written authorization where required. Do not claim that factual extraction or local-only use is cleared by this preliminary review.

### C. Secondary data providers

No secondary provider is approved by this review. Before using any such source, identify the original data source and redistribution chain, the applicable license/terms for both raw and derived data, and any restrictions on local copying, transformation, retention or display. A provider that redistributes Cricsheet records is not an independent corroborating source. If source lineage or rights are unclear, do not acquire, retain or use the material. This review makes no rights finding for any unnamed provider.

## 3. Operational controls proposed for a later, separately authorized phase

If the pending reviews are completed and the project owner separately authorizes acquisition, the rights/provenance record for each source should include:

- Exact provider, URL, archive/member or official document title/URL, and format.
- Source publication/version date if available, retrieval/check timestamp, and file hash for acquired files.
- License name/version or applicable terms URL, relevant notice text, attribution instructions, and reviewer’s decision/evidence.
- Intended acts reviewed separately: acquisition, local storage, normalization/derivative database creation, internal API access, UI display, and any future redistribution.
- Contents or assets excluded because their rights were not established.
- Change history showing when the source terms or the project’s intended use were reviewed again.

Do not place unreviewed source material in public outputs or use it in any existing ranking or analytical artifact. No data, registers, source documents or screenshots were downloaded or added as part of this review.

## 4. Decision status and blockers

The owner’s 14 November 2026 decision approves the proposed local-only governance scope in principle, but keeps these rights matters **PENDING**:

| Item | Status | Current effect |
|---|---|---|
| Cricsheet ODC-BY 1.0 and attribution review for the exact intended JSON/register items and uses | **PENDING** | No Cricsheet acquisition or integration. No legal clearance is claimed. |
| Official IPL terms and rights review for specific pages/documents and intended use | **PENDING** | No IPL content extraction, copying, storage, or display is authorized by this review. |
| Rights review for each secondary provider, if one is proposed | **PENDING** | No secondary-source use. |
| Owner approval of every measurable acceptance gate in Section 4 of `docs/external_data_governance_decision.md` | **PENDING** | Gates remain proposals; no acceptance threshold is relaxed or approved here. |
| Historical Cricsheet pilot review and documented reuse decision | **PENDING** | Do not treat existing pilot files or code as approved for new acquisition/integration. |
| Baseline protected hashes and regression comparison fixtures | **PENDING** | Must be prepared before implementation is reconsidered. |

**Overall decision remains NO-GO for external data acquisition, download, ingestion, or integration.** This document does not change any historical pilot result, approve a player identity link, authorize a source, or declare legal clearance. Owner appointment as External Player Identity Reviewer does not itself approve identities; future identity decisions still require implemented review controls and evidence.

## 5. Source review record

This is a preliminary reading of publicly available source terms on 14 November 2026. The Cricsheet licensing page, ODC-BY 1.0 text, IPL Terms & Conditions, and IPL Documents directory were reviewed. Terms may change; a later intended use must be assessed against the exact source version and current terms. This record is for project governance and should be referred to qualified legal counsel where a legal determination is needed.
