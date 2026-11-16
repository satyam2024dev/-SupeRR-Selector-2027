"""Phase 4E evidence-only recovery inventory for the confirmed IPL/T20I scope.

No source values are repaired here. The module groups unresolved event rows and
attaches existing pilot evidence so recovery work can be prioritized without
promoting candidates into accepted data.
"""
from __future__ import annotations

from pathlib import Path
import json

import pandas as pd

from src.confirmed_scope_coverage import RAW, REPORTS, filter_confirmed_scope
from src.cricket_data_validation import normalize_delivery_events

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUT_QUEUE = REPORTS / "phase4e_match_recovery_queue.csv"

SOURCE_FIELDS = [
    "match_id", "comp_id", "innings", "overid", "over_ball_num",
    "innings_ball_num", "runs", "extras_type", "extras1_runs",
    "extras_2_runs", "is_four", "is_six", "is_wicket", "dismissal_type",
    "dismissed_player_id", "striker_id", "non_striker_id", "bowler_id",
    "legal_delivery", "legal_delivery_status",
]


def unresolved_event_groups(deliveries: pd.DataFrame, matches: pd.DataFrame,
                            competitions: pd.DataFrame) -> pd.DataFrame:
    """Return one row per confirmed-scope match/innings/extra-label group.

    Group counts are computed only from rows the existing conservative scoring
    normalizer marks unresolved. Values are descriptive evidence, not corrections.
    """
    scoped = filter_confirmed_scope(deliveries, matches, competitions)
    normalized = normalize_delivery_events(scoped)
    unresolved = normalized.loc[normalized.team_runs_delta.isna()].copy()
    unresolved["extras_type_group"] = unresolved.extras_type.fillna("(null)").astype(str)
    available = [name for name in SOURCE_FIELDS if name in unresolved.columns]
    keys = ["analysis_format", "comp_id", "comp_name", "season", "match_date",
            "match_id", "innings", "extras_type_group"]
    grouped = (unresolved.groupby(keys, dropna=False, sort=True)
               .agg(event_count=("match_id", "size"),
                    observed_runs_sum=("runs", "sum"),
                    extras2_nonzero_events=("extras_2_runs", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).ne(0).sum())),
                    wicket_flag_events=("is_wicket", lambda s: int(s.fillna(False).astype(bool).sum())),
                    legal_true_events=("legal_delivery", lambda s: int(s.fillna(False).astype(bool).sum())),
                    legal_unknown_events=("legal_delivery", lambda s: int(s.isna().sum())))
               .reset_index())
    grouped["available_source_fields"] = ";".join(available)
    grouped["unresolved_semantics"] = grouped.extras_type_group.map(
        lambda t: "typed amount and team-run increment undocumented; source values retained" if t != "(null)"
        else "null extra label; nonzero secondary amount and team-run meaning require definition")
    grouped["queue_row_type"] = "unresolved_event_group"
    grouped["source_scope"] = "official canonical delivery feed"
    grouped["acceptance_status"] = "not_applicable_local_source_not_external_acceptance"
    grouped["recovery_action"] = "request documented total_runs or typed extra amounts and legal flag; validate against full innings package"
    return grouped


def pilot_recovery_rows(acceptance: pd.DataFrame,
                        reconciliation: pd.DataFrame) -> pd.DataFrame:
    """Flatten the 20-match Phase 2F pilot into auditable recovery rows."""
    merged = acceptance.merge(
        reconciliation[["official_match_id", "match_reconciliation_status",
                       "delivery_exact_count", "delivery_partial_count",
                       "delivery_mismatch_count", "delivery_unresolved_count",
                       "player_identity_status", "venue_identity_status",
                       "total_runs_status", "legal_balls_status",
                       "innings_totals_status", "target_status",
                       "bowling_figures_status", "result_status"]],
        on="official_match_id", how="left", validate="one_to_one")
    fields = ["official_match_id", "competition", "format", "season", "match_date",
              "home_team", "away_team", "pilot_role", "external_file_status",
              "external_match_id", "external_filename", "source_url", "source_sha256",
              "acceptance_status", "blocking_checks", "match_reconciliation_status",
              "delivery_exact_count", "delivery_partial_count", "delivery_mismatch_count",
              "delivery_unresolved_count", "player_identity_status", "venue_identity_status",
              "total_runs_status", "legal_balls_status", "innings_totals_status",
              "target_status", "bowling_figures_status", "result_status"]
    out = merged[fields].copy()
    out["queue_row_type"] = "pilot_match"
    out["action_priority"] = out.pilot_role.map({"control": "P1: finish downloaded controls", "missing_delivery_candidate": "P3: resolve archive-index/coverage first"})
    out["priority_basis"] = out.pilot_role.map({
        "control": "Four source files already exist; 965 aligned events and scorecard research make these the lowest-cost validation cases, but all remain unresolved.",
        "missing_delivery_candidate": "Sixteen locally abandoned/no-delivery fixtures have no indexed Cricsheet JSON candidate; confirm whether any delivery package exists before scorecard work."})
    out["recovery_action"] = out.apply(_pilot_action, axis=1)
    out["conditional_coverage_gain"] = "not counted; unresolved until every existing gate passes"
    return out


