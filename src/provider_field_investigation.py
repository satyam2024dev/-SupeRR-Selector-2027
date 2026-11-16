"""Phase 3D: audit provider field evidence and quantify conditional state coverage."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

from src.cricket_data_validation import normalize_delivery_events

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"


def unresolved_run_event_audit(ball: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Count the exact events normalized as unknown and separate nulls from semantics."""
    normalized = normalize_delivery_events(ball)
    unknown = normalized.loc[normalized.team_runs_delta.isna()].copy()
    labels = unknown.extras_type.fillna("(null)").astype(str)
    unknown["extras_type_group"] = labels
    by_type = (unknown.groupby("extras_type_group", dropna=False).agg(
        unresolved_events=("match_id", "size"),
        runs_missing=("runs", lambda x: int(pd.to_numeric(x, errors="coerce").isna().sum())),
        extras1_missing=("extras1_runs", lambda x: int(pd.to_numeric(x, errors="coerce").isna().sum())),
        extras2_missing=("extras_2_runs", lambda x: int(pd.to_numeric(x, errors="coerce").isna().sum())),
        extras2_nonzero=("extras_2_runs", lambda x: int(pd.to_numeric(x, errors="coerce").fillna(0).ne(0).sum())),
        runs_sum_observed=("runs", lambda x: int(pd.to_numeric(x, errors="coerce").sum())),
    ).reset_index())
    nonzero_extra2 = pd.to_numeric(unknown.extras_2_runs, errors="coerce").fillna(0).ne(0)
    summary = pd.DataFrame([
        {"measure": "source_delivery_rows", "value": len(ball), "interpretation": "canonical ball_by_ball.csv rows"},
        {"measure": "unknown_team_run_delta_events", "value": len(unknown), "interpretation": "normalize_delivery_events leaves team_runs_delta unknown"},
        {"measure": "unknown_events_with_extras_type", "value": int(unknown.extras_type.notna().sum()), "interpretation": "type is present; run amount/field semantics unresolved"},
        {"measure": "unknown_events_null_extras_type_nonzero_extras2", "value": int((unknown.extras_type.isna() & nonzero_extra2).sum()), "interpretation": "ordinary-looking category code but nonzero secondary field prevents classification"},
        {"measure": "unknown_events_missing_runs", "value": int(pd.to_numeric(unknown.runs, errors="coerce").isna().sum()), "interpretation": "true nulls in runs among unresolved events"},
        {"measure": "unknown_events_missing_extras1", "value": int(pd.to_numeric(unknown.extras1_runs, errors="coerce").isna().sum()), "interpretation": "true nulls in extras1_runs among unresolved events"},
        {"measure": "unknown_events_missing_extras2", "value": int(pd.to_numeric(unknown.extras_2_runs, errors="coerce").isna().sum()), "interpretation": "true nulls in extras_2_runs among unresolved events"},
        {"measure": "unknown_events_nonzero_extras2", "value": int(nonzero_extra2.sum()), "interpretation": "observed values occur but amount semantics are undocumented"},
        {"measure": "all_rows_extras1_code_pattern_matches", "value": int(normalized.extras_code_pattern_valid.sum()), "interpretation": "observed label/code pattern; not a provider definition"},
    ])
    return summary, by_type


def _format_map(features: pd.DataFrame, matches: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    context = matches[["match_id", "comp_id"]].merge(
        competitions[["comp_id", "match_format", "comp_name"]], on="comp_id", how="left", validate="many_to_one")
    out = features.merge(context, on="match_id", how="left", validate="many_to_one")
    out["analysis_format"] = pd.Series(pd.NA, index=out.index, dtype="string")
    is_ipl = out.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False)
    out.loc[is_ipl, "analysis_format"] = "IPL"
    out.loc[out.match_format.eq("T20I"), "analysis_format"] = "T20I"
    return out


