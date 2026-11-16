"""Synthetic-only tests for Phase 2B validation and state reconstruction."""
import pandas as pd
import pytest

from src.cricket_data_validation import analyze_extras, normalize_delivery_events
from src.match_state import reconstruct_match_states


def test_extras_code_pattern_is_not_misread_as_runs():
    fixture = pd.DataFrame({
        "runs": [0, 0, 0], "extras_type": [None, "wide", "Overstep"],
        "extras1_runs": [6, 2, 1], "extras_2_runs": [0, 0, 0], "is_wicket": [False] * 3,
    })
    table = analyze_extras(fixture).set_index("extras_type")
    assert table.loc["(null)", "extras1_runs_values"] == "6"
    assert "not a run amount" in table.loc["wide", "interpretation"]
    assert "not a run amount" in table.loc["Overstep", "interpretation"]


def test_normalizer_keeps_extras_score_unknown_and_classifies_wide():
    fixture = pd.DataFrame({
        "runs": [2, 0, 1], "extras_type": [None, "wide", "Overstep"],
        "extras1_runs": [6, 2, 1], "extras_2_runs": [0, 0, 0], "is_wicket": [False] * 3,
    })
    normalized = normalize_delivery_events(fixture)
    assert normalized.loc[0, "team_runs_delta"] == 2
    assert pd.isna(normalized.loc[1, "team_runs_delta"])
    assert normalized.loc[1, "legal_delivery"] == False
    assert normalized.loc[2, "legal_delivery"] == False


def test_secondary_extra_amount_is_not_added_without_semantics():
    fixture = pd.DataFrame({
        "runs": [1, 0], "extras_type": [None, "Overstep"],
        "extras1_runs": [6, 1], "extras_2_runs": [1, 4], "is_wicket": [False, False],
    })
    normalized = normalize_delivery_events(fixture)
    assert pd.isna(normalized.loc[0, "team_runs_delta"])
    assert pd.isna(normalized.loc[1, "team_runs_delta"])
    assert pd.isna(normalized.loc[0, "legal_delivery"])
    assert normalized.loc[1, "legal_delivery"] == False


def test_other_extra_legal_status_is_not_guessed():
    fixture = pd.DataFrame({
        "runs": [0], "extras_type": ["other"], "extras1_runs": [5],
        "extras_2_runs": [4], "is_wicket": [False],
    })
    normalized = normalize_delivery_events(fixture)
    assert pd.isna(normalized.loc[0, "team_runs_delta"])
    assert pd.isna(normalized.loc[0, "legal_delivery"])


def test_state_values_before_delivery_and_chase_target():
    fixture = pd.DataFrame({
        "match_id": [1] * 4, "innings": [1, 1, 2, 2], "sequence": [1, 2, 1, 2],
        "team_runs_delta": [1, 2, 1, 3], "legal_delivery": [True] * 4,
        "wicket_event": [False, True, False, False],
    })
    result = reconstruct_match_states(fixture)
    first = result[(result.innings == 1)].reset_index(drop=True)
    chase = result[(result.innings == 2)].reset_index(drop=True)
    assert first.loc[0, "score_before"] == 0
    assert first.loc[1, "score_before"] == 1
    assert first.loc[1, "wickets_lost_before"] == 0
    assert chase.loc[0, "target"] == 4
    assert chase.loc[0, "runs_required"] == 4
    assert chase.loc[1, "score_before"] == 1
    assert chase.loc[1, "runs_required"] == 3


def test_unknown_score_propagates_without_corrupting_wicket_state():
    fixture = pd.DataFrame({
        "match_id": [2] * 3, "innings": [1] * 3, "sequence": [1, 2, 3],
        "team_runs_delta": [4, pd.NA, 1], "legal_delivery": [True] * 3,
        "wicket_event": [False, True, False],
    })
    result = reconstruct_match_states(fixture)
    assert bool(result.loc[0, "score_known"])
    assert result.loc[1, "score_before"] == 4
    assert not bool(result.loc[2, "score_known"])
    assert pd.isna(result.loc[2, "score_before"])
    assert result.loc[2, "wickets_lost_before"] == 1


def test_revised_target_and_overs_are_used():
    fixture = pd.DataFrame({
        "match_id": [3] * 3, "innings": [1, 2, 2], "sequence": [1, 1, 2],
        "team_runs_delta": [7, 2, 1], "legal_delivery": [True] * 3,
        "wicket_event": [False] * 3,
    })
    result = reconstruct_match_states(fixture, {"revised_target": 10, "second_inn_revised_overs": 5})
    chase = result[result.innings == 2].reset_index(drop=True)
    assert chase.loc[0, "target"] == 10
    assert chase.loc[0, "legal_balls_remaining"] == 30
    assert chase.loc[0, "required_run_rate"] == 2.0


def test_revised_overs_column_pattern_is_converted_to_ball_limit():
    fixture = pd.DataFrame({
        "match_id": [30], "innings": [2], "sequence": [1],
        "team_runs_delta": [0], "legal_delivery": [True], "wicket_event": [False],
    })
    result = reconstruct_match_states(fixture, {"second_inn_revised_overs": 114})
    assert result.loc[0, "innings_balls_limit"] == 114
    assert result.loc[0, "legal_balls_remaining"] == 114


def test_match_state_totals_do_not_leak_between_matches():
    fixture = pd.DataFrame({
        "match_id": [10, 10, 11, 11], "innings": [1, 2, 1, 2], "sequence": [1, 1, 1, 1],
        "team_runs_delta": [30, 2, 5, 1], "legal_delivery": [True] * 4,
        "wicket_event": [False] * 4,
    })
    result = reconstruct_match_states(fixture)
    assert result.loc[(result.match_id == 10) & (result.innings == 2), "target"].iloc[0] == 31
    assert result.loc[(result.match_id == 11) & (result.innings == 2), "target"].iloc[0] == 6


def test_super_over_has_one_over_and_two_wicket_limit():
    fixture = pd.DataFrame({
        "match_id": [4] * 5, "innings": [3, 3, 4, 4, 4], "sequence": [1, 2, 1, 2, 3],
        "team_runs_delta": [2, 1, 0, 0, 0], "legal_delivery": [True] * 5,
        "wicket_event": [False, False, False, True, True],
    })
    result = reconstruct_match_states(fixture)
    super_first = result[result.innings == 3].reset_index(drop=True)
    super_second = result[result.innings == 4].reset_index(drop=True)
    assert super_first.loc[0, "legal_balls_remaining"] == 6
    assert super_first.loc[1, "legal_balls_remaining"] == 5
    assert super_second.loc[0, "target"] == 4
    assert super_second.loc[2, "wickets_lost_before"] == 1
    assert super_second.loc[0, "innings_overs_limit"] == 1


def test_duplicate_delivery_sequence_is_rejected():
    fixture = pd.DataFrame({
        "match_id": [5, 5], "innings": [1, 1], "sequence": [1, 1],
        "team_runs_delta": [0, 1], "legal_delivery": [True, True], "wicket_event": [False, False],
    })
    # The pipeline guards this at ingest; the engine's merge contract rejects ambiguity.
    with pytest.raises(pd.errors.MergeError):
        reconstruct_match_states(fixture)
