"""Phase 3B descriptive player profiles from Phase 2G eligible scopes only.

No pressure scores, ranks, external records, or incomplete conventional rates are
produced. Pressure/baseline rows use the approved RRR > CRR, within-match-phase
paired comparison and are kept separate by format and cohort.
"""
from __future__ import annotations

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
REPORTS = ROOT / "outputs" / "reports"
BATTER_FLOORS = {"pressure_events": 2, "pressure_matches": 2, "baseline_events": 16, "baseline_matches": 3}
BOWLER_FLOORS = {"pressure_events": 5, "pressure_matches": 2, "baseline_events": 37, "baseline_matches": 2}


def add_format(features: pd.DataFrame, matches: pd.DataFrame, competitions: pd.DataFrame) -> pd.DataFrame:
    """Attach only official format metadata and label the IPL separately from T20I."""
    comp = competitions[["comp_id", "match_format", "comp_name", "season"]].copy()
    ctx = matches[["match_id", "comp_id"]].merge(comp, on="comp_id", how="left", validate="many_to_one")
    out = features.merge(ctx, on="match_id", how="left", validate="many_to_one")
    is_ipl = out.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False)
    out["analysis_format"] = pd.Series(pd.NA, index=out.index, dtype="string")
    out.loc[is_ipl, "analysis_format"] = "IPL"
    out.loc[out.match_format.eq("T20I"), "analysis_format"] = "T20I"
    return out


def build_primary_cohorts(features: pd.DataFrame) -> pd.DataFrame:
    """Select paired within-match/phase cohorts using known chase state only."""
    f = features.copy()
    f["score_before"] = pd.to_numeric(f.score_before, errors="coerce")
    f["balls_bowled"] = pd.to_numeric(f.legal_balls_bowled_before, errors="coerce")
    f["rrr"] = pd.to_numeric(f.runs_required, errors="coerce") * 6 / pd.to_numeric(f.legal_balls_remaining, errors="coerce")
    f["crr"] = f.score_before * 6 / f.balls_bowled.where(f.balls_bowled > 0)
    valid = (f.analysis_format.isin(["IPL", "T20I"]) & f.innings.eq(2)
             & f.match_state_pressure_eligible.fillna(False) & f.innings_phase.notna()
             & f.legal_balls_remaining.gt(0) & f.crr.notna() & f.rrr.notna())
    f = f.loc[valid].copy()
    f["_pressure"] = f.rrr.gt(f.crr)
    strata = f.groupby(["match_id", "innings_phase"], dropna=False)._pressure.nunique()
    paired = strata[strata.eq(2)].reset_index()[["match_id", "innings_phase"]]
    f = f.merge(paired, on=["match_id", "innings_phase"], how="inner", validate="many_to_one")
    f["cohort"] = f._pressure.map({True: "pressure", False: "normal_baseline"})
    f["state_observation"] = True
    return f.drop(columns="_pressure")


def _wilson(successes: int, n: int) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    z = 1.959963984540054
    p = successes / n
    den = 1 + z*z/n
    center = (p + z*z/(2*n)) / den
    half = z * math.sqrt((p*(1-p) + z*z/(4*n))/n) / den
    return max(0.0, center-half), min(1.0, center+half)


def _mean_ci(values: pd.Series, multiplier: float = 1.0) -> tuple[float | None, float | None, float | None]:
    x = pd.to_numeric(values, errors="coerce").dropna()
    if x.empty:
        return None, None, None
    mean = float(x.mean()) * multiplier
    if len(x) < 2:
        return mean, None, None
    se = float(x.std(ddof=1) / math.sqrt(len(x))) * multiplier
    return mean, mean - 1.96*se, mean + 1.96*se


