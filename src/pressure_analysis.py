"""Pressure-analysis feasibility from source-supported delivery observations.

This module emits descriptive delivery features and coverage evidence. It does not
produce player ratings, fill missing score deltas, or label proxies as genuine pressure.
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"

NON_BOWLER_DISMISSALS = {
    "runout", "retire out", "obstracting the field", "obstructing the field",
    "retired hurt", "retired out",
}
BOWLER_CREDITED_DISMISSALS = {"bowled", "caught", "lbw", "stump", "hit wicket"}


def build_pressure_features(ball: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    """Join source events to reconstructed states and add conservative features."""
    keys = ["match_id", "innings", "innings_ball_num"]
    if not set(keys).issubset(ball) or not {"match_id", "innings", "sequence"}.issubset(states):
        raise ValueError("Source and state data must contain match/innings/delivery sequence keys")
    state_cols = [c for c in ["match_id", "innings", "sequence", "score_before", "score_known", "target",
        "runs_required", "legal_balls_remaining", "legal_balls_known", "wickets_lost_before",
        "legal_balls_bowled_before", "legal_delivery"] if c in states]
    left = ball.copy().rename(columns={"innings_ball_num": "sequence"})
    out = left.merge(states[state_cols], on=["match_id", "innings", "sequence"], how="left", validate="one_to_one")

    labels = out["extras_type"].astype("string").str.casefold()
    runs = pd.to_numeric(out["runs"], errors="coerce")
    out["ordinary_delivery"] = labels.isna() & pd.to_numeric(out["extras_2_runs"], errors="coerce").eq(0)
    out["batter_runs_verified_subset"] = runs.where(out["ordinary_delivery"])
    out["batter_runs_subset_status"] = "omitted: extras semantics unresolved"
    out.loc[out["ordinary_delivery"], "batter_runs_subset_status"] = "source runs on ordinary delivery; partial subset"
    out["balls_faced_verified_subset"] = out["ordinary_delivery"].astype("int8")
    out["four_event"] = out["is_four"].fillna(False).astype(bool)
    out["six_event"] = out["is_six"].fillna(False).astype(bool)
    out["boundary_event"] = out["four_event"] | out["six_event"]
    out["dot_ball_verified_subset"] = out["ordinary_delivery"] & runs.eq(0)
    out["batter_dismissal_event"] = out["is_wicket"].fillna(False).astype(bool) & out["dismissed_player_id"].notna()
    dismissal = out["dismissal_type"].astype("string").str.strip().str.casefold()
    out["bowler_wicket_event"] = out["is_wicket"].fillna(False).astype(bool) & dismissal.isin(BOWLER_CREDITED_DISMISSALS)
    out["non_bowler_dismissal_event"] = out["is_wicket"].fillna(False).astype(bool) & dismissal.isin(NON_BOWLER_DISMISSALS)
    out["wickets_remaining"] = (10 - pd.to_numeric(out["wickets_lost_before"], errors="coerce")).clip(lower=0)
    super_over = pd.to_numeric(out["innings"], errors="coerce").ge(3)
    out.loc[super_over, "wickets_remaining"] = (2 - pd.to_numeric(out.loc[super_over, "wickets_lost_before"], errors="coerce")).clip(lower=0)
    over = pd.to_numeric(out["overid"], errors="coerce")
    out["innings_phase"] = pd.Series(pd.NA, index=out.index, dtype="string")
    regular = ~super_over & out["innings"].isin([1, 2]) & over.notna()
    out.loc[regular & over.le(6), "innings_phase"] = "powerplay (overs 1-6)"
    out.loc[regular & over.between(7, 15), "innings_phase"] = "middle (overs 7-15)"
    out.loc[regular & over.between(16, 20), "innings_phase"] = "death (overs 16-20)"
    out.loc[super_over, "innings_phase"] = "super over (separate)"
    out["match_state_pressure_eligible"] = (
        out.get("score_known", pd.Series(False, index=out.index)).fillna(False).astype(bool)
        & out.get("target", pd.Series(pd.NA, index=out.index)).notna()
        & out.get("runs_required", pd.Series(pd.NA, index=out.index)).notna()
        & out.get("legal_balls_remaining", pd.Series(pd.NA, index=out.index)).notna()
    )
    out["wicket_phase_proxy_eligible"] = out["innings_phase"].notna() & out["wickets_lost_before"].notna()
    out["delivery_context_proxy_eligible"] = (
        out["wicket_phase_proxy_eligible"] & out["pace_or_spin"].notna()
        & out["bowling_type"].notna()
    )
    return out


def feasibility_matrix(features: pd.DataFrame) -> pd.DataFrame:
    """Return calculation feasibility, prerequisites, reliability and caveats."""
    rows = [
        ("Batter runs / strike rate", "Sum `runs` for striker; 100 × runs / balls faced", "runs; striker_id; extras_type; extras_2_runs", "Partial only", "`runs` is verified as batter runs on ordinary deliveries. Extras-row attribution is unresolved, so no complete player runs or strike rate is emitted."),
        ("Balls faced", "Count batter-faced deliveries; exclude wides, include no-balls", "striker_id; extras_type; delivery validity", "Partial only", "Ordinary-row count is available as a subset. Overstep is inferred; other events and multi-type extras prevent a verified full denominator."),
        ("Boundaries", "Count is_four / is_six by striker", "striker_id; is_four; is_six", "Reliable event counts", "Flags agree with source runs across the feed; they do not by themselves repair missing runs or balls faced."),
        ("Dot balls", "Ordinary delivery with runs = 0", "striker_id; runs; extras_type; extras_2_runs", "Reliable subset", "Only ordinary rows counted; extras events are excluded because batter attribution and faced-ball semantics are unresolved."),
        ("Batter dismissals", "Count wicket events with dismissed_player_id by batter", "is_wicket; dismissed_player_id", "Reliable with one missing ID", "10,880 of 10,881 wicket events have a dismissed player ID. Use dismissal_type to audit edge cases."),
        ("Bowler wickets", "Count bowler-credit dismissal types by bowler", "is_wicket; dismissal_type; bowler_id", "Reliable for recognized types", "RunOut, Retire Out and Obstructing-field variants are not bowler credited; unknown labels must remain excluded."),
        ("Bowler economy", "Bowler-conceded runs × 6 / legal balls", "bowler-conceded runs; legal_delivery", "Not reliable", "No complete bowler-conceded-runs field; extras amounts are unresolved. Do not calculate."),
        ("Bowling strike rate", "Legal balls / bowler-credited wickets", "legal_delivery; dismissal_type; bowler_id", "Partial only", "Credited wickets are identifiable, but per-bowler legal-ball totals include unresolved event validity; no complete rate emitted."),
        ("Innings phase", "Powerplay 1-6, middle 7-15, death 16-20 using overid", "innings; overid", "Reliable descriptive context", "Uses source over index and conventional T20 phases; super overs separated. Phase is not proof of pressure."),
        ("Wickets remaining", "10 minus wickets lost; super over cap 2", "is_wicket; innings", "Reliable event-derived state", "Counted from source wicket flags before delivery; super-over interpretation follows Phase 2B candidate classification."),
        ("Match-state pressure", "Chase runs required and required rate with known score, target and balls remaining", "validated state fields", "Verified subset only", "Only when score/target/legal-ball state are known. This is the most defensible genuine match-pressure context; coverage is sparse."),
        ("Wicket and phase pressure", "Wickets lost crossed with innings phase", "is_wicket; innings; overid", "Reliable proxy", "Contextual proxy only; no claim that late overs or wickets alone equal psychological pressure."),
        ("Delivery situational difficulty", "Describe phase, wickets remaining, pace/spin and supplied delivery attributes", "overid; wicket state; pace_or_spin; bowling_type; bowl_speed; delivery_style", "Proxy features only", "Descriptive delivery context, not a validated difficulty score or causal pressure measure."),
    ]
    return pd.DataFrame(rows, columns=["metric", "calculation", "required_fields", "reliability", "limitations"])


def coverage_table(features: pd.DataFrame) -> pd.DataFrame:
    """Summarize row coverage and player/match sample sizes for alternatives."""
    total = len(features)
    masks = {
        "Match-state pressure (verified chase state)": features["match_state_pressure_eligible"],
        "Wicket and innings-phase proxy": features["wicket_phase_proxy_eligible"],
        "Delivery situational difficulty proxy": features["delivery_context_proxy_eligible"],
        "Ordinary-delivery batter runs / balls subset": features["ordinary_delivery"],
        "Boundary events": features["boundary_event"],
        "Dot-ball verified subset": features["dot_ball_verified_subset"],
        "Batter dismissal with player ID": features["batter_dismissal_event"],
        "Bowler-credited wicket event": features["bowler_wicket_event"],
        "Known legal delivery event": features["legal_delivery"].notna(),
    }
    records = []
    for metric, mask in masks.items():
        subset = features.loc[mask]
        records.append({
            "definition": metric,
            "delivery_rows_covered": int(mask.sum()),
            "delivery_rows_total": total,
            "delivery_coverage_pct": round(100 * mask.mean(), 3) if total else 0.0,
            "matches_covered": int(subset["match_id"].nunique()),
            "innings_covered": int(subset[["match_id", "innings"]].drop_duplicates().shape[0]),
            "strikers_covered": int(subset["striker_id"].nunique()) if "striker_id" in subset else 0,
            "bowlers_covered": int(subset["bowler_id"].nunique()) if "bowler_id" in subset else 0,
            "interpretation": _coverage_note(metric),
        })
    return pd.DataFrame(records)


def _coverage_note(metric: str) -> str:
    if metric == "Match-state pressure (verified chase state)":
        return "Verified state subset; excludes unknown score/target/ball states and first innings without a target."
    if metric in {"Wicket and innings-phase proxy", "Delivery situational difficulty proxy"}:
        return "Proxy context coverage; does not establish genuine match or psychological pressure."
    if metric == "Ordinary-delivery batter runs / balls subset":
        return "Partial ordinary-event subset only; not a complete batter innings denominator."
    if metric == "Known legal delivery event":
        return "Event-level legality only; does not guarantee complete per-bowler totals across innings."
    return "Event count coverage; do not interpret as complete player rate without denominator validation."


def run_pressure_analysis() -> dict[str, object]:
    """Create processed descriptive features and Phase 2C reports."""
    state_path = PROCESSED / "match_state_deliveries.csv.gz"
    if not state_path.exists():
        raise FileNotFoundError("Run `python -m src.phase2b_pipeline` before pressure analysis")
    ball = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    states = pd.read_csv(state_path, low_memory=False)
    features = build_pressure_features(ball, states)
    matrix = feasibility_matrix(features)
    coverage = coverage_table(features)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    feature_path = PROCESSED / "pressure_research_deliveries.csv.gz"
    features.to_csv(feature_path, index=False, compression="gzip")
    matrix.to_csv(REPORTS / "metric_feasibility.csv", index=False)
    coverage.to_csv(REPORTS / "pressure_coverage.csv", index=False)
    report = _report_markdown(features, matrix, coverage)
    (REPORTS / "pressure_feasibility_report.md").write_text(report, encoding="utf-8")
    return {"delivery_rows": len(features), "match_state_pressure_rows": int(features["match_state_pressure_eligible"].sum()),
            "wicket_phase_proxy_rows": int(features["wicket_phase_proxy_eligible"].sum()),
            "delivery_context_proxy_rows": int(features["delivery_context_proxy_eligible"].sum()),
            "feature_file": str(feature_path), "coverage_file": str(REPORTS / "pressure_coverage.csv")}


def _report_markdown(features: pd.DataFrame, matrix: pd.DataFrame, coverage: pd.DataFrame) -> str:
    cols = ["definition", "delivery_rows_covered", "delivery_rows_total", "delivery_coverage_pct", "matches_covered", "innings_covered"]
    inventory = [
        ("runs", "conditionally reliable", "`runs` matches batter-run totals on audited ordinary/selected public scorecard samples; use ordinary deliveries only for verified subset metrics. Extras-row attribution remains unresolved."),
        ("extras_type", "uncertain outside explicit categories", "Category labels are observed, but multiple extras and actual amounts are undocumented."),
        ("extras1_runs", "unusable as an amount", "Exact category-like codes; never a run total."),
        ("extras_2_runs", "uncertain", "Sparse values 0/1/4; scope and attachment are undocumented."),
        ("is_four / is_six", "reliable event flags", "Previously cross-checked against runs values across all rows."),
        ("is_wicket", "reliable event flag", "Matches non-null dismissal labels in the Phase 2B audit; wicket count does not equal bowler wickets."),
        ("dismissal_type", "reliable when populated; labels need mapping", "Necessary to distinguish batter dismissal and bowler-credit types; two Obstructing-field spellings occur."),
        ("dismissal_type_id", "uncertain code", "Available on dismissal rows but no provider mapping is supplied; use the text label for conservative dismissal classification."),
        ("dismissed_player_id", "reliable with one missing wicket ID", "10,880/10,881 wicket events identify a dismissed batter."),
        ("match_id / batting_team_id / bowling_team_id", "reliable join/context keys", "Present on source deliveries; suitable for grouping, not performance outcomes."),
        ("striker_id / bowler_id", "reliable event attribution keys", "Present on delivery rows; counts do not repair incomplete run/ball denominators."),
        ("striker_name / bowler_name", "display labels", "Useful for exploration; use numeric IDs for joins and aggregation because names may vary or collide."),
        ("non_striker_id / non_striker_name", "reliable event context / display label", "Identifies the partner at the event; not a measure of who faced the ball or scored."),
        ("batting_type", "reliable categorical descriptor", "Observed batter handedness label; descriptive matchup feature, not a pressure measure."),
        ("batting_order", "reliable source context", "Observed order field; does not indicate the number of balls faced or a pressure state."),
        ("overid / innings", "reliable context fields", "Support descriptive T20 phase. Super over innings 3/4 are separated."),
        ("over_ball_num / innings_ball_num", "reliable sequence context", "Source ordering fields; innings_ball_num is the unique match/innings sequence key used in Phase 2B."),
        ("legal_delivery", "reliable only where classified", "Known on ordinary, wide, inferred Overstep, bye and leg-bye categories; other/Penalty remain unknown."),
        ("batter_runs_candidate", "uncertain for complete scoring", "Ordinary-row values supported as batter runs; do not total ambiguous extras events."),
        ("bowl_speed / bowling_type / pace_or_spin / delivery_style / stroke / on_or_off / over_or_around", "descriptive; not calibrated", "Supplied delivery context features; no validated difficulty or pressure weights."),
        ("delivery_ist_time", "unusable for this pressure definition", "Timestamp may preserve event order/time but no validated within-match pressure or rest-period interpretation is available."),
        ("score_before / target / runs_required / legal_balls_remaining", "verified only where state flags allow", "Use match-state pressure only when score, target and legal-ball state are present and known."),
    ]
    inv = pd.DataFrame(inventory, columns=["field", "classification", "evidence_and_limit"])
    dismissal_count = int(features["batter_dismissal_event"].sum())
    wicket_count = int(features["is_wicket"].fillna(False).sum())
    credited_count = int(features["bowler_wicket_event"].sum())
    return f"""# Phase 2C — Pressure Analysis Feasibility

