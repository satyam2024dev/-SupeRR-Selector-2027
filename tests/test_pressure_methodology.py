import pandas as pd

from src.pressure_methodology import build_state_cohorts


def test_state_cohort_pressure_baseline_and_exact_context_matching():
    features = pd.DataFrame([
        # Same match, phase and wicket count: two high-demand and two baseline states.
        {"match_id": 1, "innings": 2, "overid": 2, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 1,
         "match_state_pressure_eligible": True, "runs_required": 100, "legal_balls_remaining": 60, "score_before": 10, "legal_balls_bowled_before": 30},
        {"match_id": 1, "innings": 2, "overid": 2, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 1,
         "match_state_pressure_eligible": True, "runs_required": 40, "legal_balls_remaining": 60, "score_before": 40, "legal_balls_bowled_before": 30},
        {"match_id": 1, "innings": 2, "overid": 2, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 1,
         "match_state_pressure_eligible": True, "runs_required": 120, "legal_balls_remaining": 60, "score_before": 20, "legal_balls_bowled_before": 30},
        {"match_id": 1, "innings": 2, "overid": 2, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 1,
         "match_state_pressure_eligible": True, "runs_required": 60, "legal_balls_remaining": 60, "score_before": 30, "legal_balls_bowled_before": 30},
        # First delivery: current rate undefined, excluded from high/low contrast.
        {"match_id": 1, "innings": 2, "overid": 1, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 0,
         "match_state_pressure_eligible": True, "runs_required": 100, "legal_balls_remaining": 120, "score_before": 0, "legal_balls_bowled_before": 0},
        # Super Over row is excluded from regular chase design.
        {"match_id": 2, "innings": 4, "overid": 1, "innings_phase": "super over (separate)", "wickets_lost_before": 0,
         "match_state_pressure_eligible": True, "runs_required": 4, "legal_balls_remaining": 2, "score_before": 0, "legal_balls_bowled_before": 1},
    ])
    matches = pd.DataFrame({"match_id": [1, 2], "comp_id": [10, 20]})
    competitions = pd.DataFrame({"comp_id": [10, 20], "match_format": ["T20I", "T20"], "season": [2024, 2025]})

    known, matched, summary = build_state_cohorts(features, matches, competitions)

    assert len(known) == 4
    assert int(known.pressure_state.sum()) == 2
    assert int((~known.pressure_state).sum()) == 2  # Equality is comparison/baseline.
    assert len(matched) == 4
    assert summary["regular_chase_state_rows"] == 5
    assert summary["unknown_current_rate_rows"] == 1
    assert summary["paired_matches"] == 1


def test_state_stratum_without_both_classes_is_not_used_as_baseline():
    features = pd.DataFrame([
        {"match_id": 1, "innings": 2, "overid": 2, "innings_phase": "powerplay (overs 1-6)", "wickets_lost_before": 0,
         "match_state_pressure_eligible": True, "runs_required": 90, "legal_balls_remaining": 60, "score_before": 5, "legal_balls_bowled_before": 30},
        {"match_id": 2, "innings": 2, "overid": 7, "innings_phase": "middle (overs 7-15)", "wickets_lost_before": 0,
         "match_state_pressure_eligible": True, "runs_required": 40, "legal_balls_remaining": 60, "score_before": 35, "legal_balls_bowled_before": 30},
    ])
    matches = pd.DataFrame({"match_id": [1, 2], "comp_id": [10, 10]})
    competitions = pd.DataFrame({"comp_id": [10], "match_format": ["T20I"], "season": [2024]})

    known, matched, _ = build_state_cohorts(features, matches, competitions)

    assert len(known) == 2
    assert matched.empty