def _pilot_action(row: pd.Series) -> str:
    if row.pilot_role == "control":
        return "Resolve exact blockers listed in blocking_checks; retain source hashes; reconcile scoring, innings endpoints, targets, player/venue IDs and result."
    return "Ask organizer/provider whether a complete delivery record exists; if match was truly abandoned without deliveries, no pressure rows can be recovered."


def build_recovery_queue(deliveries: pd.DataFrame, matches: pd.DataFrame,
                         competitions: pd.DataFrame, acceptance: pd.DataFrame,
                         reconciliation: pd.DataFrame) -> pd.DataFrame:
    """Combine event-level local gaps and separate pilot-match recovery actions."""
    event_rows = unresolved_event_groups(deliveries, matches, competitions)
    match_rows = pilot_recovery_rows(acceptance, reconciliation)
    # Preserve a common, explicit schema while never treating the two row grains as equal.
    all_cols = list(dict.fromkeys([*event_rows.columns, *match_rows.columns]))
    return pd.concat([event_rows.reindex(columns=all_cols),
                      match_rows.reindex(columns=all_cols)], ignore_index=True)


def create_recovery_queue() -> pd.DataFrame:
    """Read canonical/processed inputs and write the Phase 4E audit CSV."""
    deliveries = pd.read_csv(RAW / "ball_by_ball.csv")
    matches = pd.read_csv(RAW / "matches.csv")
    competitions = pd.read_csv(RAW / "competitions.csv")
    acceptance = pd.read_csv(REPORTS / "match_acceptance_status.csv")
    reconciliation = pd.read_csv(REPORTS / "match_reconciliation.csv")
    queue = build_recovery_queue(deliveries, matches, competitions, acceptance, reconciliation)
    OUTPUT_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(OUTPUT_QUEUE, index=False)
    return queue


