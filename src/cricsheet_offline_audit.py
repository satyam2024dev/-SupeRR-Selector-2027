"""Build local-only Phase 2F cohort and progress artifacts; performs no network I/O."""
from __future__ import annotations

import pandas as pd

from src.cricsheet_pilot import CONTROL_IDS, PILOT_IDS, RAW, REPORTS


def build_offline_progress() -> tuple[pd.DataFrame, str]:
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    balls = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    local_counts = balls.groupby("match_id").size()
    inventory = matches.merge(competitions, on="comp_id", validate="many_to_one")
    inventory["local_delivery_rows"] = inventory.match_id.map(local_counts).fillna(0).astype(int)
    eligible = inventory[
        inventory.match_format.eq("T20I")
        | inventory.comp_name.str.startswith("IPL ", na=False)
    ]
    missing = eligible[eligible.local_delivery_rows.eq(0)]
    candidate_ids = set(missing.match_id.astype(int))
    if len(missing) != 16 or candidate_ids != set(PILOT_IDS[:16]):
        raise ValueError("Local no-delivery inventory differs from configured 16-match recovery cohort")
    if missing.match_id.duplicated().any():
        raise ValueError("Duplicate match IDs in local recovery cohort")

    cohort = missing.sort_values(["match_format", "match_date", "match_id"]).copy()
    cohort["pilot_role"] = "missing_delivery_recovery_candidate"
    cohort["local_delivery_status"] = "no local delivery rows"
    cohort["external_match_status"] = "pending: no network access/download performed"
    cohort["external_delivery_status"] = "pending: no Cricsheet records inspected"
    cohort["reconciliation_decision"] = "pending"
    columns = [
        "match_id", "comp_id", "comp_name", "match_format", "season", "match_date",
        "stage", "home_team_id", "home_team", "away_team_id", "away_team", "venue_id",
        "venue_country", "result", "local_delivery_rows", "pilot_role",
        "local_delivery_status", "external_match_status", "external_delivery_status",
        "reconciliation_decision",
    ]
    REPORTS.mkdir(parents=True, exist_ok=True)
    cohort[columns].to_csv(REPORTS / "cricsheet_pilot_cohort.csv", index=False)
    controls = inventory[inventory.match_id.isin(CONTROL_IDS)].sort_values("match_id")

    report = f"""# Phase 2F Offline Progress — Cricsheet Reconciliation Pilot

## Status

**External reconciliation has not run.** Network access and Cricsheet downloads were deliberately left disabled for this turn. No Cricsheet match or delivery result is asserted. The external match, delivery, player-crosswalk and acceptance outcomes are all **pending**.

## Deterministic local recovery cohort

The official local files were inspected directly (`matches.csv`, `competitions.csv`, and `ball_by_ball.csv`). The eligible scope was IPL competition records and T20I competition records. Exactly **{len(cohort)}** eligible match records have zero local delivery rows. All 16 are included in the recovery cohort; every local result is recorded as Match Abandoned.

| Match ID | Competition | Format | Date | Teams | Venue ID | Local result |
|---:|---|---|---|---|---:|---|
"""
    for row in cohort.itertuples(index=False):
        report += (
            f"| {int(row.match_id)} | {row.comp_name} | {row.match_format} | {row.match_date} "
            f"| {row.home_team} vs {row.away_team} | {row.venue_id} | {row.result} |\n"
        )
    report += f"""

The cohort table is `cricsheet_pilot_cohort.csv`. It contains official identifiers and local metadata only; external statuses are explicitly marked pending. The four configured local-delivery controls remain separate from this 16-match recovery cohort (IDs: {", ".join(map(str, sorted(CONTROL_IDS)))}). Together they form the script's existing 20-match pilot configuration when network access is later available.

Local source inventory: **{len(matches)}** match rows; **{balls.match_id.nunique()}** distinct match IDs with ball-by-ball rows; **{len(balls)}** official delivery rows. These counts describe local source presence only, not Cricsheet overlap.

## Script implementation review

Implemented in `src/cricsheet_pilot.py` but not exercised against Cricsheet in this offline run: ZIP central-directory lookup and selected-member HTTP range retrieval; candidate selection by date and team aliases; metadata checks for date, teams, T20 format and competition family; JSON/local delivery flattening and coordinate comparison; exact-ID register candidate review; Phase 2E match acceptance gate; and reconciliation CSV/report generation. Synthetic fixtures exercise the core matching, comparison, crosswalk ambiguity and decision paths.

Known incomplete or unresolved in the implementation: the official player-ID namespace is undocumented, so register ID matches remain unconfirmed; the official venue is an opaque numeric ID and there is no demonstrated venue crosswalk; innings totals, delivery totals/extras, targets and bowling figures lack independent local validation for most matches; and archive candidate filenames are only a retrieval filter, never proof of match identity. The external execution path and its generated reconciliation outputs remain unverified. The existing report builder must not be read as evidence until a real download and reconciliation run has completed.

## Completed

- Inspected the existing reconciliation script and Phase 2E acceptance requirements.
- Confirmed the 16-match recovery cohort deterministically from local records and checked it against the script's configured candidate IDs.
- Added synthetic tests for metadata matching, delivery run agreement/disagreement, duplicate local and external delivery coordinates, ambiguous player-register IDs, and accepted/rejected/unresolved match decisions.
- Fixed a local comparison bug found by synthetic tests: `compare_deliveries()` attempted to insert a duplicate `match_id` column when local events were present.
- Full suite passed: 34 tests. `compileall -q src tests` completed successfully.
- No official source data was edited; no values were imputed.

## Blocked

- Cricsheet archive-index lookup and retrieval are blocked by the explicit offline-only instruction for this turn.
- Therefore exact/partial/mismatch/unresolved external match and delivery counts cannot be established.
- Player crosswalk results, external file hashes/provenance, and acceptance decisions cannot be established.
- Recovery of the 16 missing local matches and any change in metrics coverage cannot be established.

## Pending

- Fetch the selected JSON records and required Cricsheet registers once network access is available.
- Run match-identity and delivery-level reconciliation against those records.
- Review player ID candidates without using names as join keys.
- Apply the Phase 2E zero-unexplained-difference acceptance gate; reject failed matches.
- Generate final reconciliation reports and quantify accepted coverage change.

## Resume commands

Run from the project root after network access is available:

```powershell
.\\venv\\Scripts\\python.exe -m src.cricsheet_pilot --download
.\\venv\\Scripts\\python.exe -m src.cricsheet_pilot --reconcile
.\\venv\\Scripts\\python.exe -m pytest -q
.\\venv\\Scripts\\python.exe -m compileall -q src tests
```

The download command retrieves selected ZIP members using HTTP ranges and stores selected JSON only under `data/external/cricsheet/pilot/`; the reconciliation command requires those downloaded files and registers. Do not report external results before both commands complete successfully and the produced evidence is reviewed.
"""
    report_path = REPORTS / "cricsheet_pilot_progress.md"
    report_path.write_text(report, encoding="utf-8")
    return cohort, report


if __name__ == "__main__":
    cohort, _ = build_offline_progress()
    print(f"Wrote local-only cohort ({len(cohort)} matches) and progress report under {REPORTS}")
