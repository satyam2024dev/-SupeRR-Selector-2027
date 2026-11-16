import pandas as pd

from src.metric_evidence import build_player_coverage, metric_eligibility


def sample_features():
    return pd.DataFrame([
        {"match_id": 1, "innings": 1, "striker_id": 10, "striker_name": "A Batter", "bowler_id": 20,
         "bowler_name": "A Bowler", "ordinary_delivery": True, "batter_runs_verified_subset": 0,
         "balls_faced_verified_subset": 1, "four_event": False, "six_event": False, "boundary_event": False,
         "dot_ball_verified_subset": True, "is_wicket": False, "bowler_wicket_event": False,
         "extras_type": None, "legal_delivery": True},
        {"match_id": 1, "innings": 1, "striker_id": 10, "striker_name": "A Batter", "bowler_id": 20,
         "bowler_name": "A Bowler", "ordinary_delivery": True, "batter_runs_verified_subset": 4,
         "balls_faced_verified_subset": 1, "four_event": True, "six_event": False, "boundary_event": True,
         "dot_ball_verified_subset": False, "is_wicket": True, "bowler_wicket_event": True,
         "extras_type": None, "legal_delivery": True},
        {"match_id": 1, "innings": 1, "striker_id": 11, "striker_name": "B Batter", "bowler_id": 20,
         "bowler_name": "A Bowler", "ordinary_delivery": False, "batter_runs_verified_subset": None,
         "balls_faced_verified_subset": 0, "four_event": False, "six_event": False, "boundary_event": False,
         "dot_ball_verified_subset": False, "is_wicket": False, "bowler_wicket_event": False,
         "extras_type": "wide", "legal_delivery": False},
        {"match_id": 1, "innings": 1, "striker_id": 11, "striker_name": "B Batter", "bowler_id": 20,
         "bowler_name": "A Bowler", "ordinary_delivery": False, "batter_runs_verified_subset": None,
         "balls_faced_verified_subset": 0, "four_event": False, "six_event": False, "boundary_event": False,
         "dot_ball_verified_subset": False, "is_wicket": False, "bowler_wicket_event": False,
         "extras_type": "byes", "legal_delivery": True},
    ])


def test_metric_matrix_keeps_full_metrics_blocked_and_scopes_subsets():
    matrix = metric_eligibility(sample_features()).set_index("metric")
    assert matrix.loc["Batter runs", "eligibility_status"] == "eligible_limited_subset"
    assert matrix.loc["Boundaries", "eligibility_status"] == "eligible_full_event_count"
    assert matrix.loc["Bowler-conceded runs", "eligibility_status"] == "blocked"
    assert matrix.loc["Economy rate", "eligibility_status"] == "blocked"
    assert matrix.loc["Bowling strike rate", "eligibility_status"] == "blocked"
    assert matrix.loc["Legal balls bowled", "metric_event_count"] == 3
    assert matrix.loc["Team wickets lost", "player_level_comparison"] == "match/innings only; not player-level"


def test_eligible_player_coverage_calculates_only_supported_scopes():
    coverage = build_player_coverage(sample_features())
    assert coverage.eligibility_status.str.startswith("eligible_").all()
    batter = coverage[(coverage.player_id == 10) & (coverage.metric == "Strike rate (ordinary subset)")].iloc[0]
    assert batter.metric_value == 200
    assert batter.metric_sample_events == 2
    assert "ordinary" in batter.scope
    bowler_legal = coverage[(coverage.player_id == 20) & (coverage.metric == "Legal balls bowled (known-category subset)")].iloc[0]
    assert bowler_legal.metric_value == 3
    bowler_wickets = coverage[(coverage.player_id == 20) & (coverage.metric == "Bowler-credit wickets (recognized types)")].iloc[0]
    assert bowler_wickets.metric_value == 1
    assert not coverage.metric.str.contains("economy|conceded runs|bowling strike rate", case=False).any()