def state_coverage_opportunities(features: pd.DataFrame) -> pd.DataFrame:
    """Compute measured current and field-completion ceilings without assigning classes."""
    rows = []
    for fmt in ("IPL", "T20I"):
        all_fmt = features.loc[features.analysis_format.eq(fmt)]
        second = all_fmt.loc[pd.to_numeric(all_fmt.innings, errors="coerce").eq(2)].copy()
        score = second.score_known.fillna(False).astype(bool)
        target = second.target.notna()
        legal_state = second.legal_balls_known.fillna(False).astype(bool)
        remaining_known = pd.to_numeric(second.legal_balls_remaining, errors="coerce").notna()
        current = second.match_state_pressure_eligible.fillna(False).astype(bool)
        current_crr = pd.to_numeric(second.legal_balls_bowled_before, errors="coerce").gt(0)
        crr = pd.to_numeric(second.score_before, errors="coerce") * 6 / pd.to_numeric(second.legal_balls_bowled_before, errors="coerce").where(current_crr)
        rrr = pd.to_numeric(second.runs_required, errors="coerce") * 6 / pd.to_numeric(second.legal_balls_remaining, errors="coerce").where(pd.to_numeric(second.legal_balls_remaining, errors="coerce") > 0)
        for scenario, mask, assumption in [
            ("current_verified_state", current, "existing official reconstructed state only"),
            ("total_runs_defined_only", target & legal_state & remaining_known, "score progression restored if total runs are supplied for every delivery; existing target and legal state retained"),
            ("targets_defined_only", score & legal_state & remaining_known, "targets are supplied for all relevant innings; existing score and legal state retained"),
            ("legal_delivery_defined_only", score & target, "legal status is supplied for every event and remaining balls are replayed using a validated innings limit; existing score and target retained"),
            ("runs_and_targets_defined", legal_state & remaining_known, "team totals and targets are complete; existing legal state retained"),
            ("runs_and_legality_defined", target, "team totals and legal deliveries are complete; existing target retained"),
            ("all_state_inputs_defined_ceiling", pd.Series(True, index=second.index), "optimistic ceiling: complete event totals, target/revised target, legality, and innings limit for every recorded regular chase delivery"),
        ]:
            count = int(mask.sum())
            baseline = int((mask & current_crr & rrr.le(crr)).sum()) if scenario == "current_verified_state" else pd.NA
            pressure = int((mask & current_crr & rrr.gt(crr)).sum()) if scenario == "current_verified_state" else pd.NA
            rows.append({"format": fmt, "scenario": scenario, "regular_chase_source_rows": len(second),
                "state_rows_current_or_conditionally_reconstructable": count,
                "additional_state_rows_vs_current": max(0, count - int(current.sum())),
                "currently_classified_pressure_rows": pressure, "currently_classified_baseline_rows": baseline,
                "new_pressure_rows": "not classifiable before actual values are supplied" if scenario != "current_verified_state" else 0,
                "new_baseline_rows": "not classifiable before actual values are supplied" if scenario != "current_verified_state" else 0,
                "matches_represented": int(second.loc[mask, "match_id"].nunique()),
                "scenario_assumption": assumption,
                "evidence_status": "conditional planning ceiling; not reconstructed, accepted, or a changed pressure label" if scenario != "current_verified_state" else "observed official local state"})
    return pd.DataFrame(rows)