def write_reports() -> None:
    """Regenerate the queue and concise evidence reports from existing artifacts."""
    queue = create_recovery_queue()
    scope = filter_confirmed_scope(
        pd.read_csv(PROCESSED / "pressure_research_deliveries.csv.gz"),
        pd.read_csv(RAW / "matches.csv"), pd.read_csv(RAW / "competitions.csv"))
    normal = normalize_delivery_events(scope)
    unresolved = normal.loc[normal.team_runs_delta.isna()]
    event_lines = ["| Format | Event type | Events | Matches | Match-innings |", "|---|---|---:|---:|---:|"]
    for (fmt, etype), group in unresolved.assign(event_type=unresolved.extras_type.fillna("(null)")).groupby(["analysis_format", "event_type"], sort=True):
        event_lines.append(f"| {fmt} | {etype} | {len(group)} | {group.match_id.nunique()} | {group[['match_id','innings']].drop_duplicates().shape[0]} |")
    match_innings = unresolved[["analysis_format", "comp_name", "comp_id", "match_id", "innings"]].drop_duplicates()
    totals = unresolved.groupby("analysis_format").size().to_dict()
    event_rows = queue.loc[queue.queue_row_type.eq("unresolved_event_group")]
    event_csv_count = int(event_rows.event_count.sum())

    status = pd.read_csv(REPORTS / "match_acceptance_status.csv")
    rec = pd.read_csv(REPORTS / "match_reconciliation.csv")
    pilot = status.merge(rec, on="official_match_id", suffixes=("_gate", "_recon"), validate="one_to_one")
    # Counts are copied from the recomputed confirmed-scope evidence artifact.
    metric = pd.read_csv(REPORTS / "pressure_coverage_opportunities.csv")
    conditional_controls = metric.loc[metric.opportunity.eq("four_control_cricsheet_candidate_detail")]
    cond_rows = int(pd.to_numeric(conditional_controls.candidate_state_rows, errors="coerce").sum())
    cond_pressure = int(pd.to_numeric(conditional_controls.candidate_paired_pressure_rows, errors="coerce").sum())
    cond_baseline = int(pd.to_numeric(conditional_controls.candidate_paired_baseline_rows, errors="coerce").sum())

    report_path = REPORTS / "phase4e_data_recovery_plan.md"
    report_path.write_text(f"""# Phase 4E — Confirmed-scope data recovery plan

## Decision and guardrails

This is a recovery queue and evidence plan, not a data repair or match acceptance. The canonical files and existing Phase 2E acceptance rules are unchanged. Confirmed scope is IPL seasons 2022 onward and T20I seasons from 2022 onward, filtered by official competition metadata and match date. All external-match gains below remain conditional; unresolved and rejected matches contribute **zero accepted coverage**.

The current confirmed-scope inventory contains **{int(totals.get('IPL', 0) + totals.get('T20I', 0)):,} unresolved team-run events**: IPL **{int(totals.get('IPL', 0)):,}**, T20I **{int(totals.get('T20I', 0)):,}**. The event-grain detail is preserved in [`phase4e_match_recovery_queue.csv`](phase4e_match_recovery_queue.csv), with one row per match, innings and unresolved extras label. Its separate `pilot_match` rows identify the Phase 2F targets.

## Unresolved events by competition and event type

Counts below are calculated on canonical `ball_by_ball.csv` after confirmed-scope filtering. The detailed match/innings breakdown (including `comp_id`, `match_id`, counts and source-field availability) is in the queue CSV.

{chr(10).join(event_lines)}

Unresolved events occur in **{unresolved.match_id.nunique()} matches** and **{len(match_innings)} match-innings**. Source rows have values in `runs`, `extras_type`, `extras1_runs`, and `extras_2_runs`; `extras1_runs` follows a category-code pattern and `extras_2_runs` has no confirmed amount definition. There is no per-delivery `total_runs` field. `legal_delivery`/status is absent or unknown for relevant categories. `is_wicket`, dismissal labels and player IDs are present but do not by themselves define team wicket loss or bowler credit. Queue rows list the actual fields present in the canonical source schema.

## What local data can and cannot recover

| Value | Existing local evidence | Recovery decision |
|---|---|---|
| Match, competition, season, date and local player IDs | `matches.csv`, `competitions.csv`, delivery IDs and mapping file | Already locally available for scoped matches; use official metadata and keep local ID namespace. This does not establish external player-ID mappings. |
| Innings/event ordering | `innings`, `overid`, `over_ball_num`, `innings_ball_num` | Coordinates are available; their conventions require validation for external alignment. `innings_ball_num` is not a legal-ball counter. |
| Batter runs | `runs`, `is_four`, `is_six`; 965 Phase 2F control rows matched Cricsheet batter runs | Locally observable as a candidate and well supported in the controls; keep its documented status/acceptance gate. Does not recover team runs. |
| Team-run delta and typed extra amount | `extras_type`, `extras1_runs`, `extras_2_runs` | **Not safely recoverable from existing local fields** until provider defines amounts and the per-row equation. Never add either extra field to `runs` by assumption. |
| Legal-ball state | `legal_delivery`, `legal_delivery_status`, labels | Some rows are classifiable; `Overstep` mapping is inferred and `other`/penalty and blank flags remain unresolved. Request explicit provider boolean and rules. |
| Targets and revised overs | `matches.revised_target`, `first_inn_revised_overs`, `second_inn_revised_overs`, result | Sparse and undocumented; can inventory existing non-null values, but cannot use as a state input without definitions, DLS/resource method and target effective-time semantics. |
| Innings final totals/wickets and bowling figures | No complete local innings scorecard/bowling figures for pilot; match result only | Requires independently sourced complete scorecards or provider innings summaries; endpoints do not locate missing delivery runs. |
| Match/venue/player external identity | local opaque `venue_id`, local player IDs, researched crosswalks | Local match metadata is available. External namespace/crosswalk remains gated; candidate/ambiguous names or venue links are not accepted evidence. |

An innings scorecard can validate an endpoint (runs, wickets, overs, target/result) but cannot recover which delivery added an unknown run. It therefore cannot restore delivery-level CRR/RRR by itself.

## Phase 2F pilot and exact acceptance blockers

The pilot has **4 downloaded controls** with **965 aligned delivery coordinates**: 0 exact, 962 partial/structural and 3 mismatched; all four remain **unresolved**. `match_acceptance_status.csv` is authoritative for the unchanged per-match blocking checks; `match_reconciliation.csv` carries field statuses and event counts.

| Match | Format/competition | Key unresolved acceptance checks | Evidence distinction |
|---:|---|---|---|
| 13511 | T20I, England in West Indies 2022 | `venue_identity; player_identity; typed_extras; delivery_totals; wickets; targets; bowling_figures` | 224 aligned rows are partial because official total/per-type extras and scorecard endpoints are absent; venue ID opaque; player namespace unconfirmed. |
| 20182 | IPL 2023 | `venue_identity; player_identity; typed_extras; delivery_totals; legal_balls; wickets; targets; bowling_figures` | 220 partial, 2 mismatches; two byes/leg-byes labels disagree at aligned events; DLS target requires independent confirmation; one `other` row has blank local legal flag. |
| 34429 | T20I, India in Sri Lanka 2024 | `venue_identity; player_identity; typed_extras; delivery_totals; wickets; targets; match_result; bowling_figures` | 256 partial, 1 mismatch; eliminator result representation differs structurally; venue/player identities unresolved. |
| 40725 | IPL 2025 | `player_identity; typed_extras; delivery_totals; legal_balls; wickets; targets; match_result; bowling_figures` | 262 partial; official IPL scorecard verified the retired-hurt event/venue and RR 188/4, but the full match remains unresolved; one `other` no-ball has blank local legality. |

For the four controls, event coordinates (innings/over/within-over position) aligned across all 965 compared rows; the current blocker is not a coordinate mismatch. The 16 no-file candidates cannot be coordinate-checked at all: no JSON delivery stream exists in the pilot to establish event indexing. Their match identity, venue and player identity checks therefore remain unresolved alongside delivery alignment and every downstream event/scoring gate. The source match metadata itself is available locally; it does not identify an external match record.

The exact checks and reasons are preserved in the original pilot audit. No new match acceptance is proposed. For delivery-free candidates, **16/16** have `unresolved_no_match_index_entry`; none has a downloaded match JSON and none is confirmed absent from a complete archive. The local match records mark these fixtures `Match Abandoned`. Confirm archive/organizer coverage first; a scorecard for an abandoned no-delivery fixture may validate status but cannot create pressure observations.

## Independent scorecard/source route and terms

Four controls already have source-backed research references. The Phase 2F.5 report records event totals matching independent scorecard material for 12/12 innings; typed-extras totals are compared for 8/8 innings in two detailed scorecard sets; bowler-conceded aggregates are corroborated on 8/8 innings in those same two matches. Those are sample-level validation findings, not acceptance of any match. The other two controls have thinner bowling/extras detail.

| Match | Documented source | What it can corroborate | Source standing / limit |
|---:|---|---|---|
| 13511 | [Windies Cricket series page](https://www.windiescricket.com/series/england-in-west-indies-2021-22-16230/) | Match/innings result and scorecard evidence used in Phase 2F.5 | Board source; full delivery/extras detail not established. |
| 20182 | [Punjab Kings match report](https://www.punjabkingsipl.in/news/rajapaksa-arshdeep-star-as-punjab-kings-beat-kolkata-knight-riders-ipl-2023-season-opener) | Match result and available scorecard evidence used in Phase 2F.5 | Team-published report; not a substitute for complete typed extras or provider delivery records. |
| 34429 | [Sri Lanka Cricket Annual Report 2024](https://srilankacricket.lk/wp-content/uploads/2025/06/SLC-Annual-Report-2024-soft-copy-1.pdf); [detailed secondary scorecard](https://www.ipl.com/matches/india-tour-of-sri-lanka-128745/sri-lanka-vs-india-78390/scorecard) | Regulation innings totals from SLC; detailed Super Over/scorecard comparison from the secondary page | SLC is the board source; the `ipl.com` scorecard is not represented as the official IPL website. |
| 40725 | [Official IPLT20 match centre](https://www.iplt20.com/matches/84107d66-507c-40a7-93b6-2b7abecdd0f3/delhi-capitals-vs-rajasthan-royals); [official IPL match report](https://www.iplt20.com/news/article/tata-ipl-2025-match-32-dc-vs-rr-match-report) | Venue, result, 188/4, Samson retired-hurt event and match context | Official BCCI/IPL source. The detailed external `ipl.com` scorecard cited in earlier research is secondary; the official match centre/report are the authoritative references. |

Revisit these URLs only for internal endpoint/event validation, recording access date, exact match, fields compared and evidence artifact hash. Do not copy or redistribute scorecard tables. The BCCI/IPL terms described above limit content reuse; public accessibility does not grant republication rights. For wider validation, request organizer/provider-supplied scorecards and explicit analytical/derivative-use permission.

Public access is not a blanket redistribution license. The [BCCI/IPL website terms](https://www.iplt20.com/terms-and-conditions) state that site content is protected and restrict copying/republication absent prior written authorization. The [ICC website terms](https://www.icc-cricket.com/about/the-icc/legal-notices/website-terms-of-use) also govern use of ICC content. Therefore: use a scorecard as a cited verification reference only after checking applicable current terms; do not scrape in bulk, republish scorecard text/tables, or package copied content. Prefer organizer/provider-supplied scorecards with explicit analytical and derivative-use permission. Cricsheet's [licensing page](https://cricsheet.org/licensing/) states its JSON/CSV match data are under ODC-BY; retain attribution and source/file hashes already recorded, and follow license conditions for any redistributed derivative.

## Prioritized recovery sequence

1. **Bulk provider response for all 837 scoped matches / 194,014 source deliveries.** Highest expected value because it addresses the systematic event ambiguity across 11,467 rows and supplies run, legality and target semantics together. Request a versioned full match package, not only a sample. A 20-match stratified pilot validates the dictionary and edge cases but does not repair unprovided matches.
2. **Finish the four downloaded controls as acceptance-gate test cases.** They are the cheapest concrete cases and expose all current gate types: player/venue namespace, scoring/extras, legal-ball semantics, endpoint/target/DLS, result/eliminator and bowling figures. Preserve match 40725's verified retired-hurt evidence but do not promote it.
3. **Resolve 16 no-delivery candidates through organizer/archive coverage records.** First request the complete archive index and source match identifiers. If no deliveries exist because play was abandoned, close as “no recoverable pressure deliveries” rather than spending scorecard effort.
4. **Use official scorecards to validate endpoints, not to impute event runs.** Target only controls and any newly received provider match packages; get permission/terms clearance before collecting or storing scorecard artifacts.
5. **Review player and venue crosswalks after stable source IDs arrive.** Current Cricsheet player candidates/ambiguities and three candidate venue links prevent safe player-level reconciliation. Keep verified, candidate, ambiguous and unresolved mappings distinct.

This order is based on breadth of pressure-state impact, paired baseline opportunity and gate coverage. The 11,467 run-event count is not used as a proxy for player eligibility.

## Conditional coverage scenarios (not recovered coverage)

Current confirmed-scope evidence remains **317 known regular-chase states**, including **292** with CRR and RRR (170 pressure and 122 comparison before pairing); the approved within-match/phase cohort remains **209 rows** (116 pressure, 93 baseline). Accepted external matches remain **0**, so realized gain is **0**.

| Scenario | Conditional state / paired-row gain | Conditional pressure / baseline | Player eligibility implication |
|---|---:|---:|---|
| Accept all 4 existing controls only after every unchanged gate passes | Up to **284** candidate within-match/phase paired rows across four controls, based on the existing opportunity audit; split **167 / 117**. Not additive as accepted data today. | 167 / 117 candidate rows | May add within-match observations; no player-format pair is shown to meet both existing floors, because player identity and cross-match exposure remain unresolved. Exact eligible-player gain is unknown until IDs, state labels and full gates pass. |
| Recover any of the 16 no-delivery pilot candidates | **Unknown**; current recovered count 0. No delivery package is indexed. | Unknown | No eligible-player gain can be estimated without complete event histories and identity mapping. A scorecard alone adds no delivery observations. |
| Provider returns complete confirmed-scope event and state fields for all matches | The absolute source-row ceiling is **91,934** regular second-innings delivery rows (42,085 IPL + 49,849 T20I), before exclusions for incomplete innings or other missing state inputs. This is not a forecast. Actual pressure/baseline counts must be recomputed from validated records. | Unknown until actual values are validated | Eligibility cannot be projected until validated pressure/baseline classifications and player IDs are available. Existing floors remain unchanged. |

The last scenario's **91,934** is only a ceiling on rows that could potentially be replayed, not a coverage gain. Complete scoring alone is insufficient without target/legal-ball metadata. A full provider response could unlock only rows whose entire innings state chain and match identity validate; actual gain must be measured after Phase 3E checks.

## Required provider/organizer response

Use [`phase4e_provider_request.md`](phase4e_provider_request.md). The minimum useful response is: (a) definitions for existing ambiguous fields; (b) per-delivery `batter_runs`, typed extras, `total_runs` and `is_legal_delivery`; (c) per-innings targets, revised legal-ball allowance/DLS semantics, final score/wickets/status and Super Over identity; (d) stable match/player/venue identifiers and documented crosswalks; (e) complete stratified records plus independent scorecard/bowling endpoints and explicit license/attribution terms. A dictionary alone or an innings scorecard alone is insufficient.

## Reproduction

```powershell
.\\venv\\Scripts\\python.exe -m src.phase4e_data_recovery
.\\venv\\Scripts\\pytest.exe -q
.\\venv\\Scripts\\python.exe -m compileall -q src tests
```
""", encoding="utf-8")

    request_path = REPORTS / "phase4e_provider_request.md"
    request_path.write_text("""# Phase 4E — Provider and organizer data request

**Subject: Versioned scoring, innings-state and identity package for confirmed IPL/T20I analysis (2022 onward)**

We are validating the supplied competition dataset under the confirmed Round 1 scope: IPL and T20I from 2022 onward. The canonical scoped population is 837 matches and 194,014 delivery rows. In the current source, 11,467 event team-run increments are unresolved (IPL 5,229; T20I 6,238). No values have been filled. Please identify the provider/product, export/schema version, effective dates, licensing terms and whether the delivered population is complete.

## Required files

The unresolved events break down by local `extras_type` as follows. The categories are observations, not confirmed run meanings:

| Format | `extras_type` | Events |
|---|---|---:|
| IPL | Overstep | 257 |
| IPL | byes | 188 |
| IPL | legbyes | 1,109 |
| IPL | other | 123 |
| IPL | wide | 3,552 |
| T20I | null | 1 |
| T20I | Overstep | 308 |
| T20I | Penalty | 1 |
| T20I | byes | 317 |
| T20I | legbyes | 1,552 |
| T20I | other | 137 |
| T20I | wide | 3,922 |

Please provide one versioned, read-only package with:

1. `manifest.json`: provider, product, release/schema version, effective dates, scope, retrieval/export timestamp, license and attribution, file hashes, completeness statement and known exclusions.
2. `data_dictionary.csv`: `field_name,type,definition,nullable,units,grain,enum_values,source_system,version`; explicitly define every field in the next section.
3. `deliveries.csv`: the complete delivery/event stream for all 837 scoped matches (or explicitly identify unavailable matches), retaining illegal deliveries and stable sequence. A smaller stratified pilot may validate definitions but cannot restore full-population coverage.
4. `innings_summary.csv`: one record per regular innings and Super Over innings with totals, wickets, legal balls/overs, innings status, target, revised target/allowance, DLS method/par, scheduled limit and end reason.
5. `match_crosswalk.csv`: provider match ID to official `match_id`, supported by date, competition/season, both team IDs/names, venue, match number/round and available source identifiers. No mapping based on date/team names alone.
6. `player_register.csv` and `player_crosswalk.csv`: stable provider player ID namespace, team/roster/date context, local `player_id` mapping, evidence, reviewer/decision. No name-only or fuzzy automatic joins.
7. `venue_register.csv` and `venue_crosswalk.csv`: stable provider venue namespace, official venue ID/name mapping, evidence and decision.
8. Complete independent scorecard references/artifacts for all supplied matches, including innings totals, wickets, overs, extras, targets/results and bowling figures. Include URLs, retrieval/access dates, artifact hashes and explicit rights for analytical use and any derivative/redistribution.

## Delivery fields and definitions

At minimum, every event must include `provider_match_id`, `innings`, `innings_type` (`regular`/`super_over` plus documented other values), stable `sequence`, over index, event position, batter/non-striker/bowler stable IDs, `batter_runs`, typed extras amounts (`wides`, `noballs`, `byes`, `legbyes`, `penalty`, `other`), `total_runs`, `is_legal_delivery`, dismissal code, dismissed player, `team_wicket_lost`, `bowler_credited_wicket`, and source row/event ID. Define the invariant `total_runs = batter_runs + all event extras`, and how innings-level penalties are represented without double counting.

For each innings supply `innings_total_runs`, `innings_wickets`, `innings_legal_balls`, end status (completed/all out/target reached/abandoned/interrupted), `target_runs`, `target_balls` or legal-ball limit, scheduled and revised overs/balls, DLS/par method and effective time, `is_super_over`, and innings sequence. Explain first innings targets, tied matches, eliminators, no-results, partial innings and revised-target transitions.

Please define current fields explicitly: `runs`, `extras_type`, `extras1_runs`, `extras_2_runs`, `legal_delivery`, `legal_delivery_status`, `is_four`, `is_six`, `is_wicket`, `dismissal_type_id`, `dismissal_type`, `dismissed_player_id`, `overid`, `over_ball_num`, `innings_ball_num`, `revised_target`, `first_inn_revised_overs`, `second_inn_revised_overs`, `venue_id`, and every player-ID field. Confirm whether `extras1_runs` is a category code, whether `extras_2_runs` is an amount, whether `Overstep` means a no-ball, and the treatment of `other`, `Penalty`, combined extras, byes, leg-byes, retired hurt/out and no-ball dismissal exceptions.

## Stratified validation package

Provide at least 20 complete match packages across IPL/T20I, seasons 2022–2026, ordinary events, wides, no-balls/Overstep, byes, leg-byes, `other`/Penalty, wickets/dismissal kinds, DLS/revised targets, Super Overs, abandoned/incomplete innings, and the four existing controls (13511, 20182, 34429, 40725) if available. Include all deliveries for each package, innings summaries, bowling figures, match outcomes and source documentation. Include the exact examples already sent in `provider_data_request.md`, including null extras type with nonzero secondary value, Overstep secondary values 1/4, other secondary values 1/4, and the Match 40725 retired-hurt coordinate (innings 2, over 6, event 36).

## Acceptance and privacy/licensing

This request does not pre-accept any match or change Phase 2E criteria. The delivered files will remain under `data/external/provider_response/<release>/`. We will compare to canonical official CSVs without overwriting them, validate every required semantic stratum, reconcile complete innings and independent scorecards, and retain failed/unknown fields as such. Please specify whether the license permits internal analysis, derived aggregate metrics, presentation of player-level results, and redistribution of event-level data; include required attribution and restrictions. Please do not provide personal data beyond the stable cricket participant identifiers necessary for the crosswalk.

## Current evidence and realistic coverage statement

Current accepted external matches and accepted external delivery rows are both **zero**. Current local evidence has 317 known regular chase states and 209 approved within-match/phase paired rows. The four downloaded controls represent a **conditional** maximum of 284 additional paired rows (167 pressure / 117 baseline) in the existing opportunity analysis, but they remain unresolved and count as zero now. No coverage gain will be claimed until the package passes the unchanged match-level gates and the Phase 3E semantic review.

Thank you.
""", encoding="utf-8")

    # Provider terms can be revised independently; keep this request reproducible.
    print(f"Wrote {OUTPUT_QUEUE.relative_to(ROOT)} ({len(queue)} rows); event groups={len(event_rows)}; unresolved events={event_csv_count}")


if __name__ == "__main__":
    write_reports()
