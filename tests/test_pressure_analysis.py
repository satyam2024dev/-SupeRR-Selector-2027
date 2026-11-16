"""Synthetic regression coverage for pressure-feasibility features."""
import pandas as pd

from src.pressure_analysis import build_pressure_features, coverage_table, feasibility_matrix


def _fixture():
    ball = pd.DataFrame({
        "match_id": [1, 1, 1, 1], "innings": [1, 2, 2, 4], "innings_ball_num": [1, 1, 2, 1],
        "striker_id": [10, 20, 20, 30], "bowler_id": [40, 41, 41, 42],
        "striker_name": ["A", "B", "B", "C"], "bowler_name": ["X", "Y", "Y", "Z"],
        "runs": [0, 4, 0, 1], "extras_type": [None, None, "wide", None], "extras_2_runs": [0, 0, 0, 0],
        "is_four": [False, True, False, False], "is_six": [False] * 4,
        "is_wicket": [False, False, True, False], "dismissed_player_id": [None, None, 20, None],
        "dismissal_type": [None, None, "Caught", None], "overid": [1, 18, 18, 1],
        "pace_or_spin": ["Pace"] * 4, "bowling_type": ["Fast"] * 4,
    })
    states = pd.DataFrame({
        "match_id": [1] * 4, "innings": [1, 2, 2, 4], "sequence": [1, 1, 2, 1],
        "score_before": [0, 0, 4, 0], "score_known": [True, True, True, True],
        "target": [pd.NA, 10, 10, 5], "runs_required": [pd.NA, 10, 6, 5],
        "legal_balls_remaining": [120, 120, 120, 6], "legal_balls_known": [True] * 4,
        "wickets_lost_before": [0, 0, 0, 0], "legal_balls_bowled_before": [0] * 4,
        "legal_delivery": [True, True, False, True],
    })
    return ball, states


def test_pressure_features_keep_proxies_separate_and_super_over_phase_separate():
    ball, states = _fixture()
    result = build_pressure_features(ball, states)
    assert result["match_state_pressure_eligible"].tolist() == [False, True, True, True]
    assert result["innings_phase"].tolist() == ["powerplay (overs 1-6)", "death (overs 16-20)",
                                                "death (overs 16-20)", "super over (separate)"]
    assert result.loc[3, "wickets_remaining"] == 2
    assert result["bowler_wicket_event"].sum() == 1
    assert result["batter_dismissal_event"].sum() == 1


def test_verified_batting_subset_excludes_extra_events():
    ball, states = _fixture()
    result = build_pressure_features(ball, states)
    assert result["ordinary_delivery"].tolist() == [True, True, False, True]
    assert result["batter_runs_verified_subset"].tolist()[:2] == [0, 4]
    assert pd.isna(result.loc[2, "batter_runs_verified_subset"])
    assert result["balls_faced_verified_subset"].tolist() == [1, 1, 0, 1]


def test_feasibility_blocks_bowler_economy_and_coverage_counts_rows():
    ball, states = _fixture()
    result = build_pressure_features(ball, states)
    matrix = feasibility_matrix(result).set_index("metric")
    assert matrix.loc["Bowler economy", "reliability"] == "Not reliable"
    coverage = coverage_table(result).set_index("definition")
    assert coverage.loc["Match-state pressure (verified chase state)", "delivery_rows_covered"] == 3
    assert coverage.loc["Boundary events", "delivery_rows_covered"] == 1
