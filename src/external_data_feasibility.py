"""Generate a read-only assessment of potential external cricket data sources."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
REPORTS = ROOT / "outputs" / "reports"

SOURCE_ROWS = [
    {
        "source": "Cricsheet JSON (recommended candidate)", "source_type": "Public structured ball-by-ball archive",
        "published_coverage": "1,243 IPL matches; 3,649 men's T20Is (site counts on 2026-11-11); 166 T20I matches withheld; all Afghanistan men's matches withheld",
        "field_definitions": "Per delivery: batter/extras/total runs, typed extras, bat/bowler/non-striker, wicket kind/player, ball sequence; innings target/overs, super_over, penalty_runs; match teams/date/outcome",
        "player_identifiers": "Cricsheet registry IDs in match data; people register maps selected BCCI, ESPNcricinfo, Opta, Pulse and other IDs; not all crosswalk IDs exist",
        "licensing_access": "JSON/YAML/CSV under ODC-BY 1.0; attribution and license notice required; public downloadable ZIP; no download performed",
        "reliability": "Structured, documented and revised; source states no warranties; omissions include Afghanistan and other missing matches; match-specific reconciliation still required",
        "compatibility": "High semantic fit for IPL and T20I; format differs from official CSV; team/player names and match IDs require explicit crosswalk; 30 non-IPL domestic T20 matches outside its relevant competition coverage",
        "recommendation": "Proceed to a small isolated match-level reconciliation pilot after provenance/legal review; do not merge yet",
        "source_urls": "https://cricsheet.org/downloads/ | https://cricsheet.org/format/json/ | https://cricsheet.org/register/ | https://cricsheet.org/licensing/",
    },
    {
        "source": "IPL / IPLT20 official Match Centre", "source_type": "Official match scorecards and match pages",
        "published_coverage": "IPL competition; match centre is dynamic and does not publish a bulk archive count on the inspected page",
        "field_definitions": "Scorecard totals and player batting/bowling figures; scorecard pages can support match-total, wickets, extras and overs checks; per-delivery structured export not identified",
        "player_identifiers": "Team/player labels and site match URLs; crosswalk to official competition IDs not documented in page",
        "licensing_access": "Public pages; IPL/BCCI terms limit content to personal use and prohibit reproduction/derivative use without prior written authorization; no open bulk-data license",
        "reliability": "Primary competition publisher; best reference for IPL match totals; dynamic page loading and page availability may complicate reproducibility",
        "compatibility": "High for manual match-level validation of IPL; insufficient demonstrated as a machine-ingest source for per-ball repair",
        "recommendation": "Use selected pages as validation references; obtain permission/vendor access for bulk reuse",
        "source_urls": "https://www.iplt20.com/matches/More/match-details | https://www.iplt20.com/terms-and-conditions",
    },
    {
        "source": "BCCI men's match archive", "source_type": "Official India international/domestic match archive",
        "published_coverage": "India men's archive offers format filters including T20I and T20; not a global T20I archive",
        "field_definitions": "Match pages/scorecards provide official match results and innings/batting/bowling totals where published; no bulk delivery schema identified",
        "player_identifiers": "BCCI player pages/IDs may be present; not proven equivalent to competition dataset IDs",
        "licensing_access": "Public archive pages; BCCI terms limit use to personal/non-commercial and prohibit copying, bulk use and automated scraping without permission; no open bulk-data license",
        "reliability": "Primary authority for covered India matches; cannot validate all 482 supplied T20Is",
        "compatibility": "Strong manual validation for India matches, weak as a complete programmatic supplement",
        "recommendation": "Use for independent India-match scorecard checks only, subject to permitted use",
        "source_urls": "https://scores-bcci.epicon.in/international/men/archive | https://www.bcci.tv/terms-and-conditions",
    },
    {
        "source": "ESPNcricinfo scorecards", "source_type": "Publicly viewable third-party scorecard archive",
        "published_coverage": "Broad international and franchise archive; no independently documented count for this exact sample reviewed",
        "field_definitions": "Detailed batting/bowling innings scorecards and many ball-commentary pages; structured fields/API availability is not an officially documented open feed",
        "player_identifiers": "ESPNcricinfo player IDs; Cricsheet register includes some key_cricinfo identifiers, but coverage is not universal",
        "licensing_access": "Terms of use apply; no open bulk-data license identified. Public visibility is not permission for bulk extraction or redistribution",
        "reliability": "Useful secondary cross-check and broad archive; scorecards can be revised and commentary coverage varies",
        "compatibility": "Potential manual scorecard corroboration; do not use as automated bulk supplement absent permission and a stable documented interface",
        "recommendation": "Reference-only fallback where official scorecards are unavailable; no scraping/ingestion authorized by this audit",
        "source_urls": "https://www.espncricinfo.com/ | https://img.cricinfo.com/db/MANAGEMENT/TERMS_USE.html | https://cricsheet.org/register/",
    },
]


def inspect_local_scope(matches: pd.DataFrame, competitions: pd.DataFrame, balls: pd.DataFrame) -> dict[str, object]:
    """Calculate eligible match scope and a conservative Cricsheet coverage ceiling."""
    joined = matches.merge(competitions[["comp_id", "match_format", "comp_name", "season"]], on="comp_id", how="left", validate="many_to_one")
    ball_match_ids = set(balls["match_id"].dropna().astype(int))
    joined["has_ball_by_ball"] = joined["match_id"].astype(int).isin(ball_match_ids)
    is_ipl = joined["comp_name"].astype("string").str.match(r"^IPL\s", case=False, na=False)
    is_t20i = joined["match_format"].eq("T20I")
    is_afghan = joined["home_team"].astype("string").str.contains("Afghanistan", case=False, na=False) | joined["away_team"].astype("string").str.contains("Afghanistan", case=False, na=False)
    cricsheet_family = is_ipl | is_t20i
    candidate = joined[cricsheet_family]
    potentially_available = candidate[~(is_t20i & is_afghan).loc[candidate.index]]
    potential_match_ids = set(potentially_available.match_id.astype(int))
    return {
        "match_records": len(joined), "matches_with_ball_by_ball": int(joined.has_ball_by_ball.sum()),
        "matches_without_ball_by_ball": int((~joined.has_ball_by_ball).sum()),
        "ipl_matches": int(is_ipl.sum()), "ipl_matches_with_ball_by_ball": int(joined.loc[is_ipl, "has_ball_by_ball"].sum()),
        "t20i_matches": int(is_t20i.sum()), "t20i_matches_with_ball_by_ball": int(joined.loc[is_t20i, "has_ball_by_ball"].sum()),
        "t20i_matches_involving_afghanistan": int((is_t20i & is_afghan).sum()),
        "cricsheet_family_matches": int(cricsheet_family.sum()),
        "potentially_covered_matches_upper_bound": len(potential_match_ids),
        "potentially_covered_matches_already_have_ball_by_ball": int(potentially_available.has_ball_by_ball.sum()),
        "potentially_covered_matches_missing_ball_by_ball": int((~potentially_available.has_ball_by_ball).sum()),
        "potentially_outside_source_family_matches": int((~cricsheet_family).sum()),
        "afghanistan_t20i_matches_excluded_from_ceiling": int((is_t20i & is_afghan).sum()),
        "potentially_coverable_regulation_innings_upper_bound": 2 * len(potential_match_ids),
        "final_score_known_innings_before": 18,
        "final_score_known_innings_total": 1724,
    }


def run_external_data_audit() -> dict[str, object]:
    """Write feasibility artifacts using local metadata and documented sources only."""
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    balls = pd.read_csv(RAW / "ball_by_ball.csv", usecols=["match_id"], low_memory=False)
    scope = inspect_local_scope(matches, competitions, balls)
    REPORTS.mkdir(parents=True, exist_ok=True)
    comparison = pd.DataFrame(SOURCE_ROWS)
    comparison["local_scope_reference_not_confirmed_external_overlap"] = [
        f"at most {scope['potentially_covered_matches_upper_bound']} eligible IPL/T20I records",
        f"{scope['ipl_matches']} IPL records", "India men's T20I subset only; exact count not used here",
        f"{scope['match_records']} record pool; source-level match coverage not measured"]
    comparison.to_csv(REPORTS / "external_source_comparison.csv", index=False)
    (REPORTS / "reconciliation_requirements.md").write_text(_reconciliation_markdown(), encoding="utf-8")
    (REPORTS / "external_data_feasibility.md").write_text(_report_markdown(scope), encoding="utf-8")
    return {"scope": scope, "comparison": str(REPORTS / "external_source_comparison.csv"),
            "report": str(REPORTS / "external_data_feasibility.md"),
            "reconciliation": str(REPORTS / "reconciliation_requirements.md"), "external_data_downloaded": False}


def _report_markdown(s: dict[str, object]) -> str:
    return f"""# Phase 2E — External Data Feasibility Audit

