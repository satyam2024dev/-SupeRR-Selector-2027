"""Phase 3A methodology design and evidence coverage audit (no player scores)."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
REPORTS = ROOT / "outputs" / "reports"

# Empirical screens carried forward from Phase 2D's observed exposure quartiles.
SAMPLE_FLOORS = {
    "batter": {"pressure_events_q1": 2, "pressure_matches_min": 2, "baseline_events_q1": 16, "baseline_matches_q1": 3},
    "bowler": {"pressure_events_q1": 5, "pressure_matches_min": 2, "baseline_events_q1": 37, "baseline_matches_q1": 2},
}


def build_state_cohorts(features: pd.DataFrame, matches: pd.DataFrame, competitions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Make state-confirmed behind/ahead groups, plus only directly matched strata.

    `pressure_state` means required run rate exceeds current rate in a known regular
    chase. It is a scoreboard-demand label, not a psychological-state label.
    """
    context = matches[["match_id", "comp_id"]].merge(competitions[["comp_id", "match_format", "season"]], on="comp_id", how="left", validate="many_to_one")
    state = features.loc[features["match_state_pressure_eligible"].fillna(False)].merge(context, on="match_id", how="left", validate="many_to_one")
    total_state_rows = len(state)
    # Regulation chase only; innings 4 Super Overs are kept out of the primary cohort.
    regular = state.loc[(pd.to_numeric(state["innings"], errors="coerce") == 2)
                        & (pd.to_numeric(state["legal_balls_remaining"], errors="coerce") > 0)].copy()
    regular_rows = len(regular)
    balls_bowled = pd.to_numeric(regular["legal_balls_bowled_before"], errors="coerce")
    regular["required_run_rate"] = pd.to_numeric(regular["runs_required"], errors="coerce") * 6 / pd.to_numeric(regular["legal_balls_remaining"], errors="coerce")
    regular["current_run_rate"] = pd.to_numeric(regular["score_before"], errors="coerce") * 6 / balls_bowled.where(balls_bowled > 0)
    known = regular.loc[regular["current_run_rate"].notna() & regular["required_run_rate"].notna()].copy()
    known["pressure_state"] = known["required_run_rate"] > known["current_run_rate"]
    known["state_class"] = known["pressure_state"].map({True: "behind_required_rate", False: "at_or_ahead_of_required_rate"})
    known["phase_match_key"] = known["innings_phase"].astype("string")
    keys = ["match_id", "match_format", "phase_match_key", "wickets_lost_before"]
    class_counts = known.groupby(keys, dropna=False)["pressure_state"].nunique()
    paired_keys = class_counts[class_counts == 2].reset_index()[keys]
    matched = known.merge(paired_keys, on=keys, how="inner", validate="many_to_one")
    q75 = float(known["required_run_rate"].quantile(.75)) if len(known) else float("nan")
    alt = known.loc[known["required_run_rate"] >= q75] if len(known) else known
    summary = {
        "all_state_rows": total_state_rows, "regular_chase_state_rows": regular_rows,
        "known_current_rate_rows": len(known), "unknown_current_rate_rows": regular_rows - len(known),
        "high_demand_rows": int(known["pressure_state"].sum()), "baseline_rows": int((~known["pressure_state"]).sum()),
        "high_demand_matches": int(known.loc[known.pressure_state, "match_id"].nunique()),
        "baseline_matches": int(known.loc[~known.pressure_state, "match_id"].nunique()),
        "paired_state_rows": len(matched), "paired_high_rows": int(matched.pressure_state.sum()),
        "paired_baseline_rows": int((~matched.pressure_state).sum()), "paired_matches": int(matched.match_id.nunique()),
        "paired_strata": len(paired_keys), "required_run_rate_q75": q75,
        "q75_rows": len(alt), "q75_matches": int(alt.match_id.nunique()),
        "format_counts": known.groupby("match_format").size().to_dict(),
        "format_q75": known.groupby("match_format")["required_run_rate"].quantile(.75).to_dict(),
        "phase_counts": known.groupby(["innings_phase", "state_class"], dropna=False).size().to_dict(),
    }
    return known, matched, summary


