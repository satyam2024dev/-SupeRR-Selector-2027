import pandas as pd

from src.player_analytics import add_format, build_profiles, build_primary_cohorts


def _fixture():
    rows = []
    # Two pressure events and one at-rate event in one IPL match/phase.
    for seq, score, balls_bowled, runs in [(1, 0, 6, 4), (2, 0, 7, None), (3, 120, 60, 1)]:
        rows.append({
            "match_id": 1, "innings": 2, "innings_phase": "middle (overs 7-15)", "sequence": seq,
            "analysis_format": "IPL", "match_state_pressure_eligible": True,
            "legal_balls_remaining": 60, "runs_required": 120, "score_before": score,
            "legal_balls_bowled_before": balls_bowled, "ordinary_delivery": True,
            "batter_runs_verified_subset": runs, "dot_ball_verified_subset": runs == 0,
            "boundary_event": runs == 4, "striker_id": 10, "striker_name": "Batter A",
            "bowler_id": 20, "bowler_name": "Bowler X", "bowler_wicket_event": False,
            "extras_type": pd.NA, "legal_delivery": True,
        })
    return pd.DataFrame(rows)


def test_pressure_baseline_cohorts_pair_by_match_and_phase_and_aggregate_missingness():
    f = build_primary_cohorts(_fixture())
    assert f.cohort.tolist() == ["pressure", "pressure", "normal_baseline"]
    bat, bowl, exposure = build_profiles(_fixture())
    p = bat.loc[bat.cohort.eq("pressure")].iloc[0]
    assert p.ordinary_subset_balls == 2
    assert p.ordinary_subset_scoring_rows == 1
    assert p.batter_runs_ordinary_subset == 4
    assert p.ordinary_subset_strike_rate == 400
    assert p.batter_runs_missing_ordinary_rows == 1
    assert p.boundary_events_full_eligible_scope == 1
    assert not exposure.sufficient_evidence_for_future_pressure_comparison.any()
    assert bowl.loc[bowl.cohort.eq("pressure"), "observed_deliveries"].iloc[0] == 2


def test_small_samples_keep_point_estimates_but_do_not_claim_rate_intervals():
    one = _fixture().iloc[[0]].copy()
    # Cannot form a within-match comparison with a single state row.
    bat, bowl, exposure = build_profiles(one)
    assert bat.empty and bowl.empty and exposure.empty


def test_format_crosswalk_keeps_ipl_and_t20i_separate_and_excludes_other_t20():
    features = pd.DataFrame({"match_id": [1, 2, 3]})
    matches = pd.DataFrame({"match_id": [1, 2, 3], "comp_id": [10, 20, 30]})
    competitions = pd.DataFrame({
        "comp_id": [10, 20, 30], "match_format": ["T20", "T20I", "T20"],
        "comp_name": ["IPL 2024", "India T20I Series", "Other T20 Cup"], "season": [2024, 2024, 2024],
    })
    result = add_format(features, matches, competitions)
    assert result.analysis_format.iloc[0] == "IPL"
    assert result.analysis_format.iloc[1] == "T20I"
    assert pd.isna(result.analysis_format.iloc[2])