**Research checked:** 2026-11-11. No external files were downloaded, copied, merged, or used to fill official values. Candidate sources remain external to `data/raw/` and `data/processed/`.

## Finding

External supplementation is **technically feasible and worth a controlled, match-level pilot**, with Cricsheet JSON as the recommended candidate for structured IPL and men's T20I event data. Do not ingest or merge it before reconciliation and licensing/provenance checks. Official IPL/BCCI scorecards are stronger as primary validation references, but their inspected public pages do not provide a documented bulk open-data feed. Player IDs are not assumed compatible.

## Missing fields

| Objective | Needed fields | Current gap | Cricsheet JSON candidate |
| --- | --- | --- | --- |
| Batter runs and balls faced | Batter-attributed runs per delivery; explicit batter faced; delivery faced/validity or typed wides/no-balls | `runs` is only provisional on ordinary rows; extras events affect attribution and balls faced | `runs.batter`, batter name, typed `extras.wides` / `extras.noballs`; validate all edge cases and batting scorecard totals |
| Bowler runs conceded and legal balls | Bowler-charged runs per event or complete extras taxonomy; valid-ball indicator or typed wide/no-ball | No conceded-runs field; legal status uncertain for 266 events; unknown extras meanings | `runs.total`, type-wise extras, bowler name and delivery numbering; derive bowler charge only through explicit rules and validate against scorecard bowling figures |
| Innings totals and final scores | Per-delivery team total, innings penalties, wickets, innings-end/outcome | No innings scorecard totals; 18/1,724 final innings scores known | `runs.total`, wicket arrays, innings `penalty_runs`, match outcome; sum and reconcile rather than assume completeness |
| Target and revised innings allowance | Target runs, overs/deliveries, interruption/revision metadata | `revised_target` exists for only 23 match rows; revised-over semantics are inferred, not documented | Innings `target.runs` and `target.overs`; reconcile revised values and end conditions |
| Reliable match-state reconstruction | Ordered event, total runs, legal-ball status, wickets, target, innings/super-over/termination metadata | Score uncertainty propagates after extras; 321 delivery rows currently have fully known chase state | JSON has explicit event totals, typed extras, wicket detail, innings target, `super_over`, penalty runs, dates/teams/outcome; still requires match-event reconciliation |