def _player_gate_counts(matched: pd.DataFrame) -> dict[str, dict[str, int]]:
    result = {}
    ordinary = matched["ordinary_delivery"].fillna(False).astype(bool)
    for role, id_col, cohort_mask in [
        ("batter", "striker_id", ordinary),
        ("bowler", "bowler_id", pd.Series(True, index=matched.index)),
    ]:
        groups = {}
        for is_pressure, label in [(True, "pressure"), (False, "baseline")]:
            subset = matched.loc[matched["pressure_state"].eq(is_pressure) & cohort_mask]
            grouped = subset.groupby(id_col).agg(events=("match_id", "size"), matches=("match_id", "nunique"))
            groups[label] = grouped
        p, b = groups["pressure"], groups["baseline"]
        intersection = p.index.intersection(b.index)
        p = p.reindex(intersection, fill_value=0)
        b = b.reindex(intersection, fill_value=0)
        floors = SAMPLE_FLOORS[role]
        p_pass = p.events.ge(floors["pressure_events_q1"]) & p.matches.ge(floors["pressure_matches_min"])
        b_pass = b.events.ge(floors["baseline_events_q1"]) & b.matches.ge(floors["baseline_matches_q1"])
        result[role] = {
            "pressure_players": int(len(groups["pressure"])), "baseline_players": int(len(groups["baseline"])),
            "both_cohorts_players": int(len(intersection)), "pressure_meeting_phase2d_floor": int(p_pass.sum()),
            "baseline_meeting_phase2d_floor": int(b_pass.sum()), "meeting_both_floors": int((p_pass & b_pass).sum()),
            "pressure_event_q1_observed": float(groups["pressure"].events.quantile(.25)) if len(groups["pressure"]) else 0.0,
            "baseline_event_q1_observed": float(groups["baseline"].events.quantile(.25)) if len(groups["baseline"]) else 0.0,
            "pressure_match_q1_observed": float(groups["pressure"].matches.quantile(.25)) if len(groups["pressure"]) else 0,
            "baseline_match_q1_observed": float(groups["baseline"].matches.quantile(.25)) if len(groups["baseline"]) else 0,
        }
    return result


