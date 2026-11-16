import pandas as pd

from src.provider_field_investigation import state_coverage_opportunities, unresolved_run_event_audit


def test_unresolved_runs_are_counted_as_semantic_gaps_not_null_cells():
    ball = pd.DataFrame({
        "match_id": [1, 1, 1, 1], "runs": [0, 0, 0, 1],
        "extras_type": [pd.NA, "wide", pd.NA, "other"],
        "extras1_runs": [6, 2, 6, 5], "extras_2_runs": [0, 0, 1, 4],
        "is_wicket": [False] * 4,
    })
    summary, by_type = unresolved_run_event_audit(ball)
    values = summary.set_index("measure").value
    assert values["unknown_team_run_delta_events"] == 3
    assert values["unknown_events_with_extras_type"] == 2
    assert values["unknown_events_null_extras_type_nonzero_extras2"] == 1
    assert values["unknown_events_missing_runs"] == 0
    assert values["unknown_events_nonzero_extras2"] == 2
    assert by_type.unresolved_events.sum() == 3


def test_state_coverage_scenarios_preserve_pressure_classes_as_unknown():
    frame = pd.DataFrame({
        "analysis_format": ["IPL"] * 4, "innings": [2] * 4,
        "match_state_pressure_eligible": [True, False, False, False],
        "score_known": [True, False, True, True], "target": [100, 100, pd.NA, 100],
        "legal_balls_known": [True, True, True, False],
        "legal_balls_remaining": [60, 60, 60, pd.NA],
        "legal_balls_bowled_before": [10, 10, 10, 10],
        "score_before": [10, pd.NA, 20, 20], "runs_required": [90, pd.NA, pd.NA, 80],
        "innings_balls_limit": [120] * 4, "match_id": [1, 1, 1, 1],
        "current_run_rate": [6, pd.NA, 12, 12], "required_run_rate": [9, pd.NA, pd.NA, pd.NA],
    })
    result = state_coverage_opportunities(frame).query("format == 'IPL'").set_index("scenario")
    assert result.loc["current_verified_state", "state_rows_current_or_conditionally_reconstructable"] == 1
    assert result.loc["total_runs_defined_only", "state_rows_current_or_conditionally_reconstructable"] == 2
    assert result.loc["targets_defined_only", "state_rows_current_or_conditionally_reconstructable"] == 2
    assert result.loc["legal_delivery_defined_only", "state_rows_current_or_conditionally_reconstructable"] == 2
    assert result.loc["all_state_inputs_defined_ceiling", "state_rows_current_or_conditionally_reconstructable"] == 4
    assert result.loc["all_state_inputs_defined_ceiling", "new_pressure_rows"] == "not classifiable before actual values are supplied"