Other current coverage reference: the Phase 2D archive has 200,999 deliveries, 883 match records, 867 matches with delivery rows, and 1,724 innings; 321 rows meet the verified chase-state definition. The Phase 2B.1 score audit found no safe global formula for the proprietary extras columns.

## Source coverage and realistic gain bounds

Local match inventory yields {s['match_records']} matches: {s['ipl_matches']} IPL matches (2022–2026), {s['t20i_matches']} T20Is, and 30 T20 matches outside IPL. The delivery file contains {s['matches_with_ball_by_ball']} match IDs and omits {s['matches_without_ball_by_ball']} match records. Of these, {s['ipl_matches_with_ball_by_ball']}/{s['ipl_matches']} IPL matches and {s['t20i_matches_with_ball_by_ball']}/{s['t20i_matches']} T20Is have delivery rows. Fifty-three supplied T20Is involve Afghanistan; Cricsheet states Afghanistan men's matches are withheld.

Cricsheet currently lists 1,243 IPL and 3,649 men's T20I matches, but these counts are not an exact overlap manifest for the supplied sample. Based on competition family and the documented Afghanistan gap, at most **{s['potentially_covered_matches_upper_bound']} local matches** ({s['potentially_covered_matches_already_have_ball_by_ball']} already have local deliveries; **{s['potentially_covered_matches_missing_ball_by_ball']} are candidates for missing-match recovery**) fall within the source's stated scope. Up to {s['potentially_coverable_regulation_innings_upper_bound']} first/second regulation innings could therefore have candidate external coverage if every eligible match is actually present (Super Overs may add innings); this is an upper bound, not observed recovery. Exact potential recovery of pressure states among existing matches cannot be quantified without the match manifest and acceptance testing. The 16 missing local delivery matches are all IPL/T20I and outside the Afghanistan exclusion, so they are plausible recovery candidates, not guaranteed recoveries.