def _design_tables(features: pd.DataFrame, matched: pd.DataFrame, summary: dict, gates: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordinary = matched["ordinary_delivery"].fillna(False).astype(bool)
    p_ord = int((matched.pressure_state & ordinary).sum())
    b_ord = int((~matched.pressure_state & ordinary).sum())
    bat = [
        {"framework": "Verified match-state pressure", "component": "Ordinary-subset strike-rate change", "phase2g_eligibility": "eligible_limited_subset", "pressure_definition": "Known regular chase with required run rate > current run rate", "normal_baseline": "At/ahead of required rate; exact same match, phase and wickets lost; ordinary rows only", "calculation": "SR_pressure − SR_baseline, where SR=100×ordinary batter runs/ordinary faced balls", "weight": "0.60", "sensitivity": "Compare 1.00 SR-only; 0.50/0.25/0.25; 0.40/0.30/0.30", "minimum_evidence": "Pressure ≥2 ordinary balls in ≥2 matches; baseline ≥16 ordinary balls in ≥3 matches (Phase 2D Q1 floors)", "current_evidence": f"{summary['paired_high_rows']} high-demand / {summary['paired_baseline_rows']} baseline state events; {p_ord} / {b_ord} ordinary rows; {gates['batter']['meeting_both_floors']} players meet both floors", "interpretation": "Primary scoring component; subset SR only, not conventional full strike rate."},
        {"framework": "Verified match-state pressure", "component": "Ordinary-subset dot-rate improvement", "phase2g_eligibility": "eligible_limited_subset", "pressure_definition": "Same known-state high-demand versus matched baseline", "normal_baseline": "Exact same match, phase and wickets lost; ordinary rows only", "calculation": "DotRate_baseline − DotRate_pressure; dots are ordinary rows with runs=0", "weight": "0.20", "sensitivity": "Remove this component or vary weight 0.15–0.30", "minimum_evidence": "Same paired exposure floors; numerator/denominator reported", "current_evidence": f"{p_ord} / {b_ord} matched ordinary rows; no player meets both full floors", "interpretation": "Lower dot share is favorable, but correlated with strike rate."},
        {"framework": "Verified match-state pressure", "component": "Ordinary-subset boundary frequency change", "phase2g_eligibility": "eligible_full_event_count; denominator uses eligible ordinary balls", "pressure_definition": "Same known-state high-demand versus matched baseline", "normal_baseline": "Exact same match, phase and wickets lost; ordinary rows only", "calculation": "BoundaryRate_pressure − BoundaryRate_baseline; (is_four+is_six)/ordinary faced balls", "weight": "0.20", "sensitivity": "Remove this component or vary weight 0.15–0.30", "minimum_evidence": "Same paired exposure floors; report fours/sixes and denominator", "current_evidence": f"{p_ord} / {b_ord} matched ordinary rows; no player meets both full floors", "interpretation": "Style diagnostic; correlated with strike rate."},
        {"framework": "Wicket/phase situational proxy", "component": "Ordinary-subset batting profile by phase × wickets lost", "phase2g_eligibility": "eligible_limited_subset", "pressure_definition": "Report wicket-loss and innings-phase strata as context only; no high-pressure label", "normal_baseline": "No normal-pressure baseline; show within-player/context strata separately", "calculation": "Ordinary-subset SR, dot rate and boundary frequency by stratum", "weight": "Not scored", "sensitivity": "Show alternate wicket/phase cuts; no composite proxy score", "minimum_evidence": "Expose row, match and innings counts for every stratum; no ranking threshold", "current_evidence": "189,166 ordinary rows across 867 matches/1,724 innings; 200,999 rows have proxy context", "interpretation": "Exploratory situational description only; never verified psychological pressure."},
    ]
    bowl = [
        {"framework": "Verified match-state pressure", "component": "Recognized bowler-credit wicket surplus", "phase2g_eligibility": "eligible_recognized_dismissals", "pressure_definition": "Known regular chase with required run rate > current run rate", "normal_baseline": "At/ahead of required rate; exact same match, phase and wickets lost; all observed bowling events as exposure", "calculation": "W_pressure − (W_baseline/N_baseline × N_pressure); exposure-adjusted expected credited wickets, not bowling strike rate", "weight": "1.00", "sensitivity": "Wicket-only; vary pressure definition (RRR>CRR vs top-quartile RRR) and leave-one-match-out", "minimum_evidence": "Pressure ≥5 bowled events in ≥2 matches; baseline ≥37 bowled events in ≥2 matches (Phase 2D Q1 floors)", "current_evidence": f"{summary['paired_high_rows']} / {summary['paired_baseline_rows']} matched event exposures; {gates['bowler']['meeting_both_floors']} players meet both floors", "interpretation": "Only eligible bowling outcome. Do not report as conventional bowling strike rate."},
        {"framework": "Wicket/phase situational proxy", "component": "Recognized bowler-credit wickets by phase × wickets lost", "phase2g_eligibility": "eligible_recognized_dismissals", "pressure_definition": "Describe credited wickets across phase and wicket-loss contexts; no high-pressure label", "normal_baseline": "No psychological-pressure baseline; show strata descriptively", "calculation": "Count recognized bowler-credit wickets; show bowled-event exposure and match clusters", "weight": "Not scored", "sensitivity": "Alternate phase/wicket strata; do not combine with verified-state score", "minimum_evidence": "Show credited wickets and observed event exposure; no Top-10 threshold", "current_evidence": "10,272 recognized credited wicket events in full source; proxy context covers 200,999 deliveries", "interpretation": "Descriptive context only. No economy, legal-ball rate, or bowling strike rate."},
    ]
    return pd.DataFrame(bat), pd.DataFrame(bowl)


def generate() -> dict[str, int]:
    if not FEATURES.is_file():
        raise FileNotFoundError("Run `python -m src.pressure_analysis` before Phase 3A")
    features = pd.read_csv(FEATURES, low_memory=False)
    matches = pd.read_csv(ROOT / "data" / "raw" / "matches.csv")
    competitions = pd.read_csv(ROOT / "data" / "raw" / "competitions.csv")
    known, matched, summary = build_state_cohorts(features, matches, competitions)
    gates = _player_gate_counts(matched)
    batter_design, bowler_design = _design_tables(features, matched, summary, gates)
    REPORTS.mkdir(parents=True, exist_ok=True)
    batter_design.to_csv(REPORTS / "batter_scoring_design.csv", index=False)
    bowler_design.to_csv(REPORTS / "bowler_scoring_design.csv", index=False)
    (REPORTS / "pressure_scoring_methodology.md").write_text(_methodology(features, known, matched, summary, gates), encoding="utf-8")
    (REPORTS / "scoring_risk_register.md").write_text(_risk_report(summary, gates), encoding="utf-8")
    return {"state_rows": summary["all_state_rows"], "known_regular_chase_rows": len(known), "matched_rows": len(matched),
            "batters_meeting_both_floors": gates["batter"]["meeting_both_floors"],
            "bowlers_meeting_both_floors": gates["bowler"]["meeting_both_floors"]}


def _methodology(features: pd.DataFrame, known: pd.DataFrame, matched: pd.DataFrame, s: dict, gates: dict) -> str:
    format_rows = "\n".join(f"| {fmt} | {n} | {s['format_q75'][fmt]:.2f} | {int(known.loc[known.match_format.eq(fmt), 'match_id'].nunique())} |" for fmt, n in s["format_counts"].items())
    sample_rows = "\n".join(
        f"| {role.title()} | {gates[role]['pressure_event_q1_observed']:.2f} / {gates[role]['baseline_event_q1_observed']:.2f} | "
        f"{gates[role]['pressure_match_q1_observed']:.2f} / {gates[role]['baseline_match_q1_observed']:.2f} | "
        f"{SAMPLE_FLOORS[role]['pressure_events_q1']} events, {SAMPLE_FLOORS[role]['pressure_matches_min']} pressure matches; "
        f"{SAMPLE_FLOORS[role]['baseline_events_q1']} baseline events, {SAMPLE_FLOORS[role]['baseline_matches_q1']} baseline matches |"
        for role in ("batter", "bowler"))
    return f'''# Phase 3A — Pressure scoring methodology design

## Review status and scope

This is a **methodology proposal for review**, not a scoring implementation. No player scores, rankings or Top 10 lists were generated. Phase 2E/2F full-match acceptance remains unchanged: **0 matches accepted**. State-confirmed rows can support a metric-specific research design while the enclosing match remains unresolved, but they do not make that match accepted.

Only Phase 2G-eligible outcomes are used: ordinary-subset batter runs/balls/strike rate/dots; validated boundary flags; and recognized bowler-credit wickets. Full bowler-conceded runs, economy and conventional bowling strike rate are excluded. The limited known-legal-ball subset is not used as a conventional bowling denominator.

## Pressure definitions and measured coverage

### Primary: verified match-state scoreboard demand

Use regular second-innings chase deliveries only when Phase 2B state flags say score, target, runs required and balls remaining are known. Exclude the first ball when current run rate cannot yet be calculated, and analyze Super Overs separately. Define current run rate as `score_before × 6 / legal_balls_bowled_before`; required run rate as `runs_required × 6 / legal_balls_remaining`. The proposed high-demand state is **required rate > current rate**; the comparison state is required rate ≤ current rate. This is an observable scoreboard-demand condition, not a measure of psychological pressure.

Of the Phase 2C total **321** state-known chase rows (28 matches), **{s['regular_chase_state_rows']}** are regular second-innings states and 3 belong to Super Overs. Current run rate is available for **{len(known)}** regular rows across {known.match_id.nunique()} matches: **{s['high_demand_rows']}** are behind the required rate and **{s['baseline_rows']}** are at/ahead. The remaining {s['unknown_current_rate_rows']} regular rows are the opening delivery in their chase and are excluded from this contrast.

Comparable baseline rule: pair only within the **same match, same innings phase, and exact wickets lost**. Retain only strata containing at least one high-demand and one comparison-state delivery. This leaves **{s['paired_state_rows']}** rows in **{s['paired_strata']}** paired strata across **{s['paired_matches']}** matches ({s['paired_high_rows']} high-demand; {s['paired_baseline_rows']} comparison). For the ordinary batter subset this becomes {int((matched.pressure_state & matched.ordinary_delivery.fillna(False)).sum())} high-demand and {int((~matched.pressure_state & matched.ordinary_delivery.fillna(False)).sum())} comparison deliveries. This is the only proposed normal-performance baseline; unknown-state deliveries are never called normal.

Current required-rate Q75 is **{s['required_run_rate_q75']:.2f} runs/over** overall. A Q75 absolute-rate sensitivity cohort contains {s['q75_rows']} rows in {s['q75_matches']} matches. Format coverage is uneven:

| Format | Known regular chase states | Q75 required rate | Matches |
|---|---:|---:|---:|
{format_rows}

The format-specific Q75 alternative is unstable for IPL/T20 (`T20`): the known-current-rate sample has 31 states in 4 matches, and its upper-quartile cohort falls in one match. Use it only as sensitivity analysis, not the primary rule. Do not pool T20I and IPL rates into one score.

### Separate: wicket/phase situational proxy

Phase 2C proxy context covers **200,999 deliveries, 867 matches and 1,724 innings**. Display batter outcomes by powerplay/middle/death phase and wickets lost, and bowler credited wickets by the same strata. Do not label the strata “verified pressure,” do not assign a psychological interpretation, and do not blend proxy output with the scoreboard-demand score. The proxy branch is descriptive only and has no composite score or normal-pressure baseline.

## Batter framework

Use the ordinary-delivery subset consistently for the numerator and denominator. The proposed paired components are: (1) ordinary-subset strike-rate change, (2) reduction in ordinary dot rate, and (3) change in ordinary boundary frequency. Boundary flags are valid event counts, but using ordinary events for the rate makes the denominator comparable to the eligible balls-faced subset. Do not use full-match runs, full balls faced, conventional strike rate, boundary-run share or full dot rate.

Proposed composite, calculated **within format only** after the minimum evidence screen:

`BatterScore = 0.60·z_f(SR_pressure − SR_baseline) + 0.20·z_f(DotRate_baseline − DotRate_pressure) + 0.20·z_f(BoundaryRate_pressure − BoundaryRate_baseline)`

`z_f` means standardize paired player deltas within the same format; if there is not a usable scale or sufficient matched cohort, report the three raw deltas and do not emit the composite. The 60% weight makes the eligible scoring-rate outcome primary; dot and boundary rates each contribute 20% as explanatory styles. These are transparent, judgment-based weights, not fitted or validated weights. Sensitivity: SR-only (100/0/0), balanced (50/25/25), and process-heavy (40/30/30). Their results must be compared before any ranking decision. SR, dot and boundary components are correlated, so the SR-only case is essential.

Design rows and current evidence are in `batter_scoring_design.csv`.

## Bowler framework

The only eligible bowling outcome is recognized bowler-credit wickets. Compare pressure wickets with the player's expected pressure wickets under the same matched baseline event yield:

`ExpectedW_pressure = (W_baseline / N_baseline) × N_pressure`

`BowlerResidual = W_pressure − ExpectedW_pressure`

`N` is the count of observed bowler delivery events in the matched state cohort and is an exposure offset, not legal balls. This proposed residual uses only the eligible recognized wicket count as the bowling outcome; it is **not** a conventional bowling strike rate, wickets per legal ball, economy rate, or bowler-conceded-runs measure. If reviewers require only standalone Phase 2G outcomes and disallow an event-exposure offset, the bowler framework must remain descriptive wicket counts with no pressure score. Weight is 100% credited-wicket residual because no other eligible bowling outcome exists. Sensitivity uses alternate pressure definitions and leave-one-match-out checks, not invented bowling metrics.

Design rows and current evidence are in `bowler_scoring_design.csv`.

## Minimum evidence and present baseline coverage

Phase 2D thresholds were derived from the actual player exposure distributions: batters—pressure Q1 2 ordinary deliveries in at least 2 matches; baseline Q1 16 deliveries in at least 3 matches. Bowlers—pressure Q1 5 delivery events in at least 2 matches; baseline Q1 37 events in at least 2 matches. These are screening floors, not proof of statistical stability. Require both cohorts to satisfy their role-specific floors after exact context matching, and report event counts and distinct matches beside every estimate.

The current matched-sample exposure distributions show why the inherited floors screen everyone out:

| Role | Matched-sample Q1 events (pressure / baseline) | Q1 distinct matches (pressure / baseline) | Phase 2D minimum floors |
|---|---:|---:|---|
{sample_rows}

In the stricter paired state sample, {gates['batter']['pressure_players']} batters have pressure observations and {gates['batter']['baseline_players']} have baseline observations; {gates['batter']['both_cohorts_players']} appear in both. **{gates['batter']['meeting_both_floors']}** meet both floors. For bowlers, {gates['bowler']['pressure_players']} have pressure observations and {gates['bowler']['baseline_players']} baseline observations; {gates['bowler']['both_cohorts_players']} appear in both, and **{gates['bowler']['meeting_both_floors']}** meet both floors. The baseline side is the bottleneck; do not lower the thresholds to manufacture a cohort.

Players below either cohort's floor receive **insufficient evidence**, not a zero score, penalty, or rank. A player without both pressure and comparable baseline evidence is not eligible for a pressure-retention estimate. Do not impute from scorecard totals, proxy deliveries, or another player.

## Clustering, format and bias controls

- The pressure opportunity is clustered by match/innings; treat deliveries as repeated observations, not independent samples. Use match-cluster bootstrap or leave-one-match-out stability only if the eligible cohort becomes large enough; report the number of clusters. With 14 matched matches, uncertainty estimates are not ranking-grade.
- Match and phase/wickets exact matching is designed to reduce context imbalance; it does not remove opponent, venue, batter role, bowling allocation, team strength or innings-selection bias.
- Report T20I and IPL separately. The T20I known-state sample is much larger than IPL; no pooled ranking or global standardization is justified by current coverage.
- Ordinary-only outcomes omit extra events. Batter exposure selection is not random; the restricted rows may overrepresent some innings and players.
- The Phase 2C/2D state-known pressure cohort is sparse and likely censored by unresolved scoring events. A completed match scorecard alone cannot reconstruct each delivery's pre-ball state.

## Challenge questions not yet answerable reliably

The data do not support defensible final batter/bowler Top 10 lists, complete conventional strike rates, full dot rates, boundary percentages, bowler economy or bowling strike rates. The current state-known baseline does not satisfy the evidence floors for any player under exact matching. Even if a few player pairs emerged, small samples, cluster count and T20I/IPL imbalance prevent robust comparative ranking. The official challenge's pressure-performance comparison against normal performance can be designed, but it cannot yet be answered reliably from current evidence.

No score has been applied. Implementation should wait for review of the pressure threshold, matching rule, sample floors, bowler exposure offset and weights.
'''


def _risk_report(s: dict, gates: dict) -> str:
    return f'''# Phase 3A — Scoring risk register

| Risk | Evidence / impact | Proposed control | Residual / decision |
|---|---|---|---|
| Pressure label overclaims psychology | `RRR > CRR` identifies scoreboard demand; it does not observe player mental state. | Label “verified match-state scoreboard demand”; call phase/wicket analysis a situational proxy. | Psychological pressure remains unmeasured. |
| State and match acceptance conflated | Phase 2F has 0 accepted matches; 321 rows have state-known flags. | Keep row-level state evidence separate from match-level acceptance; no match status changes. | Full-match supplemental dataset remains empty. |
| Sparse comparator baseline | Only {s['paired_state_rows']} observations in {s['paired_matches']} exact match/phase/wickets strata; {gates['batter']['meeting_both_floors']} batters and {gates['bowler']['meeting_both_floors']} bowlers meet both Q1 floors. | Require matched baseline and pressure evidence; mark others insufficient, no imputation. | No current player pressure-retention score is supportable. |
| Partial batting denominator | 189,166/200,999 rows are ordinary subset; extras attribution remains unresolved. | Restrict runs/balls/SR/dots/boundary frequencies to ordinary events; name each subset. | Selection bias remains and conventional rates are blocked. |
| Bowling outcome coverage | Recognized credited wickets available; conceded runs, economy and conventional bowling strike rate blocked. | Use credited wicket count only; exposure offset is explicit, nonstandard and subject to review. | No bowling control for runs conceded; wicket residual may be unstable. |
| Double-counting correlated batting components | SR, dot share and boundary rate overlap mathematically. | Make SR 60%; run SR-only and alternative-weight sensitivities; publish components. | Heuristic weights still require approval and robustness. |
| Match clustering | Delivery rows from the same match are dependent. Current paired states span {s['paired_matches']} matches. | Cluster inference by match; leave-one-match-out; show cluster and event counts. | Current cluster count is too small for robust rankings. |
| Format imbalance | Known regular chase states: T20 {s['format_counts'].get('T20', 0)}, T20I {s['format_counts'].get('T20I', 0)}. | Fit/standardize separately by format; do not pool final scores. | IPL/T20 comparison remains underpowered. |
| Proxy contamination | Wicket/phase contexts cover all source rows but are not validated match pressure. | Separate page/table/score namespace; proxy outputs descriptive only. | Users may still misread proxy strata without clear labels. |
| Threshold sensitivity | Primary RRR>CRR yields {s['high_demand_rows']} high-demand states; Q75 RRR gives {s['q75_rows']} states in {s['q75_matches']} matches. | Pre-specify primary definition; report Q75 and stricter combined rule as sensitivities. | Threshold choice can change cohort membership. |
| Selection/survivorship bias | Chase state depends on innings progress, score certainty, batting order and bowling allocation. | Compare same match/phase/wickets; report who is excluded and why. | Cannot remove unobserved role/opponent/venue differences. |
| False precision from z-scores | Small format cohorts may have unstable scale or zero variance. | If scale is unstable, show raw deltas only and withhold composite. | No single rankable score guaranteed. |
| External identity leakage | Candidate/ambiguous Cricsheet player/venue mappings remain in Phase 2F. | Use official local IDs only for local aggregates; do not import player-level scorecard evidence. | External player comparisons remain blocked. |
| Challenge completion claim | Final top-ten task cannot be reliably answered with current eligible evidence. | Report feasibility honestly; no Top 10 until data and evidence floors improve. | Competition submission may need provider data or clarification. |
'''


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
