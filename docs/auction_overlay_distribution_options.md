# Auction availability overlay distribution decision

**Decision required before packaging or sharing the availability overlay.** The local file `data/external/ipl_2027_player_availability.csv` is Git-ignored and contains dated source URLs, status assessments, and verification notes. Phase 4 reads it only through the existing read-only API. This change does not modify the file or its ignore rule.

## Options

| Option | Handling | Advantages | Trade-offs |
| --- | --- | --- | --- |
| Keep as local operator-managed input | Each approved analyst receives and updates the file through an existing private channel; it remains outside Git. | Smallest change; preserves the current local-only model and audit fields. | Distribution and version coordination stay manual. |
| Private, access-controlled artifact store | A designated operator publishes immutable, dated snapshots to a restricted organization store; local setup retrieves an explicitly chosen version. | Clear access control and reproducible snapshots without committing player-level source assessments. | Requires an owner, service, retention policy, credentials and an update procedure. |
| Controlled ingestion process | A documented review process writes approved official source evidence into the local overlay; the API continues to read the same schema. | Preserves auditability and leaves the dashboard contract unchanged. | Requires a maintainer and status-review workflow; does not by itself solve distribution. |
| Repository exception | Add a narrowly scoped Git allow rule and commit selected overlay snapshots. | Simple checkout for collaborators. | Makes external status research broadly available to repository readers and creates a version-control maintenance obligation. Not enabled. |

## Current snapshot limits

The snapshot verification date is 2026-11-13. The official auction registration and final register are not present in the project artifacts. The API consequently reports zero confirmed performance-qualified batter targets. “Previous franchise” is historical mapping, not evidence of a 2027 contract. Do not infer registration from a release announcement or an unverified prediction.

## Decision

**Selected: keep the overlay local and operator-managed.** Continue supplying and updating the file through the existing local workflow. Do not add a private artifact store, retrieval automation, or a Git exception under this decision.

The overlay and ignore rule remain unchanged. If the project later needs multi-user distribution, revisit the private artifact store option and identify an owner, access policy, retention policy, and update cadence before implementing it. If the local file is absent, the API should retain its explicit unavailable state; dashboard code must not generate a replacement.