The outer limit is useful: the source covers a large share of the archive's two main competition families, but cannot supply the 53 Afghanistan T20Is or the 30 non-IPL T20 matches. This scope count does not establish that a specific match file exists or matches the official event stream. Match-by-match overlap, coverage of rain-affected games, Super Overs and corrected/revised records remains to be checked.

## Source comparison

See `external_source_comparison.csv` for the source-by-source comparison of coverage, field definitions, player IDs, licensing/access, reliability and compatibility. The short assessment is:

1. **Cricsheet JSON:** strongest practical candidate. It explicitly separates batter, extras and total delivery runs; documents extras subtypes, wickets, targets and Super Overs; and offers a people register with selected external IDs. ODC-BY 1.0 permits adaptation with attribution and license notices. Gaps and no-warranty language mean event reconciliation remains mandatory.
2. **Official IPL Match Centre and BCCI archive:** primary authorities for their respective scorecards, useful for validation. The BCCI terms referenced by IPLT20 limit use to personal viewing and prohibit reproduction/derivative use without prior written authorization; BCCI's general terms also restrict copying, automated scraping and use as a substitute. No bulk reuse license or machine-readable complete event feed was established here.
3. **ESPNcricinfo:** useful broad scorecard cross-check, but public viewing does not grant bulk reuse. No open license/stable official bulk schema was established. Do not scrape as part of this work.

## Compatibility and player identity

Cricsheet uses its own IDs and a people register that contains selected external source IDs (including BCCI, ESPNcricinfo, Opta and Pulse). Its register explicitly warns that not every ID is populated and names are not unique. The official competition CSV does not document the origin/system of `player_id`. Therefore no ID namespace match is assumed. Use exact external-ID joins only after confirming the official ID system; otherwise require a reviewed match-roster crosswalk with team and date context. Never auto-join by display name alone.

## Reconciliation and acceptance

Before any values are accepted, follow `reconciliation_requirements.md`. The procedure isolates source files, matches fixtures by date/teams/competition/venue, maps player IDs, then compares delivery sequence, batter runs, extras components, total runs, legality, wickets, innings totals, targets, bowling figures and result. A match is accepted only if every required field reconciles or every exception is documented and approved. Preserve both source values and provenance; rejection means quarantine, not repair by guess.

## Recommendation

Proceed with a **small Cricsheet JSON reconciliation pilot**, first on a stratified set of completed IPL and T20I fixtures that includes ordinary matches, wides/no-balls/byes/leg-byes, DLS/revised targets, all-out/short innings, and Super Overs. Use official IPL/BCCI scorecards as the primary total checks for fixtures they cover. Do not bulk merge any external data until legal/provenance requirements, exact match overlap, ID crosswalk, and zero-unexplained-difference acceptance criteria are satisfied. Keep the source and derived reconciliation tables under a separate `data/external/` area with immutable checksums and attribution.

## Sources

- Cricsheet downloads and current coverage: https://cricsheet.org/downloads/
- Cricsheet JSON field definitions: https://cricsheet.org/format/json/
- Cricsheet format overview: https://cricsheet.org/format/
- Cricsheet People Register identifiers and limitations: https://cricsheet.org/register/
- Cricsheet licensing (ODC-BY for JSON/YAML/CSV): https://cricsheet.org/licensing/
- IPL official Match Centre: https://www.iplt20.com/matches/More/match-details
- BCCI men's archive: https://scores-bcci.epicon.in/international/men/archive
- ESPNcricinfo terms of use: https://img.cricinfo.com/db/MANAGEMENT/TERMS_USE.html

```powershell
.\\venv\\Scripts\\python.exe -m src.external_data_feasibility
```
"""


def _reconciliation_markdown() -> str:
    return """# External Match-Level Reconciliation Requirements

## 1. Source isolation and provenance