def _batter_profile(group: pd.DataFrame, pid: object, name: str, fmt: str, cohort: str) -> dict:
    ordinary = group.loc[group.ordinary_delivery.fillna(False)].copy()
    runs = pd.to_numeric(ordinary.batter_runs_verified_subset, errors="coerce")
    balls = len(ordinary)
    scoring_rows = int(runs.notna().sum())
    run_sum = float(runs.sum(min_count=1)) if runs.notna().any() else None
    sr = 100 * run_sum / scoring_rows if scoring_rows and run_sum is not None else None
    sr_mean, sr_low, sr_high = _mean_ci(runs, 100)
    dot_n = int(ordinary.dot_ball_verified_subset.fillna(False).sum())
    dot_rate = dot_n / scoring_rows if scoring_rows else None
    dot_low, dot_high = _wilson(dot_n, scoring_rows)
    boundary_n = int(group.boundary_event.fillna(False).sum())
    boundary_den = len(group)
    boundary_rate = boundary_n / boundary_den if boundary_den else None
    boundary_low, boundary_high = _wilson(boundary_n, boundary_den)
    n_matches = int(group.match_id.nunique())
    return {
        "player_id": pid, "player_name": name, "format": fmt, "cohort": cohort,
        "observed_deliveries": len(group), "ordinary_subset_balls": balls, "ordinary_subset_scoring_rows": scoring_rows, "matches": n_matches,
        "innings": int(group[["match_id", "innings"]].drop_duplicates().shape[0]),
        "batter_runs_ordinary_subset": run_sum, "batter_runs_missing_ordinary_rows": int(runs.isna().sum()),
        "ordinary_subset_strike_rate": sr, "strike_rate_naive_95ci_low": sr_low,
        "strike_rate_naive_95ci_high": sr_high, "strike_rate_ci_note": "delivery-level normal approximation; clustered dependence ignored" if sr is not None else "unavailable",
        "ordinary_subset_dot_events": dot_n, "ordinary_subset_dot_rate": dot_rate,
        "dot_rate_wilson_95ci_low": dot_low, "dot_rate_wilson_95ci_high": dot_high,
        "boundary_events_full_eligible_scope": boundary_n, "boundary_event_rate_per_observed_delivery": boundary_rate,
        "boundary_rate_wilson_95ci_low": boundary_low, "boundary_rate_wilson_95ci_high": boundary_high,
        "descriptive_profile_usable": balls > 0,
    }


def _bowler_profile(group: pd.DataFrame, pid: object, name: str, fmt: str, cohort: str) -> dict:
    credit = group.bowler_wicket_event.fillna(False).astype(bool)
    extras = group.extras_type.astype("string").str.casefold()
    ordinary = group.ordinary_delivery.fillna(False).astype(bool)
    known_legal_subset = ordinary | (extras.isin(["byes", "legbyes"]) & group.legal_delivery.fillna(False).astype(bool))
    wickets = int(credit.sum())
    exposure = int(known_legal_subset.sum())
    # Keep numerator/denominator tied to the same eligible cohort; the full delivery
    # exposure is also reported and this ratio is explicitly not a bowling strike rate.
    legal_credit = int((credit & known_legal_subset).sum())
    ratio = legal_credit / exposure if exposure else None
    low, high = _wilson(legal_credit, exposure)
    return {
        "player_id": pid, "player_name": name, "format": fmt, "cohort": cohort,
        "observed_deliveries": len(group), "known_category_legal_delivery_exposure": exposure,
        "matches": int(group.match_id.nunique()), "innings": int(group[["match_id", "innings"]].drop_duplicates().shape[0]),
        "recognized_bowler_credit_wickets": wickets, "recognized_wickets_on_eligible_exposure": legal_credit,
        "wickets_per_known_category_legal_delivery": ratio,
        "wickets_per_delivery_wilson_95ci_low": low, "wickets_per_delivery_wilson_95ci_high": high,
        "ratio_limitation": "recognized wickets on eligible known-category legal deliveries only; not conventional bowling strike rate" if exposure else "no eligible denominator",
        "unclassified_legality_events": int(group.legal_delivery.isna().sum()),
        "descriptive_profile_usable": len(group) > 0,
    }


