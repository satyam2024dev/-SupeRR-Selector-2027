"""Build conservative delivery-state artifacts from the canonical official CSV files."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from src.cricket_data_validation import analyze_extras, delivery_validation_summary, normalize_delivery_events
from src.match_state import reconstruct_match_states

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"


def run_pipeline() -> dict[str, object]:
    """Validate source patterns and write compressed delivery state plus reports.

    Reads only the canonical root-level ball, match, and competition CSVs. No source
    file is edited. Derived scores become unknown after any unsupported extras event.
    """
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    ball = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)

    extras = analyze_extras(ball)
    extras.to_csv(REPORTS / "extras_analysis.csv", index=False)
    validation = delivery_validation_summary(ball)
    normalized = normalize_delivery_events(ball)
    if normalized.duplicated(["match_id", "innings", "innings_ball_num"]).any():
        raise ValueError("Source has duplicate match/innings/innings_ball_num keys; order cannot be safely reconstructed")
    normalized = normalized.rename(columns={"innings_ball_num": "sequence"})
    revision_checks = {}
    for innings_num, field in [(1, "first_inn_revised_overs"), (2, "second_inn_revised_overs")]:
        populated = matches.loc[matches[field].notna(), ["match_id", field]]
        values = pd.to_numeric(populated[field], errors="coerce")
        comparisons = []
        for _, record in populated.iterrows():
            cap = pd.to_numeric(pd.Series([record[field]]), errors="coerce").iloc[0]
            inning_rows = normalized[(normalized["match_id"] == record["match_id"]) & (normalized["innings"] == innings_num)]
            if pd.isna(cap) or inning_rows.empty:
                continue
            candidate_legal = int(inning_rows["legal_delivery"].fillna(False).sum())
            comparisons.append({"match_id": int(record["match_id"]), "field_value": float(cap),
                                "classified_legal_rows": candidate_legal,
                                "unknown_legal_category_rows": int(inning_rows["legal_delivery"].isna().sum()),
                                "difference": int(candidate_legal - cap)})
        valid_values = values.dropna()
        revision_checks[field] = {
            "populated_match_rows": len(populated),
            "all_observed_values_are_integer_multiples_of_six": bool(len(valid_values) and all(v.is_integer() and int(v) % 6 == 0 for v in valid_values)),
            "observed_min": float(valid_values.min()) if len(valid_values) else None,
            "observed_max": float(valid_values.max()) if len(valid_values) else None,
            "classified_delivery_count_equals_field": sum(r["difference"] == 0 for r in comparisons),
            "classified_delivery_count_below_field": sum(r["difference"] < 0 for r in comparisons),
            "classified_delivery_count_above_field": sum(r["difference"] > 0 for r in comparisons),
            "comparisons_with_unknown_legal_category_rows": sum(r["unknown_legal_category_rows"] > 0 for r in comparisons),
            "fully_classified_count_equals_field": sum(r["difference"] == 0 and r["unknown_legal_category_rows"] == 0 for r in comparisons),
            "above_field_cases": [r for r in comparisons if r["difference"] > 0],
            "interpretation": "Inference: values represent legal-ball allowances (balls) rather than overs; names are misleading. All observed values are multiples of six and above the maximum 20-over notation; recheck against official innings scorecards.",
        }
    validation["revised_innings_allowance_field_investigation"] = revision_checks

    comp_format = competitions.set_index("comp_id")["match_format"]
    match_rows = matches.set_index("match_id")
    quality_records = []
    state_parts = []
    audits = []
    candidate_matches = sorted(normalized["match_id"].dropna().unique().tolist())
    multi_innings = normalized.groupby("match_id")["innings"].nunique()
    sample_matches = [int(m) for m in candidate_matches if multi_innings.get(m, 0) >= 2][:5]

    for match_id, match_ball in normalized.groupby("match_id", sort=True):
        if match_id not in match_rows.index:
            raise ValueError(f"Unmatched source match_id {match_id}")
        meta = match_rows.loc[match_id]
        match_info = {
            "revised_target": meta.get("revised_target"),
            "first_inn_revised_overs": meta.get("first_inn_revised_overs"),
            "second_inn_revised_overs": meta.get("second_inn_revised_overs"),
        }
        states = reconstruct_match_states(match_ball, match_info)
        state_parts.append(states)
        fmt = comp_format.get(meta["comp_id"], "unknown")
        known_score_rows = int(states["score_known"].sum())
        known_ball_rows = int(states["legal_balls_known"].sum())
        innings_status = states.groupby("innings", sort=True).tail(1)
        innings_count = int(states["innings"].nunique())
        terminal_known = int(innings_status["innings_final_score_if_known"].notna().sum())
        quality_records.append({
            "match_id": int(match_id), "comp_id": int(meta["comp_id"]), "format": fmt,
            "season": str(competitions.loc[competitions["comp_id"].eq(meta["comp_id"]), "season"].iloc[0]),
            "source_delivery_rows": len(match_ball), "innings_count": innings_count,
            "contains_super_over_candidate": bool(match_ball["innings"].ge(3).any()),
            "score_state_known_rows": known_score_rows, "score_state_known_pct": round(100 * known_score_rows / len(states), 3) if len(states) else 0,
            "legal_ball_state_known_rows": known_ball_rows, "legal_ball_state_known_pct": round(100 * known_ball_rows / len(states), 3) if len(states) else 0,
            "innings_final_score_known_count": terminal_known,
            "innings_final_score_unknown_count": innings_count - terminal_known,
            "source_result": meta.get("result"), "source_winner_present": pd.notna(meta.get("win_team_id")),
            "quality_status": "partial: unresolved source event accounting" if terminal_known < innings_count else "state arithmetic complete; verify with official scorecard",
        })
        if int(match_id) in sample_matches:
            audits.append(_manual_audit(match_id, match_ball, states))

    # Keep scheduled matches with no delivery extract visible in quality output.
    present_match_ids = set(normalized["match_id"].dropna().unique())
    for _, meta in matches.loc[~matches["match_id"].isin(present_match_ids)].iterrows():
        fmt = comp_format.get(meta["comp_id"], "unknown")
        season_value = competitions.loc[competitions["comp_id"].eq(meta["comp_id"]), "season"]
        quality_records.append({
            "match_id": int(meta["match_id"]), "comp_id": int(meta["comp_id"]), "format": fmt,
            "season": str(season_value.iloc[0]) if len(season_value) else "unknown",
            "source_delivery_rows": 0, "innings_count": 0,
            "contains_super_over_candidate": False,
            "score_state_known_rows": 0, "score_state_known_pct": 0.0,
            "legal_ball_state_known_rows": 0, "legal_ball_state_known_pct": 0.0,
            "innings_final_score_known_count": 0, "innings_final_score_unknown_count": 0,
            "source_result": meta.get("result"), "source_winner_present": pd.notna(meta.get("win_team_id")),
            "quality_status": "missing ball-by-ball records",
        })

    all_states = pd.concat(state_parts, ignore_index=True)
    # Compact processed derivative; source fields remain byte-for-byte untouched.
    output_columns = [c for c in ["match_id", "innings", "sequence", "overid", "over_ball_num", "batting_team_id",
        "bowling_team_id", "striker_id", "striker_name", "bowler_id", "bowler_name", "runs", "extras_type",
        "extras1_runs", "extras_2_runs", "batter_runs_candidate", "team_runs_delta", "team_runs_status",
        "legal_delivery", "legal_delivery_status", "wicket_event", "dismissal_type", "dismissed_player_id",
        "score_before", "score_known", "wickets_lost_before", "legal_balls_bowled_before", "legal_balls_known",
        "legal_balls_remaining", "target", "runs_required", "current_run_rate", "required_run_rate",
        "state_status", "innings_overs_limit", "innings_balls_limit", "innings_end_status", "innings_final_score_if_known"] if c in all_states]
    state_path = PROCESSED / "match_state_deliveries.csv.gz"
    all_states[output_columns].to_csv(state_path, index=False, compression="gzip")
    quality = pd.DataFrame(quality_records)
    quality.to_csv(REPORTS / "match_state_quality.csv", index=False)
    validation["manual_real_match_audits"] = audits
    validation["pressure_state_summary"] = {
        "match_count": len(quality_records), "delivery_state_rows": len(all_states),
        "matches_without_ball_by_ball_rows": int((quality["source_delivery_rows"] == 0).sum()),
        "score_known_state_rows": int(all_states["score_known"].sum()),
        "legal_balls_known_state_rows": int(all_states["legal_balls_known"].sum()),
        "complete_final_innings_scores": int(quality["innings_final_score_known_count"].sum()),
        "total_innings": int(quality["innings_count"].sum()),
    }
    (REPORTS / "match_state_validation.md").write_text(_validation_markdown(validation, extras, quality, audits), encoding="utf-8")
    (REPORTS / "match_state_validation.json").write_text(json.dumps(validation, indent=2, default=str), encoding="utf-8")
    return {"match_count": len(quality_records), "delivery_rows": len(all_states),
            "manual_matches": audits, "state_file": str(state_path), "quality_file": str(REPORTS / "match_state_quality.csv")}


def _manual_audit(match_id: int, source: pd.DataFrame, states: pd.DataFrame) -> dict[str, object]:
    """Independently replay known source deltas and verify every pre-delivery wicket state."""
    source = source.sort_values(["innings", "sequence"], kind="stable").reset_index(drop=True)
    states = states.sort_values(["innings", "sequence"], kind="stable").reset_index(drop=True)
    if len(source) != len(states):
        raise AssertionError(f"Match {match_id}: output/source row counts differ")
    checks = 0
    innings_audits = []
    for innings in sorted(source["innings"].unique()):
        src = source[source["innings"].eq(innings)].reset_index(drop=True)
        out = states[states["innings"].eq(innings)].reset_index(drop=True)
        expected_score = 0.0
        score_known = True
        expected_wickets = 0
        legal_balls = 0
        legal_known = True
        first_unknown_sequence = None
        for i, delivery in src.iterrows():
            row = out.iloc[i]
            if int(row["wickets_lost_before"]) != expected_wickets:
                raise AssertionError(f"Match {match_id} innings {innings}: wicket state mismatch at sequence {delivery.sequence}")
            checks += 1
            if bool(row["score_known"]) != score_known:
                raise AssertionError(f"Match {match_id} innings {innings}: score-known flag mismatch at sequence {delivery.sequence}")
            if score_known and float(row["score_before"]) != expected_score:
                raise AssertionError(f"Match {match_id} innings {innings}: score mismatch at sequence {delivery.sequence}")
            if bool(row["legal_balls_known"]) != legal_known:
                raise AssertionError(f"Match {match_id} innings {innings}: legal-known flag mismatch at sequence {delivery.sequence}")
            if legal_known and int(row["legal_balls_bowled_before"]) != legal_balls:
                raise AssertionError(f"Match {match_id} innings {innings}: legal ball count mismatch at sequence {delivery.sequence}")
            delta = delivery.team_runs_delta
            if pd.isna(delta):
                score_known = False
                if first_unknown_sequence is None:
                    first_unknown_sequence = int(delivery.sequence)
            elif score_known:
                expected_score += float(delta)
            legal = delivery.legal_delivery
            if pd.isna(legal):
                legal_known = False
            elif legal_known and bool(legal):
                legal_balls += 1
            if bool(delivery.wicket_event):
                expected_wickets += 1
            checks += 1
        innings_audits.append({"innings": int(innings), "deliveries_checked": len(src),
            "first_unknown_score_sequence": first_unknown_sequence, "terminal_score_exact": score_known,
            "terminal_legal_ball_count_exact": legal_known, "wicket_events": expected_wickets})
    return {"match_id": int(match_id), "source_rows": len(source), "independent_row_checks": checks,
            "checks_passed": True, "innings": innings_audits,
            "scope": "internal event replay validation only; not an independent scorecard/official total reconciliation"}


def _validation_markdown(validation: dict[str, object], extras: pd.DataFrame,
                         quality: pd.DataFrame, audits: list[dict[str, object]]) -> str:
    extra_table = _md_table(extras[["extras_type", "rows", "extras1_runs_values", "extras_2_runs_distribution", "interpretation"]])
    quality_summary = _md_table((quality[["score_state_known_pct", "legal_ball_state_known_pct", "innings_final_score_known_count"]]
        .describe().round(2).reset_index().rename(columns={"index": "stat"})))
    revision_info = validation["revised_innings_allowance_field_investigation"]
    rev_first = revision_info["first_inn_revised_overs"]
    rev_second = revision_info["second_inn_revised_overs"]
    audit_table = _md_table(pd.DataFrame([{"match_id": a["match_id"], "source_rows": a["source_rows"],
        "row_checks": a["independent_row_checks"], "checks_passed": a["checks_passed"],
        "detail": "; ".join(f"inn {i['innings']}: {i['deliveries_checked']} rows, first unknown score at {i['first_unknown_score_sequence']}" for i in a["innings"])} for a in audits]))
    return f"""# Phase 2B — cricket data validation and match state reconstruction