## Executive finding

The most defensible primary definition is **verified match-state pressure**: a chase delivery for which the reconstructed score, target, runs required and legal balls remaining are all known. It describes actual match demands, but its sparse coverage makes it unsuitable as the only analysis. Use wicket-and-phase context as a clearly named proxy with broader coverage, and use delivery attributes only as descriptive covariates. Do not equate late overs with pressure, and do not produce player rankings from partial denominators.

## Source field audit

The classifications below refer to the 200,999 source deliveries and the Phase 2B evidence. “Reliable” means fit for the stated narrow use, not universal semantic certainty.

{_md_table(inv)}

## Metric feasibility

{_md_table(matrix)}

Wicket checks: source has {wicket_count:,} flagged wicket events; {dismissal_count:,} have a dismissed-player ID. {credited_count:,} events use recognized bowler-credit dismissal labels (Bowled, Caught, LBW, Stump, Hit Wicket). RunOut, Retire Out and Obstructing-field variants are excluded from bowler wickets. Bowling economy is blocked because bowler-conceded runs are not recoverable from the supplied fields.

## Alternative pressure definitions and coverage

{_md_table(coverage[cols])}

1. **Match-state pressure (genuine match context):** use only known chase state and calculate runs required / balls remaining and required rate. State pressure is undefined for non-chases and excluded once score or legal-ball state becomes unknown. It is match context, not a claim about each player's mental state.
2. **Wicket and innings-phase proxy:** combine wickets lost before the ball with powerplay/middle/death phase from `overid`; separate super overs. This is a situational proxy, never “pressure performance” by itself.
3. **Delivery-level situational difficulty proxy:** retain phase, wickets remaining, pace/spin, bowling type, speed, line/trajectory and stroke labels as observable context. No composite difficulty score is created because weights and calibration evidence are absent.