- Store candidate files only under `data/external/<provider>/<release>/`; never in `data/raw/` and never alongside the official file with the same basename.
- Record provider, exact download URL, retrieval time, match-format subset, data/schema version, embedded revision, license/attribution text, file size and SHA-256 for each artifact.
- Preserve compressed original bytes as read-only. Create parsed/normalized derivatives separately and carry `source_provider`, `source_match_key`, source file hash and delivery key on every row.
- No network download or merge occurs until separately authorized and licensing/access terms are reviewed.

## 2. Match identity crosswalk

1. Candidate match key: format + calendar date + canonicalized two team identities + competition/event + venue where available.
2. Require exactly one match candidate. If doubleheaders, date rollover, neutral venue, renamed franchise, tournament-stage ambiguity or multiple candidates prevent a unique match, quarantine for manual review.
3. Keep `official_match_id` and external match identifier in separate columns. Never replace one with the other.
4. Document team aliases in a reviewed mapping table. No fuzzy team-name matching without a human-approved alias entry.

## 3. Player identity crosswalk

- First establish the source system for official `player_id`; the current official schema does not document it.
- Prefer exact external provider IDs in a published register and compare against match roster/team/date.
- Otherwise require manual review using full name/known variants, team, match date and roster. A name-only join is prohibited.
- Record one-to-one, one-to-many, unresolved and rejected mappings; unresolved player identity blocks player metric acceptance for affected rows.

## 4. Delivery alignment and field checks

Align within each unique match and innings by ordered event stream; do not use `innings_ball_num` as legal-ball number. Preserve illegal deliveries and repeated ball labels. Handle super overs as distinct innings and detect provider-specific labels/sequence conventions.

For each aligned row, compare:

| Official event field | External evidence required | Acceptance check |
| --- | --- | --- |
| Batter / non-striker / bowler | Explicit batter, non-striker, bowler identity | Crosswalked IDs agree; otherwise manually resolved |
| Batter runs | Per-delivery batter-run amount | Exact equality; boundary/run-out edge cases explained |
| Team total runs | Per-delivery total and extras by subtype | Exact event total equality and `batter + extras = total` for external rows |
| Extras | Wide, no-ball, bye, leg-bye, penalty components | Per-type match; do not infer amount from a category label |
| Legal-ball status | Explicit validity or sufficient typed events | Exact per-innings legal-ball totals and event sequence; exceptions documented |
| Wickets | Dismissal kind and dismissed player | Exact event/wicket count and identity; bowler credit by dismissal rules |
| Innings totals | Delivery totals plus pre/post-innings penalties | Exact published innings total, wickets, overs and extras |
| Chase target | Revised target and available overs/deliveries | Match/innings target and resource allowance agree with official metadata |
| Match outcome | Winner/result/margin | Consistent with official result, accounting for ties/no-results/super overs |

## 5. Match acceptance gate

A match may enter a validated supplemental table only when the match identity is unique, all player identities used by the row are resolved, every delivery aligns, score components and wickets match row by row, legal-ball counts and innings totals reconcile, target/overs and match result agree, and all exceptions have a written explanation. For a critical field, unexplained mismatch tolerance is **zero**. Partial matches may be accepted only field-by-field with an explicit accepted-field list; they cannot be used for fields that failed validation.

Before any pressure-state use, compare pre-delivery score/wicket/balls/target states for every event in the selected innings against an independent official scorecard and the external event stream. Validate first innings, chase, interruption/revised target, early finish/all out, super over, and incomplete/no-result cases separately. Do not fill missing source values from end-of-innings totals because totals cannot locate the missing run on a delivery.

## 6. Storage, merge and audit controls

- Keep official columns immutable; produce an external-only candidate table with separate suffixed fields and reconciliation status.
- Only accepted per-field values may be exposed downstream. Preserve `official_value`, `external_value`, `accepted_value`, `acceptance_reason`, `source_url`, file hash, match key, player crosswalk version and reviewer.
- Report counts of candidate, uniquely matched, accepted, quarantined, rejected and unmatched matches/deliveries; calculate coverage before/after using identical denominators and definitions.
- Maintain a holdout sample not used to develop mappings or rules. Re-run automated checks whenever provider revision changes.
- Include attribution and ODC-BY 1.0 license notice wherever Cricsheet data or adapted outputs are distributed; verify whether competition-use conditions impose additional restrictions.
"""


if __name__ == "__main__":
    import json
    print(json.dumps(run_external_data_audit(), indent=2, default=str))