def build_profiles(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build separate role profiles and player-format evidence summary."""
    paired = build_primary_cohorts(features)
    bat_rows, bowl_rows, exposure_rows = [], [], []
    for (fmt, pid, cohort), group in paired.dropna(subset=["striker_id"]).groupby(["analysis_format", "striker_id", "cohort"], sort=True):
        names = group.striker_name.dropna().astype(str).mode()
        name = names.iloc[0] if len(names) else "Unknown"
        bat_rows.append(_batter_profile(group, pid, name, fmt, cohort))
    for (fmt, pid, cohort), group in paired.dropna(subset=["bowler_id"]).groupby(["analysis_format", "bowler_id", "cohort"], sort=True):
        names = group.bowler_name.dropna().astype(str).mode()
        name = names.iloc[0] if len(names) else "Unknown"
        bowl_rows.append(_bowler_profile(group, pid, name, fmt, cohort))
    batter = pd.DataFrame(bat_rows)
    bowler = pd.DataFrame(bowl_rows)
    for role, id_col, name_col, floors, profiles in [
        ("batter", "striker_id", "striker_name", BATTER_FLOORS, batter),
        ("bowler", "bowler_id", "bowler_name", BOWLER_FLOORS, bowler),
    ]:
        if paired.empty:
            continue
        for (fmt, pid), group in paired.dropna(subset=[id_col]).groupby(["analysis_format", id_col], sort=True):
            name_values = group[name_col].dropna().astype(str).mode()
            name = name_values.iloc[0] if len(name_values) else "Unknown"
            pressure_part = group.loc[group.cohort.eq("pressure")]
            baseline_part = group.loc[group.cohort.eq("normal_baseline")]
            side = {}
            for cohort in ("pressure", "normal_baseline"):
                part = group.loc[group.cohort.eq(cohort)]
                event_col = "ordinary_delivery" if role == "batter" else "state_observation"
                eligible_events = int(part[event_col].fillna(False).sum())
                side[cohort] = (eligible_events, int(part.match_id.nunique()))
            pe, pm = side["pressure"]
            be, bm = side["normal_baseline"]
            enough = (pe >= floors["pressure_events"] and pm >= floors["pressure_matches"]
                      and be >= floors["baseline_events"] and bm >= floors["baseline_matches"])
            def eligible_exposure(part: pd.DataFrame) -> int:
                if role == "batter":
                    return int(part.ordinary_delivery.fillna(False).sum())
                labels = part.extras_type.astype("string").str.casefold()
                ordinary_events = part.ordinary_delivery.fillna(False).astype(bool)
                return int((ordinary_events | (labels.isin(["byes", "legbyes"]) & part.legal_delivery.fillna(False).astype(bool))).sum())
            exposure_rows.append({"player_id": pid, "player_name": name, "role": role, "format": fmt,
                "pressure_observed_deliveries": len(pressure_part), "baseline_observed_deliveries": len(baseline_part),
                "pressure_evidence_events_for_phase2d_floor": pe, "pressure_eligible_delivery_exposure": eligible_exposure(pressure_part), "pressure_matches": pm,
                "baseline_evidence_events_for_phase2d_floor": be, "baseline_eligible_delivery_exposure": eligible_exposure(baseline_part), "baseline_matches": bm,
                "all_primary_cohort_matches": int(group.match_id.nunique()),
                "descriptive_profile_usable": bool(profiles.loc[(profiles.player_id.eq(pid)) & (profiles.format.eq(fmt)), "descriptive_profile_usable"].any()) if not profiles.empty else False,
                "sufficient_evidence_for_future_pressure_comparison": bool(enough),
                "pressure_event_floor": floors["pressure_events"], "pressure_match_floor": floors["pressure_matches"],
                "baseline_event_floor": floors["baseline_events"], "baseline_match_floor": floors["baseline_matches"],
                "pressure_score_status": "not calculated"})
    return batter, bowler, pd.DataFrame(exposure_rows)


def _limitations(batter: pd.DataFrame, bowler: pd.DataFrame, exposure: pd.DataFrame) -> str:
    def role_summary(role: str) -> tuple[int, int, int]:
        part = exposure[exposure.role.eq(role)] if not exposure.empty else exposure
        profiles = int(part.loc[part.descriptive_profile_usable, ["player_id", "format"]].drop_duplicates().shape[0]) if len(part) else 0
        future = int(part.loc[part.sufficient_evidence_for_future_pressure_comparison, ["player_id", "format"]].drop_duplicates().shape[0]) if len(part) else 0
        players = int(part.player_id.nunique()) if len(part) else 0
        return profiles, future, players
    bp, be, bplayers = role_summary("batter")
    wp, we, wplayers = role_summary("bowler")
    return f'''# Phase 3B — Player-level performance analytics prototype

## Scope and interpretation

Profiles use official local player IDs and Phase 2G eligible source scopes only. IPL and T20I appear separately. The primary comparison keeps Phase 3A.1's `RRR > CRR` definition and within-match, phase-matched pressure/baseline strata. It includes only known second-innings chase states where both cohorts occur in the same match and phase. “Normal baseline” means at/ahead of required rate in those paired chase contexts; it does not mean all normal performance or a complete player-season baseline.

The profile outputs are descriptive, not scores or rankings. A player's entries remain separate by pressure and baseline cohort. No missing extras, targets, legal balls, or player outcomes are filled. Phase 2E match acceptance is unchanged; external data are not joined.

## Descriptive profile counts

| Role | Player-format profiles usable | Distinct local players represented | Player-format pairs meeting Phase 2D floors |
|---|---:|---:|---:|
| Batter | {bp} | {bplayers} | {be} |
| Bowler | {wp} | {wplayers} | {we} |

Counts are based on the output rows and can include the same player in both formats. Phase 2D evidence floors are carried forward: batters require at least 2 ordinary pressure deliveries in 2 matches and 16 ordinary baseline deliveries in 3 matches; bowlers require at least 5 pressure events in 2 matches and 37 baseline events in 2 matches. Passing these floors only indicates future comparison exposure; no pressure score is calculated here.

## Metric definitions and uncertainty

- **Batter runs, balls and strike rate:** ordinary-delivery subset only. Balls faced counts all ordinary rows; strike rate and dot rate use only ordinary rows with an observed run value, so an unknown run is never treated as zero. Strike rate is not conventional full strike rate. Missing run rows are counted, not imputed.
- **Dot rate:** ordinary zero-run events / ordinary deliveries. **Boundary event rate:** verified four/six flags / all observed deliveries in that cohort. Boundary flags have broader event coverage than ordinary-only batting statistics.
- **Bowling:** recognized bowler-credit dismissal count only. The displayed limited ratio is recognized credited wickets on the Phase 2G known-category legal subset / those eligible legal delivery events. It is explicitly not conventional bowling strike rate, and it is not suitable as a ranking measure.
- Wilson intervals accompany event proportions. The batting strike-rate interval uses a delivery-level normal approximation. These intervals treat deliveries as independent; match clustering makes them optimistic, so they are descriptive uncertainty summaries, not inferential confidence intervals.
- Missingness columns count unobserved batter-run values among ordinary rows and unclassified delivery-legality events in the bowler cohort. Absent profile rows do not imply zero performance.

## Limitations

Only the paired, state-known cohort is profiled, so coverage is very small and selected by match-state reconstruction. The normal baseline is same-match and phase matched but can have a different wickets-lost state; this trade-off is from the approved Phase 3A.1 primary method. The exact wicket-state method remains a sensitivity, not silently substituted here.

IPL and T20I are not pooled. Role, opposition, season, venue, bowling allocation, batting order, and team strength remain uncontrolled. Event-level intervals do not account for match clustering. Batter ordinary-only outcomes omit extras events; bowler-conceded runs and economy remain blocked. No final pressure score, Top 10 list, or rank is produced.
'''


def generate() -> dict[str, int]:
    features = pd.read_csv(FEATURES, low_memory=False)
    matches = pd.read_csv(ROOT / "data" / "raw" / "matches.csv")
    competitions = pd.read_csv(ROOT / "data" / "raw" / "competitions.csv")
    enriched = add_format(features, matches, competitions)
    batter, bowler, exposure = build_profiles(enriched)
    REPORTS.mkdir(parents=True, exist_ok=True)
    batter.to_csv(REPORTS / "batter_performance_profile.csv", index=False)
    bowler.to_csv(REPORTS / "bowler_performance_profile.csv", index=False)
    exposure.to_csv(REPORTS / "player_exposure_summary.csv", index=False)
    (REPORTS / "player_analytics_limitations.md").write_text(_limitations(batter, bowler, exposure), encoding="utf-8")
    return {"batter_profile_rows": len(batter), "bowler_profile_rows": len(bowler), "exposure_rows": len(exposure),
            "batter_profiles_usable": int(exposure.loc[exposure.role.eq("batter") & exposure.descriptive_profile_usable, ["player_id", "format"]].drop_duplicates().shape[0]) if len(exposure) else 0,
            "bowler_profiles_usable": int(exposure.loc[exposure.role.eq("bowler") & exposure.descriptive_profile_usable, ["player_id", "format"]].drop_duplicates().shape[0]) if len(exposure) else 0,
            "future_pressure_comparison_pairs": int(exposure.sufficient_evidence_for_future_pressure_comparison.sum()) if len(exposure) else 0}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