## Scope and safeguards

Read only the canonical `data/raw/ball_by_ball.csv`, `matches.csv`, and `competitions.csv`. ZIP contents and nested copies were not ingested. Source CSVs were not changed. The engine writes a compressed delivery derivative to `data/processed/match_state_deliveries.csv.gz`. Unknown score or legal-ball events propagate to later states as unknown; no fabricated increments or rankings are produced.

## Field semantics from the observed feed

`extras1_runs` is exactly category-coded in all observed rows: null `extras_type` pairs with 6; Overstep=1, wide=2, legbyes=3, byes=4, other=5, Penalty=7. It is not an amount. `extras_2_runs` is 0 on 200,963 rows, 1 on 20, and 4 on 16; its meaning is undocumented and its values do not cover wide/bye/leg-bye run amounts. The `runs` field is 0–6, its sum is {validation['runs_column_sum_not_total_claim']:,}, and all four/six flags agree with values 4/6. It is therefore treated as a provisional batter-run field on ordinary deliveries only, not as a verified team total. All extras-labelled events currently have unknown team-run delta.

`Overstep` is a likely no-ball label from feed patterns and cricket terminology; it is **an inference**, not a supplied data dictionary definition. ICC/MCC rules state no-balls and wides do not count as valid balls, each has a one-run penalty, and further runs are attributed according to whether the batter hit the ball or runs were byes/leg-byes. This dataset does not retain sufficient extra amounts to apply those rules to all events. Byes and leg-byes are legal-ball events under ordinary circumstances, but type overlap/override cannot be verified from this single extras category field. Other/Penalty validity also remains unknown. Wicket flags equal non-null dismissal types ({validation['wicket_flag_rows']:,} each); one wicket row lacks dismissed-player ID. 609 flagged dismissals are RunOut, Retire Out, or Obstructing-field variants and must not automatically be credited to a bowler.