def build_requirements(unknown_summary: pd.DataFrame, by_type: pd.DataFrame,
                       opportunities: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    unresolved = int(unknown_summary.loc[unknown_summary.measure.eq("unknown_team_run_delta_events"), "value"].iloc[0])
    typed = int(unknown_summary.loc[unknown_summary.measure.eq("unknown_events_with_extras_type"), "value"].iloc[0])
    nulltype = int(unknown_summary.loc[unknown_summary.measure.eq("unknown_events_null_extras_type_nonzero_extras2"), "value"].iloc[0])
    missing_scorecards = 18
    revised_target_count = int(matches.revised_target.notna().sum())
    first_revision_count = int(matches.first_inn_revised_overs.notna().sum())
    second_revision_count = int(matches.second_inn_revised_overs.notna().sum())
    fields = [
        ("runs", "ball_by_ball.csv:runs", "present (200,999/200,999)", "ordinary-event values act as batter runs; provider definition absent; extra-event allocation not defined", "Do not call the whole column batter runs or total runs without a definition", "Document grain and attribution: batter runs vs total delivery runs; handling of extras-labelled events", "Validated batter-run subset; does not alone recover score state"),
        ("per_delivery_total_runs", "no column", "genuinely absent", f"{unresolved:,} delivery deltas are currently unknown", "No per-delivery team total exists", "Add a nullable/non-null integer total team runs off each recorded delivery, including penalties and multiple extra types", "Potential score states only when supplied across all prior innings events; pressure labels still need target and legality"),
        ("extras_type", "ball_by_ball.csv:extras_type", f"present on 11,832 events; null on 189,167", "values observed: wide, Overstep, byes, legbyes, other, Penalty; no provider definition", "Explicit category labels do not specify amounts, combinations, or rule priority", "Publish enum, null semantics, multi-type event encoding and version/effective date", "Separates delivery categories; alone unlocks no exact team-run amount"),
        ("extras1_runs", "ball_by_ball.csv:extras1_runs", "present (200,999/200,999)", "singleton code patterns match label categories; exactly 0 pattern mismatches", "Name suggests runs, but observed patterns indicate a category code; provider definition unavailable", "Document code list and explicitly state whether value is amount or type ID", "No score-state gain if it is categorical as observed"),
        ("extras_2_runs", "ball_by_ball.csv:extras_2_runs", "present (200,999/200,999); 36 nonzero", "values 0/1/4; all 36 nonzero cases occur on unresolved events; universal scope not established", "Meaning is undocumented; do not add it to runs", "Define unit, inclusion/exclusion, relation to extras_type, and multi-extra cases", "Could account for subset only after validation; not safe to extrapolate"),
        ("legal_delivery", "no source column; processed derivative only", "genuinely absent", "266 source events have unknown legality; Overstep=576 is inferred no-ball candidate", "Current legal flags are pattern-derived, not supplied by provider", "Add explicit boolean legal_delivery per event plus revised innings ball allowance units", "Can restore legal-ball/remaining-ball state where event totals, target, and limit are also known"),
        ("wide_no_ball flags_and_amounts", "extras_type; no dedicated flags", "partially represented / no-ball only inferred", "wide=7,714 explicit labels; Overstep=576 candidate; other=264 and Penalty=1 unclear", "Types/penalties and additional runs per event are not sufficiently documented", "Provide explicit wide_runs, no_ball_runs/flag, byes, legbyes, penalty amount and precedence", "Required for reliable total and legal count; individual labels alone do not give totals"),
        ("innings_totals", "no ball or matches total column", f"genuinely absent; only {missing_scorecards}/1,724 innings have exact local final score", "matches.result contains winner/margin text, not score totals", "Independent selected public scorecards validate sample matches but do not populate provider data", "Provide per-innings total, wickets, legal-ball notation, termination status, and scorecard reference", "Validates targets and replay end states; final total alone adds zero pre-delivery pressure rows"),
        ("target_revised_target", "matches.csv:revised_target; first_inn_revised_overs; second_inn_revised_overs", f"revised_target populated {revised_target_count}/{len(matches)}; first/second revised allowance populated {first_revision_count}/{len(matches)} and {second_revision_count}/{len(matches)}", "No public provider semantics; allowance values behave like balls by observed multiples-of-six pattern", "Target differs from final score; DLS and Super Over target rules need explicit field definitions", "Provide target runs, target overs/balls, DLS/par revisions, which innings/match the target applies to, and null semantics", "Targets alone expose only rows whose running scores and legal balls are already known"),
        ("bowler_conceded_runs", "no column", "genuinely absent", "No per-delivery or per-bowler conceded amount in official schema", "Cannot derive safely from current extras codes", "Supply conceded runs per delivery or complete bowler figures plus typed event-level extras", "Needed for economy; not needed to classify match pressure, but required for reliable bowling performance"),
        ("dismissal_bowler_credit", "is_wicket; dismissal_type_id; dismissal_type; dismissed_player_id", "event fields present, semantics partly undocumented", "10,881 wicket flags; 1 wicket row lacks dismissed ID; retired-hurt local event may be unclassified", "Team wicket, dismissed-player marker and bowler-credit are distinct; codes have no supplied dictionary", "Provide dismissal ID-to-label codebook, retired-hurt/out distinction, team-wicket rule, bowler credit rules and no-ball exceptions", "Improves wicket state/metric attribution; state-pressure score itself needs wickets only for certain proxies"),
        ("provider_provenance_schema_version", "not present in CSV schema", "genuinely absent", "No provider identity, export version, schema revision, or effective date discovered in repo/ZIP", "Cannot determine if semantics changed over seasons", "Identify provider, product, export/schema version, event-time convention, correction policy and data dictionary", "Necessary to apply definitions consistently across 2022–2026")
    ]
    result = pd.DataFrame(fields, columns=["concept", "official_columns", "availability", "observed_evidence", "documented_semantics_status", "provider_response_required", "pressure_or_metric_coverage_effect"])
    return result


def sample_records(ball: pd.DataFrame) -> pd.DataFrame:
    """Return minimal column subsets for ordinary, wide, secondary-extra, and retirement examples."""
    cols = ["match_id", "innings", "overid", "over_ball_num", "innings_ball_num", "runs", "extras_type", "extras1_runs", "extras_2_runs", "is_wicket", "dismissal_type", "dismissed_player_id"]
    picks = []
    def take(mask: pd.Series, label: str) -> None:
        subset = ball.loc[mask]
        if not subset.empty:
            row = subset.iloc[0][[c for c in cols if c in subset.columns]].to_dict()
            row["sample_purpose"] = label
            picks.append(row)
    take(ball.extras_type.isna() & ball.extras_2_runs.eq(0), "ordinary/null-type reference")
    take(ball.extras_type.isna() & ball.extras_2_runs.eq(1), "null extras type with nonzero extras_2_runs")
    take(ball.extras_type.astype("string").str.casefold().eq("wide"), "wide label; no run amount column")
    take(ball.extras_type.astype("string").str.casefold().eq("overstep") & ball.extras_2_runs.eq(1), "Overstep candidate with secondary value 1")
    take(ball.extras_type.astype("string").str.casefold().eq("overstep") & ball.extras_2_runs.eq(4), "Overstep candidate with nonzero secondary field")
    take(ball.extras_type.astype("string").str.casefold().eq("other") & ball.extras_2_runs.eq(1), "other category with secondary value 1")
    take(ball.extras_type.astype("string").str.casefold().eq("other") & ball.extras_2_runs.eq(4), "other category with nonzero secondary field")
    take(ball.match_id.eq(40725) & ball.innings.eq(2) & ball.innings_ball_num.eq(36), "retired-hurt evidence: local event lacks explicit retirement type")
    return pd.DataFrame(picks)


def _request_markdown(summary: pd.DataFrame, by_type: pd.DataFrame, samples: pd.DataFrame,
                      requirements: pd.DataFrame) -> str:
    def table(frame: pd.DataFrame) -> str:
        view = frame.astype(object).where(pd.notna(frame), "").astype(str)
        heads = list(view.columns)
        lines = ["| " + " | ".join(heads) + " |", "|" + "|".join(["---"] * len(heads)) + "|"]
        lines += ["| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in view.itertuples(index=False, name=None)]
        return "\n".join(lines)
    return f'''# Technical request to original dataset provider

**Subject: Required field definitions and event-level scoring fields for the supplied T20/T20I CSV export**

Hello,

We are validating a delivery-level T20/T20I dataset covering the 2022–2026 seasons. The export contains 200,999 rows in `ball_by_ball.csv`, linked by `match_id` to `matches.csv` and `competitions.csv`. Please identify the provider/product, export version, schema version and effective dates, then answer the definitions below. We will preserve your response with the dataset version and will not infer undocumented values.

## Observed event patterns requiring clarification

The pipeline currently cannot determine an exact team-run increment for **{int(summary.loc[summary.measure.eq('unknown_team_run_delta_events'), 'value'].iloc[0]):,}** rows. These are not simply null run cells: `runs`, `extras1_runs` and `extras_2_runs` are populated on every row. The unresolved groups are:

{table(by_type)}

`extras1_runs` has a one-to-one observed category-code pattern with `extras_type`, including code 6 for null type; it is therefore not treated as a run amount. `extras_2_runs` has values 0, 1 and 4, but the meaning and relationship to the extra category are not documented. The values support hypotheses only and are not added to `runs`.

Representative rows from the canonical file (player identifiers omitted):

{table(samples)}

## Definitions and fields requested

Please provide a versioned data dictionary and, preferably, a corrected sample/export with these fields for every delivery:

1. `batter_runs`: runs credited to the striker on this event.
2. `extras` as typed amounts (`wides`, `noballs`, `byes`, `legbyes`, `penalty`, and any other supported types), permitting multiple types on one event where rules require it.
3. `total_runs`: total team runs added on the delivery, with a documented invariant against batter runs, typed extras and penalties.
4. `is_legal_delivery`: provider-defined boolean for every event, including Overstep/no-ball, wide, Other, Penalty, combined extras and exceptional events.
5. `is_ball_faced` or the provider's exact balls-faced rule, if supplied; state treatment of wides, no-balls and byes/leg-byes.
6. Match/innings metadata: innings number/type, innings total, wickets lost, innings completion/abandonment status, scheduled legal-ball limit, revised limit, target runs and target legal balls/overs, DLS/par method, and Super Over/eliminator identifier.
7. `bowler_conceded_runs` per delivery or an exact derivation rule; identify which extra categories are charged to the bowler.
8. Dismissals: stable dismissal code dictionary, dismissed player, team wicket-loss effect, bowler-credit effect, retired hurt versus retired out, and no-ball exceptions.
9. Player ID namespace and venue ID namespace, plus historical alias/renaming policy; identifiers must be stable and versioned.

For existing fields, please define `runs`, `extras_type`, `extras1_runs`, `extras_2_runs`, `is_four`, `is_six`, `is_wicket`, `dismissal_type_id`, `dismissal_type`, `dismissed_player_id`, `overid`, `over_ball_num`, `innings_ball_num`, `revised_target`, `first_inn_revised_overs` and `second_inn_revised_overs`. In particular, confirm whether `extras1_runs` is a category ID (the observed values suggest this), whether `extras_2_runs` is an amount or code, and whether `Overstep` is exactly a no-ball.

## Required validation material

Please return at least 20 complete match packages stratified across IPL/T20I, seasons, ordinary matches, wides/no-balls, byes/leg-byes, DLS/revised targets, Super Overs, Penalty/Other events and dismissals. Include the raw delivery records, final innings scorecards, bowling figures, match result, and schema version. Include all rows for each selected match rather than isolated examples, so totals and event sequencing can be reconciled.

The current unknown event counts by type are:

{table(by_type)}

Please include at least one documented example for each nonzero extras pattern, including null `extras_type` with nonzero `extras_2_runs`, `Overstep` with secondary values 1 and 4, `other` with secondary values 1 and 4, and the local Match 40725 retired-hurt event coordinate (innings 2, over 6, source event 36). The retired-hurt event is currently represented locally by `is_wicket=false`, blank `dismissal_type`, and a dismissed-player identifier; please clarify how that retirement was intended to be encoded.

## Coverage implications and acceptance

The local file has 42,085 IPL and 49,849 T20I second-innings delivery rows. These are only a theoretical state-reconstruction ceiling if complete per-delivery totals, targets/revised targets and legal-ball fields are provided and validate. They are **not** pressure or baseline counts; pressure class cannot be assigned until actual values arrive. Current known IPL/T20I regular chase states are 36 and 281 respectively, with 22 and 187 states in the approved within-match/phase paired sample. Complete team-run totals alone will not repair missing targets or legal-ball state; innings scorecards alone will not recover delivery-by-delivery running scores.

We will not overwrite the original files or adopt a correction based solely on this email. Any new data will be kept separately, reconciled match-by-match against independent scorecards, and subjected to the existing acceptance criteria. Please state applicable licensing and redistribution restrictions.

Thank you.
'''


def _report(summary: pd.DataFrame, by_type: pd.DataFrame, opportunities: pd.DataFrame,
            requirements: pd.DataFrame, samples: pd.DataFrame) -> str:
    def table(frame: pd.DataFrame) -> str:
        view = frame.astype(object).where(pd.notna(frame), "").astype(str)
        heads = list(view.columns)
        lines = ["| " + " | ".join(heads) + " |", "|" + "|".join(["---"] * len(heads)) + "|"]
        lines += ["| " + " | ".join(v.replace("|", "\\|").replace("\n", " ") for v in row) + " |" for row in view.itertuples(index=False, name=None)]
        return "\n".join(lines)
    return f'''# Phase 3D — Original data provider field investigation

## Source documentation status

No provider name, export version, or provider data dictionary is present in the six canonical CSVs, the repository, or the supplied ZIP archive (which contains only those CSVs and the competition PDF). A public search for the exact identifiers `extras1_runs` and `extras_2_runs` returned no provider specification. Consequently the requested provider documentation is **not found**, not evidence that a particular semantic is correct. Cricket Laws describe cricket scoring mechanics but cannot define this provider's proprietary fields.

## Exact source of the 11,833 unresolved team-run events

The state pipeline's `normalize_delivery_events` sets `team_runs_delta` only when `extras_type` is null, `extras_2_runs == 0`, and `runs` is present. The unresolved count therefore comes from these source fields: `extras_type`, `extras_2_runs`, `runs`, and (for code-pattern audit only) `extras1_runs`. Exact counts:

{table(summary)}

The exact source rule is: `team_runs_delta` is populated only when `extras_type` is null, `extras_2_runs == 0`, and `runs` is non-null; otherwise it is unknown. Thus the decisive columns are `extras_type` and `extras_2_runs`, with `runs` serving as the candidate amount and `extras1_runs` only cross-checking the observed category-code pattern. The 11,833 are **semantic unknowns, not missing numeric cells**: all unresolved rows have populated `runs`, `extras1_runs`, and `extras_2_runs`. Specifically, **{int(summary.loc[summary.measure.eq('unknown_events_with_extras_type'), 'value'].iloc[0]):,}** have an extras label and **{int(summary.loc[summary.measure.eq('unknown_events_null_extras_type_nonzero_extras2'), 'value'].iloc[0])}** have null `extras_type` with `extras_2_runs=1`. All 11,833 are excluded from a safe total-run delta. The extra-code pattern matches all rows but documents no amount.

### Unresolved events by observed category

{table(by_type)}

`extras1_runs` is observed to map as 1=Overstep, 2=wide, 3=legbyes, 4=byes, 5=other, 6=null type, and 7=Penalty. This is a complete pattern in the file, not an original provider definition. `extras_2_runs` is 0 in 200,963 rows; the 36 nonzero entries are 20 ones and 16 fours. Those values appear only on otherwise unresolved rows. Selected external scorecards in prior audits show that these values can coincide with extras, but do not prove a universal scope or amount rule.

## Field-by-field documentation and availability

No original provider specification was found for any requested semantic. The CSV contains some related fields, but a field name/pattern is not a definition.

{table(requirements)}

Important distinctions:

- `runs` is populated on every row. It agrees with Cricsheet `runs.batter` on all 965 aligned control deliveries, and ordinary-event behavior is validated. This is a comparison against four unaccepted external controls, not an original provider definition or full archive reconciliation; it is never a team total.
- There is **no** raw per-delivery `total_runs`, `legal_delivery`, `is_wide`, `is_no_ball`, `is_ball_faced`, or bowler-conceded-runs field.
- `extras_type` labels wide explicitly (7,714 rows); Overstep (576) is only a no-ball candidate. `other` (264) and Penalty (1) legality are unresolved. Provider definitions are needed for additional runs and combinations.
- `matches.csv.revised_target` is present but sparse; `first_inn_revised_overs`/`second_inn_revised_overs` are populated on 25 matches each and behave like legal-ball allowances by observed values, but this remains an inference. `matches.result` is not an innings score.
- `is_wicket` and dismissal labels support event counting, not automatic bowler credit. The retired-hurt review documents one local event with no explicit retirement label. Bowler-credit rules, no-ball exceptions, and dismissal code IDs remain undocumented.

## Conditional pressure-state coverage from confirmed fields

Current validated state counts are unchanged. Across the IPL/T20I subsets, 36 IPL and 281 T20I regular chase rows currently have all required state inputs; the approved same-match/phase paired samples contain 22 IPL and 187 T20I states. The full source has 42,085 IPL and 49,849 T20I innings-2 delivery rows. Those figures bound a *theoretical* row ceiling only if complete total-run events, target/revised-target metadata and legal-ball status are provided and reconciled.

{table(opportunities)}

No future pressure/baseline class is assigned in these scenarios. Actual classifications require the provider's event values to be supplied; first-ball states also lack a completed-ball CRR denominator. Scorecards with only innings totals/targets can verify endpoints but cannot restore pre-delivery scores; the four Cricsheet controls conditionally yielded 284 paired state rows in the Phase 3C replay, but remain unaccepted (0/4), so validated gain is still zero. The 16 no-local-delivery matches remain unresolved.

## Minimum reliable state request

At a minimum request: (1) exact team `total_runs` per delivery, or documented batter and typed extra amounts with an invariant; (2) explicit `is_legal_delivery` for every event and the scheduled/revised legal-ball allowance; (3) innings target runs, target balls/overs and DLS/revised-target semantics; and (4) innings identity/end status, including Super Over designation. Validate a complete sample against independent innings totals and scorecards before using any state.

For player-level pressure comparisons also require a documented stable player-ID namespace/crosswalk. Reliable bowler performance additionally requires bowler-conceded runs or enough typed extras for a proven derivation, plus complete legal-ball and bowler-credit dismissal rules. Venue-ID mapping is required for full Phase 2E external match acceptance, even though venue does not enter the current pressure formula.

## Conclusion

The dataset itself establishes the 11,833 unresolved rows and several reproducible patterns, but it does not contain the provider documentation needed to turn those patterns into scoring rules. The most effective next action is the precise provider request in `provider_data_request.md`: prioritize event-level totals, legal-ball status, target/revised-target and innings-limit definitions, with complete stratified match bundles and independent scorecards. Do not promote any scenario ceiling to observed coverage until actual provider values pass the unchanged reconciliation and acceptance gates.
'''


def generate() -> dict[str, int]:
    ball = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    features = pd.read_csv(PROCESSED / "pressure_research_deliveries.csv.gz", low_memory=False)
    unknown_summary, by_type = unresolved_run_event_audit(ball)
    formatted = _format_map(features, matches, competitions)
    opportunities = state_coverage_opportunities(formatted)
    samples = sample_records(ball)
    requirements = build_requirements(unknown_summary, by_type, opportunities, matches)
    REPORTS.mkdir(parents=True, exist_ok=True)
    requirements.to_csv(REPORTS / "provider_field_requirements.csv", index=False)
    (REPORTS / "provider_field_investigation.md").write_text(_report(unknown_summary, by_type, opportunities, requirements, samples), encoding="utf-8")
    (REPORTS / "provider_data_request.md").write_text(_request_markdown(unknown_summary, by_type, samples, requirements), encoding="utf-8")
    return {"unresolved_team_run_events": int(unknown_summary.loc[unknown_summary.measure.eq("unknown_team_run_delta_events"), "value"].iloc[0]),
        "unknown_events_with_type": int(unknown_summary.loc[unknown_summary.measure.eq("unknown_events_with_extras_type"), "value"].iloc[0]),
        "unknown_events_from_secondary_without_type": int(unknown_summary.loc[unknown_summary.measure.eq("unknown_events_null_extras_type_nonzero_extras2"), "value"].iloc[0]),
        "current_verified_states": int(formatted.match_state_pressure_eligible.fillna(False).sum()),
        "coverage_scenario_rows": len(opportunities), "field_requirements": len(requirements)}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
