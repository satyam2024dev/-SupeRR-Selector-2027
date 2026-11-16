"""Phase 3A.1 alternative pressure/baseline feasibility; no scoring or rankings."""
from __future__ import annotations

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
REPORTS = ROOT / "outputs" / "reports"
METHODS = [
    "exact_match_phase_wickets",
    "within_match_phase",
    "within_player_comparable_matches",
]


def state_frame(features: pd.DataFrame, matches: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    context = matches[["match_id", "comp_id"]].merge(
        competitions[["comp_id", "match_format", "season"]], on="comp_id", how="left", validate="many_to_one")
    frame = features.loc[features["match_state_pressure_eligible"].fillna(False)].merge(
        context, on="match_id", how="left", validate="many_to_one")
    frame = frame.loc[(pd.to_numeric(frame.innings, errors="coerce") == 2)
                      & (pd.to_numeric(frame.legal_balls_remaining, errors="coerce") > 0)].copy()
    balls_bowled = pd.to_numeric(frame["legal_balls_bowled_before"], errors="coerce")
    frame["required_run_rate"] = pd.to_numeric(frame.runs_required, errors="coerce") * 6 / pd.to_numeric(frame.legal_balls_remaining, errors="coerce")
    frame["current_run_rate"] = pd.to_numeric(frame.score_before, errors="coerce") * 6 / balls_bowled.where(balls_bowled > 0)
    frame["rate_gap"] = frame["required_run_rate"] - frame["current_run_rate"]
    frame = frame.loc[frame.required_run_rate.notna()].copy()
    frame["pressure_state"] = frame["rate_gap"] > 0
    frame["phase_key"] = frame["innings_phase"].astype("string")
    frame["wickets_lost_key"] = pd.to_numeric(frame["wickets_lost_before"], errors="coerce")
    frame["wickets_remaining_key"] = pd.to_numeric(frame["wickets_remaining"], errors="coerce")
    return frame


def pressure_definitions(frame: pd.DataFrame) -> dict[str, tuple[pd.Series, pd.Series, str]]:
    """Return high and lower-demand masks; values use only existing known state."""
    q75_rrr = frame.required_run_rate.quantile(.75)
    q50_rrr = frame.required_run_rate.quantile(.50)
    gap = frame.rate_gap.dropna()
    q75_gap = gap.quantile(.75) if len(gap) else float("nan")
    q25_gap = gap.quantile(.25) if len(gap) else float("nan")
    q25_balls = pd.to_numeric(frame.legal_balls_remaining, errors="coerce").quantile(.25)
    q25_wickets = frame.wickets_remaining_key.quantile(.25)
    squeeze = (frame.legal_balls_remaining.le(q25_balls) | frame.wickets_remaining_key.le(q25_wickets))
    low_resource = (frame.legal_balls_remaining.gt(q25_balls) & frame.wickets_remaining_key.gt(q25_wickets))
    runs_per_wicket = frame.runs_required.div(frame.wickets_remaining_key.where(frame.wickets_remaining_key > 0))
    q75_rpw = runs_per_wicket.dropna().quantile(.75)
    q25_rpw = runs_per_wicket.dropna().quantile(.25)
    return {
        "behind_required_rate_primary": (frame.current_run_rate.notna() & frame.rate_gap.gt(0), frame.current_run_rate.notna() & frame.rate_gap.le(0), "RRR > CRR vs RRR ≤ CRR; first-ball CRR-unknown rows excluded"),
        "high_absolute_required_rate_q75": (frame.required_run_rate.ge(q75_rrr), frame.required_run_rate.le(q50_rrr), f"RRR ≥ overall Q75 ({q75_rrr:.3f}) vs RRR ≤ Q50 ({q50_rrr:.3f}); middle group excluded"),
        "high_rate_gap_q75": (frame.current_run_rate.notna() & frame.rate_gap.ge(q75_gap), frame.current_run_rate.notna() & frame.rate_gap.le(q25_gap), f"RRR−CRR ≥ gap Q75 ({q75_gap:.3f}) vs ≤ gap Q25 ({q25_gap:.3f}); middle excluded"),
        "behind_rate_and_low_resource": (frame.current_run_rate.notna() & frame.rate_gap.gt(0) & squeeze,
                                         frame.current_run_rate.notna() & frame.rate_gap.le(0) & low_resource,
                                         f"Behind rate plus balls-left or wickets-left in bottom quartile (balls Q25={q25_balls:.1f}; wickets-left Q25={q25_wickets:.1f}) vs at/ahead with neither low resource"),
        "high_runs_required_per_wicket": (runs_per_wicket.notna() & runs_per_wicket.ge(q75_rpw), runs_per_wicket.notna() & runs_per_wicket.le(q25_rpw),
                                          f"Runs required / wickets remaining ≥ Q75 ({q75_rpw:.3f}) vs ≤ Q25 ({q25_rpw:.3f}); excludes zero wickets and middle"),
    }


def _paired_population(frame: pd.DataFrame, high: pd.Series, low: pd.Series, method: str, role: str | None = None) -> pd.DataFrame:
    base = frame.loc[high | low].copy()
    base["_high"] = high.loc[base.index].astype(bool)
    if method == "exact_match_phase_wickets":
        keys = ["match_id", "phase_key", "wickets_lost_key"]
        counts = base.groupby(keys, dropna=False)["_high"].nunique()
        keep = counts[counts == 2].reset_index()[keys]
        return base.merge(keep, on=keys, how="inner", validate="many_to_one")
    if method == "within_match_phase":
        keys = ["match_id", "phase_key"]
        counts = base.groupby(keys, dropna=False)["_high"].nunique()
        keep = counts[counts == 2].reset_index()[keys]
        return base.merge(keep, on=keys, how="inner", validate="many_to_one")
    if method == "within_player_comparable_matches":
        # Retain each player's pressure/baseline observations only where both occur
        # in comparable format-season-phase-wicket contexts in different matches.
        keys = ["match_format", "season", "phase_key", "wickets_lost_key"]
        pieces = []
        player_cols = (["striker_id"] if role == "batter" else ["bowler_id"] if role == "bowler" else ["striker_id", "bowler_id"])
        for player_col in player_cols:
            for _, group in base.dropna(subset=[player_col]).groupby([player_col, *keys], dropna=False, sort=False):
                p = group.loc[group._high]
                b = group.loc[~group._high]
                if p.empty or b.empty:
                    continue
                p_matches = set(p.match_id)
                b_matches = set(b.match_id)
                # Require disjoint match evidence so the baseline is across matches.
                p_ok = p.loc[p.match_id.map(lambda mid: any(other != mid for other in b_matches))]
                b_ok = b.loc[b.match_id.map(lambda mid: any(other != mid for other in p_matches))]
                if not p_ok.empty and not b_ok.empty:
                    pieces.extend([p_ok, b_ok])
        if not pieces:
            return base.iloc[0:0].copy()
        return pd.concat(pieces).drop_duplicates(subset=["match_id", "innings", "sequence", "_high"]).sort_index()
    raise ValueError(f"Unknown matching method: {method}")


def _role_exposures(population: pd.DataFrame, role: str) -> dict[str, object]:
    if role == "batter":
        population = population.loc[population.ordinary_delivery.fillna(False)].copy()
        player_col = "striker_id"
    else:
        player_col = "bowler_id"
    result: dict[str, object] = {}
    groups = {}
    for high, label in [(True, "pressure"), (False, "baseline")]:
        sub = population.loc[population._high.eq(high)]
        grouped = sub.groupby(player_col).agg(events=("match_id", "size"), matches=("match_id", "nunique"))
        groups[label] = grouped
        result[f"{label}_events"] = len(sub)
        result[f"{label}_players"] = int(sub[player_col].nunique())
        result[f"{label}_matches"] = int(sub.match_id.nunique())
        result[f"{label}_match_ids"] = ";".join(map(str, sorted(sub.match_id.dropna().unique())))
    p, b = groups["pressure"], groups["baseline"]
    intersection = p.index.intersection(b.index)
    p = p.reindex(intersection, fill_value=0)
    b = b.reindex(intersection, fill_value=0)
    result["players_both_cohorts"] = int(len(intersection))
    result["pressure_event_q25"] = float(groups["pressure"].events.quantile(.25)) if len(groups["pressure"]) else 0.0
    result["pressure_event_median"] = float(groups["pressure"].events.median()) if len(groups["pressure"]) else 0.0
    result["pressure_event_q75"] = float(groups["pressure"].events.quantile(.75)) if len(groups["pressure"]) else 0.0
    result["baseline_event_q25"] = float(groups["baseline"].events.quantile(.25)) if len(groups["baseline"]) else 0.0
    result["baseline_event_median"] = float(groups["baseline"].events.median()) if len(groups["baseline"]) else 0.0
    result["baseline_event_q75"] = float(groups["baseline"].events.quantile(.75)) if len(groups["baseline"]) else 0.0
    result["pressure_matches_q25"] = float(groups["pressure"].matches.quantile(.25)) if len(groups["pressure"]) else 0.0
    result["baseline_matches_q25"] = float(groups["baseline"].matches.quantile(.25)) if len(groups["baseline"]) else 0.0
    result["pressure_matches_median"] = float(groups["pressure"].matches.median()) if len(groups["pressure"]) else 0.0
    result["baseline_matches_median"] = float(groups["baseline"].matches.median()) if len(groups["baseline"]) else 0.0
    return result


def _eligible(p: pd.DataFrame, role: str, floors: dict[str, int]) -> int:
    player_col = "striker_id" if role == "batter" else "bowler_id"
    exp = {}
    for value, label in [(True, "p"), (False, "b")]:
        sub = p.loc[p._high.eq(value)]
        exp[label] = sub.groupby(player_col).agg(events=("match_id", "size"), matches=("match_id", "nunique"))
    intersection = exp["p"].index.intersection(exp["b"].index)
    pstats = exp["p"].reindex(intersection, fill_value=0)
    bstats = exp["b"].reindex(intersection, fill_value=0)
    pm = pstats.events.ge(floors["pressure_events"]) & pstats.matches.ge(floors["pressure_matches"])
    bm = bstats.events.ge(floors["baseline_events"]) & bstats.matches.ge(floors["baseline_matches"])
    return int((pm & bm).sum())


def _build_outputs(features: pd.DataFrame, frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    definitions = pressure_definitions(frame)
    method_rows, sensitivity_rows = [], []
    method_cache = {}
    for definition, (high, low, description) in definitions.items():
        for method in METHODS:
            for role in ("batter", "bowler"):
                population = _paired_population(frame, high, low, method, role)
                method_cache[(definition, method, role)] = population
                exposure = _role_exposures(population, role)
                floors = {"batter": {"pressure_events": 2, "pressure_matches": 2, "baseline_events": 16, "baseline_matches": 3},
                          "bowler": {"pressure_events": 5, "pressure_matches": 2, "baseline_events": 37, "baseline_matches": 2}}[role]
                method_rows.append({"pressure_definition": definition, "definition_rule": description,
                    "baseline_method": method, "role": role, "pressure_metric_events": exposure["pressure_events"],
                    "baseline_metric_events": exposure["baseline_events"], "pressure_players": exposure["pressure_players"],
                    "baseline_players": exposure["baseline_players"], "players_in_both_cohorts": exposure["players_both_cohorts"],
                    "pressure_matches": exposure["pressure_matches"], "baseline_matches": exposure["baseline_matches"],
                    "matches_in_comparison": len(set(exposure["pressure_match_ids"].split(";")) & set(exposure["baseline_match_ids"].split(";"))) if method != "within_player_comparable_matches" else "cross-match; see cohort lists",
                    "eligible_players_phase2d_q1_floors": _eligible(population.loc[population.ordinary_delivery.fillna(False)] if role == "batter" else population, role, floors),
                    "phase2d_pressure_events_floor": floors["pressure_events"], "phase2d_pressure_matches_floor": floors["pressure_matches"],
                    "phase2d_baseline_events_floor": floors["baseline_events"], "phase2d_baseline_matches_floor": floors["baseline_matches"],
                    "pressure_event_q25": exposure["pressure_event_q25"], "pressure_event_median": exposure["pressure_event_median"],
                    "pressure_event_q75": exposure["pressure_event_q75"], "baseline_event_q25": exposure["baseline_event_q25"],
                    "baseline_event_median": exposure["baseline_event_median"], "baseline_event_q75": exposure["baseline_event_q75"],
                    "pressure_match_q25": exposure["pressure_matches_q25"], "baseline_match_q25": exposure["baseline_matches_q25"],
                    "note": "Coverage only; no player score or ranking."})
                if len(population):
                    floors_for_tier = [
                        ("Phase2D_Q1_floor", floors["pressure_events"], floors["pressure_matches"], floors["baseline_events"], floors["baseline_matches"]),
                        ("Paired_Q25_with_two_match_min", max(1, math.ceil(exposure["pressure_event_q25"])), max(2, math.ceil(exposure["pressure_matches_q25"])), max(1, math.ceil(exposure["baseline_event_q25"])), max(2, math.ceil(exposure["baseline_matches_q25"]))),
                        ("Paired_median_with_two_match_min", max(1, math.ceil(exposure["pressure_event_median"])), max(2, math.ceil(exposure["pressure_matches_median"])), max(1, math.ceil(exposure["baseline_event_median"])), max(2, math.ceil(exposure["baseline_matches_median"]))),
                        ("Paired_Q75_with_two_match_min", max(1, math.ceil(exposure["pressure_event_q75"])), max(2, math.ceil(exposure["pressure_matches_median"])), max(1, math.ceil(exposure["baseline_event_q75"])), max(2, math.ceil(exposure["baseline_matches_median"]))),
                    ]
                else:
                    floors_for_tier = [("Phase2D_Q1_floor", floors["pressure_events"], floors["pressure_matches"], floors["baseline_events"], floors["baseline_matches"])]
                role_population = population.loc[population.ordinary_delivery.fillna(False)] if role == "batter" else population
                for tier, pe, pm, be, bm in floors_for_tier:
                    sensitivity_rows.append({"pressure_definition": definition, "baseline_method": method, "role": role,
                        "threshold_tier": tier, "pressure_events_min": pe, "pressure_matches_min": pm,
                        "baseline_events_min": be, "baseline_matches_min": bm,
                        "pressure_events_available": exposure["pressure_events"], "baseline_events_available": exposure["baseline_events"],
                        "pressure_players_available": exposure["pressure_players"], "baseline_players_available": exposure["baseline_players"],
                        "players_meeting_both_cohort_floors": _eligible(role_population, role, {"pressure_events": pe, "pressure_matches": pm, "baseline_events": be, "baseline_matches": bm}),
                        "pressure_matches": exposure["pressure_matches"], "baseline_matches": exposure["baseline_matches"],
                        "threshold_basis": "Phase 2D observed Q1 floors" if tier == "Phase2D_Q1_floor" else "empirical pressure/baseline exposure quantiles within this method and definition; retain ≥2 matches each",
                        "ranking": "not produced"})
    return pd.DataFrame(method_rows), pd.DataFrame(sensitivity_rows), method_cache


def generate() -> dict[str, int]:
    if not FEATURES.is_file():
        raise FileNotFoundError("Run `python -m src.pressure_analysis` before Phase 3A.1")
    features = pd.read_csv(FEATURES, low_memory=False)
    matches = pd.read_csv(ROOT / "data" / "raw" / "matches.csv")
    competitions = pd.read_csv(ROOT / "data" / "raw" / "competitions.csv")
    frame = state_frame(features, matches, competitions)
    method_comparison, sensitivity, cache = _build_outputs(features, frame)
    REPORTS.mkdir(parents=True, exist_ok=True)
    method_comparison.to_csv(REPORTS / "alternative_method_comparison.csv", index=False)
    sensitivity.to_csv(REPORTS / "eligibility_sensitivity.csv", index=False)
    (REPORTS / "format_comparability.md").write_text(_format_report(frame, cache, method_comparison), encoding="utf-8")
    (REPORTS / "pressure_methodology_review.md").write_text(_review_report(frame, method_comparison, sensitivity), encoding="utf-8")
    return {"regular_state_rows": len(frame), "methods_compared": len(METHODS), "pressure_definitions": len(pressure_definitions(frame)),
            "comparison_rows": len(method_comparison), "sensitivity_rows": len(sensitivity)}


def _format_report(frame: pd.DataFrame, cache: dict, comparison: pd.DataFrame) -> str:
    format_lines = []
    for fmt, group in frame.groupby("match_format"):
        format_lines.append(f"| {fmt} | {len(group)} | {group.match_id.nunique()} | {group.required_run_rate.quantile(.75):.2f} | {int(group.pressure_state.sum()) if 'pressure_state' in group else int(group.rate_gap.gt(0).sum())} |")
    primary_by_format = []
    p_hi, p_lo, _ = pressure_definitions(frame)["behind_required_rate_primary"]
    for method in METHODS:
        for role in ("batter", "bowler"):
            subset = _paired_population(frame, p_hi, p_lo, method, role)
            for fmt, group in subset.groupby("match_format"):
                primary_by_format.append({"method": method, "role": role, "format": fmt, "paired_state_rows": len(group),
                    "pressure_rows": int(group._high.sum()), "baseline_rows": int((~group._high).sum()),
                    "matches": group.match_id.nunique()})
    fmt_table = "\n".join(format_lines)
    comp_table = "\n".join(f"| {r['method']} | {r['role']} | {r['format']} | {r['paired_state_rows']} | {r['pressure_rows']} | {r['baseline_rows']} | {r['matches']} |" for r in primary_by_format)
    q75_table = []
    for fmt, g in frame.groupby("match_format"):
        q75 = g.required_run_rate.quantile(.75)
        high = g.required_run_rate.ge(q75)
        q75_table.append(f"| {fmt} | {len(g)} | {g.match_id.nunique()} | {q75:.2f} | {int(high.sum())} | {g.loc[high, 'match_id'].nunique()} |")
    return f'''# Format comparability review

Phase 2 data mix IPL (`T20`) and international T20 (`T20I`). The current known regular chase-state subset is not balanced:

| Format | Known chase states with required rate | Matches | RRR Q75 | Behind current rate |
|---|---:|---:|---:|---:|
{fmt_table}

## Absolute required-rate pressure sensitivity

Format-specific Q75 thresholds and cohort sizes:

| Format | State rows | Matches | Format Q75 | Q75 pressure rows | Matches represented |
|---|---:|---:|---:|---:|---:|
{chr(10).join(q75_table)}

The T20/IPL sample is much smaller and the high-RRR tail is concentrated in very few matches. Format-specific standardization would be unstable; a pooled raw RRR threshold would favor whichever format has generally higher chase rates. Treat any alternative RRR threshold as sensitivity, not as a revised primary definition.

## Primary pressure definition by format and baseline design

| Baseline method | Role | Format | Paired state rows | Pressure | Baseline | Matches |
|---|---|---|---:|---:|---:|---:|
{comp_table}

Do not pool component changes or final scores across formats. If a future cohort grows, estimate and report format-specific effects first; a combined estimate requires a predeclared context adjustment and enough independent matches in each format. IPL and T20I differ in opposition, role, competition, seasons and match conditions.

Source feature rows with unknown score/target/ball state remain excluded. No cross-format conversion or external player join is used here.
'''


def _review_report(frame: pd.DataFrame, comparison: pd.DataFrame, sensitivity: pd.DataFrame) -> str:
    primary = comparison[comparison.pressure_definition.eq("behind_required_rate_primary")]
    exact = primary[primary.baseline_method.eq("exact_match_phase_wickets")]
    phase = primary[primary.baseline_method.eq("within_match_phase")]
    cross = primary[primary.baseline_method.eq("within_player_comparable_matches")]
    def show_rows(data: pd.DataFrame) -> str:
        return "\n".join(f"| {r.role} | {r.baseline_method} | {r.pressure_metric_events} | {r.baseline_metric_events} | {r.pressure_matches} | {r.baseline_matches} | {r.eligible_players_phase2d_q1_floors} |" for r in data.itertuples())
    max_eligible = int(comparison.eligible_players_phase2d_q1_floors.max()) if len(comparison) else 0
    return f'''# Phase 3A.1 — Pressure methodology review and alternative feasibility

## Finding and guardrails

The existing method's zero eligible players is a **coverage result**, not a reason to loosen the evidence rule. This review keeps the Phase 3A primary pressure definition (`RRR > CRR`) intact and evaluates alternatives as named sensitivity analyses. It does not alter Phase 2E acceptance; **no unresolved match is accepted**. No player scores or rankings are calculated.

Only Phase 2G eligible outcomes are considered: batter ordinary-subset runs/balls/SR/dots, boundary flags, and recognized bowler-credit wickets. No score/target is imputed. All pressure-state evidence comes from rows whose processed score, target and balls flags are known. The current Phase 2F status remains 0 accepted matches.

## Defensible match-state indicators

The regular chase state table has **{len(frame)}** rows with known score/target/required rate/balls remaining. Derived current rate is available on **{int(frame.current_run_rate.notna().sum())}** because the first delivery has no completed-ball denominator. Candidates tested:

1. **Behind required rate (current primary):** RRR > CRR; baseline is RRR ≤ CRR. This directly uses observed known state and remains the primary definition.
2. **High absolute RRR:** top quartile of observed regular-chase RRR; comparison group at/below median, with middle states excluded. It measures high pace demand but is format sensitive.
3. **Large pace deficit:** top quartile of RRR−CRR versus bottom quartile. This uses both demand and current pace; it is a stronger but smaller cohort.
4. **Rate deficit plus depleted resources:** behind RRR, plus balls remaining or wickets remaining in the observed bottom quartile; comparison is at/ahead of RRR with neither resource in the bottom quartile. This is an explicit conjunction, not a changed primary label.
5. **Runs required per wicket remaining:** top quartile versus bottom quartile, for states with wickets remaining. This is a state-derived sensitivity, not a validated win-probability or psychological-pressure measure.

Thresholds are computed from observed eligible state distributions and written into the CSV rule descriptions. These variants are not combined into a new single pressure definition. The full-ball state coverage remains only 321 deliveries in Phase 2C; regulation pressure indicators use this smaller known-state subset.

## Baseline comparison

The three requested baseline methods are compared in `alternative_method_comparison.csv`:

| Method | Primary control | Trade-off |
|---|---|---|
| Exact within-match, phase and wickets-lost | Same match, same phase, exact wickets lost; only strata containing both pressure classes | Strongest control for match conditions and wicket context; most sparse. |
| Within-match phase-matched | Same match and phase, with wicket state allowed to vary | Keeps match context and yields more rows; pressure/baseline can differ in wickets lost. Report wicket-state balance and do not imply full adjustment. |
| Within-player baseline across comparable matches | Same player, format, season, phase and exact wickets lost; baseline match differs from pressure match | More repeated player evidence where available; weaker match-context control and susceptible to opponent/venue/team changes. |

For each pressure indicator and role, the CSV reports pressure/baseline metric-event counts, players and matches, players in both cohorts, and eligible-player counts under Phase 2D Q1 floors. Batter metric events are ordinary deliveries only. Bowler exposure is observed delivery events; the outcome remains recognized bowler-credit wickets, never legal-ball strike rate.

## Eligibility sensitivity

`eligibility_sensitivity.csv` evaluates the Phase 2D Q1 floors and thresholds derived from each method/indicator's observed player event and match distributions (Q25, median, Q75). Every empirical tier retains at least two distinct matches for both the pressure and baseline sides. Match recurrence cannot be replaced by more deliveries from one match.

Across all tested definitions and methods, the largest Phase 2D-floor eligible-player count is **{max_eligible}**. Threshold rows show exactly where coverage comes from; no threshold is selected to target ten players. Shrinkage cannot rescue a player with no comparable baseline observations.

## Is shrinkage justified?

Hierarchical models can reduce noisy rate estimates when players have some repeated pressure and baseline observations, and can account for delivery clustering within matches. They cannot create unobserved baselines, repair missing extras, resolve player identity, or make the state population representative. Current counts are too sparse and format-imbalanced for stable player random effects and format-specific pressure effects. A future model could be a robustness analysis after more accepted state rows and independent matches accrue; it is not a current route to a defensible Top 10.

## Format comparison

`format_comparability.md` reports IPL/T20I state coverage and primary matched cohorts separately. The known-state distribution is strongly imbalanced, while the T20/IPL upper-tail RRR cohort is concentrated in few matches. Analyse formats separately; do not apply one pooled raw threshold or one pooled standardization. If the challenge requires one combined list, that requires a declared adjustment and enough within-format player evidence, which is not present.

## Bowler ranking feasibility

Bowler performance has only one eligible outcome here: recognized bowler-credit wicket events. Bowler-conceded runs, economy and conventional bowling strike rate remain blocked. The available denominator for comparisons is observed bowler events, not legal balls; any exposure-adjusted wicket residual is explicitly nonstandard. Match clustering, sparse paired baselines and unresolved player-level external mappings further limit inference. **The data do not support a reliable bowler Top 10**, even if a looser method returns more exposed players.

## Primary and exploratory recommendations

**Primary:** retain `RRR > CRR`; use within-match phase-matched baseline as the practical primary comparison design only if wicket-state distributions are reported and sensitivity checked against exact wickets-lost matching. If no player clears evidence floors, publish no pressure scores. Exact phase+wickets matching remains the strongest sensitivity/control and should be preferred whenever sample support permits.

**Exploratory:** use within-player baseline across comparable matches, separately by format and season, clearly labeled as exploratory. It relaxes match control and cannot establish causal pressure response. Wicket/phase strata remain contextual proxy descriptions only, never verified psychological pressure.

The competition's requirement for two Top 10 lists conflicts with the present evidence. The analysis can describe limited metric coverage and compare a small number of adequately observed cases if any pass the predeclared floors; it cannot defensibly guarantee ten eligible players per role. Lowering thresholds to satisfy the requested list length would trade away the evidence standard and is not recommended.

No scores or rankings were produced. Review the pressure alternatives, baseline choice and sensitivity floors before any scoring implementation.
'''


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