## Implemented scope and limitations

`data/processed/pressure_research_deliveries.csv.gz` contains row-level descriptive features. Verified-subset batter runs, balls faced and dots are limited to ordinary deliveries. Boundary and wicket events are retained as event counts; they are not divided into full player rates. Dismissal credit is explicit by recognized type. No missing runs, targets, legal balls, or player totals are imputed. Original CSVs and existing Phase 1/2B modules are unchanged.

The feature file and dashboard show distributions and coverage, not rankings. Even a complete observable field is not evidence of causal pressure: opponent strength, match stakes, player role, venue conditions and scorecard validation are not yet incorporated.

## Recommendation

Use verified match-state pressure as the primary research cohort because it has a cricket-grounded, auditable definition. Pair it with wicket-and-phase context for coverage, clearly label it as a proxy, and report sample sizes beside every result. Keep delivery attributes descriptive until a model is validated against an independent outcome dataset. Exclude complete strike rate, dot rate, bowler economy and bowling strike rate from player comparisons until run attribution and delivery denominators are validated.

## Reproduce

```powershell
.\\venv\\Scripts\\python.exe -m src.pressure_analysis
.\\venv\\Scripts\\python.exe -m pytest -q
```
"""


def _md_table(frame: pd.DataFrame) -> str:
    columns = [str(c) for c in frame.columns]
    rows = [[str(v).replace("|", "\\|").replace("\n", " ") for v in row] for row in frame.itertuples(index=False, name=None)]
    return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n" + "\n".join("| " + " | ".join(row) + " |" for row in rows)


if __name__ == "__main__":
    import json
    print(json.dumps(run_pressure_analysis(), indent=2, default=str))