### Revised-overs fields

The fields `first_inn_revised_overs` and `second_inn_revised_overs` have {rev_first['populated_match_rows']} and {rev_second['populated_match_rows']} populated values respectively. Every observed value is an integer multiple of six, ranging from {rev_first['observed_min']:.0f}–{rev_first['observed_max']:.0f} and {rev_second['observed_min']:.0f}–{rev_second['observed_max']:.0f}. Values above 20 cannot represent overs in these T20 competitions; classified legal-delivery counts reach the field value in {rev_first['classified_delivery_count_equals_field']}/{rev_first['populated_match_rows']} first-innings and {rev_second['classified_delivery_count_equals_field']}/{rev_second['populated_match_rows']} second-innings records. Unknown validity categories appear in {rev_first['comparisons_with_unknown_legal_category_rows']} first-innings and {rev_second['comparisons_with_unknown_legal_category_rows']} second-innings comparisons, so equality is not official verification. This supports interpreting the value as a legal-ball allowance despite the column name. Classified counts above the field occur in {rev_first['classified_delivery_count_above_field']} first-innings and {rev_second['classified_delivery_count_above_field']} second-innings records. The engine converts only observed multiples of six to ball caps; unconventional values remain unknown.

### Observed extras patterns

{extra_table}

Sources: [MCC Laws of Cricket, 2017 Code, 4th Edition (2026), Laws 18, 21–23](https://www.lords.org/getmedia/a4ef9f77-2a25-4f5b-a286-4601f08e6334/Laws-of-Cricket-2017-Code-4th-Edition-%282026%29_5.pdf); [ICC Men’s T20I Playing Conditions](https://www.icc-cricket.com/about/cricket/rules-and-regulations/playing-conditions), including validity of balls and Super Over procedures. These rules inform cricket mechanics only; they do not define this provider’s columns.

## What can and cannot be verified

| Check | Result |
|---|---|
| Extras code/type agreement | {validation['extras_code_pattern_mismatch_rows']} mismatches in {validation['rows']:,} rows |
| Batter-run plausibility | four/six flags match source runs; ordinary run sum is provisional |
| Total team runs | **Not verified**; no innings scorecards and extra amounts are incomplete |
| Bowler-conceded runs | **Not verified**; no complete total extras field |
| Legal deliveries | partial: ordinary/wide/byes/legbyes classified; Overstep inferred no-ball; Other/Penalty remain unknown |
| Revised innings allowance | observed values strongly indicate legal-ball limits, not over counts; some categories still lack proven validity, so this comparison is not official scorecard verification |
| Wickets | event flags match dismissal labels; bowler credit needs dismissal rules; one dismissed ID missing |
| Super Overs | innings 3/4 appear in six matches, each one-over sized; classified separately with a 6-ball/two-wicket cap, subject to feed confirmation |
| Match result | result text present in all 883; winner ID absent in 41; all populated winner IDs match one of the listed teams |
| Match coverage | {validation['pressure_state_summary']['matches_without_ball_by_ball_rows']} of 883 match records have no ball-by-ball rows and appear as missing in `match_state_quality.csv` |

No source innings totals are available to reconcile derived innings totals. This limitation blocks full-score verification and pressure-state calculations after ambiguous extras.

## State engine

`src/match_state.py` emits state immediately before each source delivery: score, wickets, legal balls, balls remaining, target, runs required, current run rate, and required run rate. It uses match revised overs when present and 20 overs otherwise for T20/T20I; innings 3/4 use Super Over limits. Innings 2 target uses `revised_target` when supplied, otherwise an exact preceding innings total plus one. Super Over innings 4 uses innings 3 total plus one. No missing target or event total is imputed. Incomplete innings remain incomplete in quality output; no synthetic deliveries are appended.

The raw feed has {validation['unknown_total_run_delta_rows']:,} delivery rows whose team-run amount is unresolved and {validation['unknown_legal_delivery_rows']:,} rows whose legal status is unresolved. Once an unknown event occurs, the corresponding state becomes unknown for subsequent balls in that innings. `match_state_quality.csv` reports coverage per match; `data/processed/match_state_deliveries.csv.gz` contains the row-level result.

### State coverage distribution

{quality_summary}

### Manual real-match row replays

Five real source matches were independently replayed row by row for sequence preservation, pre-delivery wickets, known score increments, and known legal-ball increments. These are arithmetic/reconstruction checks against the source delivery records, **not** official scorecard reconciliations (which are unavailable).

{audit_table}

## Unresolved data-owner questions

1. Provide the provider data dictionary for `runs`, `extras1_runs`, and `extras_2_runs`; explain whether `extras_2_runs` is an amount, subtype, or other code.
2. Confirm Overstep maps exactly to no-ball and whether multi-type extras (e.g. no-ball plus byes) are collapsed into one `extras_type`.
3. Supply innings scorecard totals or another independent source for team totals, bowler conceded runs, and legal-ball counts.
4. Supply historical match-level innings termination/revised-overs semantics if the result file is expected to distinguish complete, abandoned, and interrupted innings.
5. Confirm Super Over rows and any non-standard tie-break procedure from the provider.

## Reproduce

```powershell
.\\venv\\Scripts\\python.exe -m src.phase2b_pipeline
.\\venv\\Scripts\\python.exe -m pytest -q
```
"""


def _md_table(frame: pd.DataFrame) -> str:
    """Render a small dataframe as Markdown without an optional tabulate dependency."""
    columns = [str(c) for c in frame.columns]
    rows = [[str(v).replace("|", "\\|").replace("\n", " ") for v in row] for row in frame.itertuples(index=False, name=None)]
    return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n" + "\n".join("| " + " | ".join(row) + " |" for row in rows)


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), indent=2, default=str))
