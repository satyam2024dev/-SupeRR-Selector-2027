import pandas as pd

from src.phase5b_rating_methodology import _paired, _metric_rows, METHODS


def test_three_pressure_methods_are_explicit_and_distinct():
    assert METHODS == ("verified_chase", "wicket_phase_proxy", "combined_verified_and_proxy")


def test_pairing_requires_pressure_and_reference_inside_same_match_phase():
    frame = pd.DataFrame({
        "match_id": [1, 1, 1, 2],
        "innings_phase": ["middle", "middle", "death", "middle"],
        "ordinary_delivery": [True] * 4,
    })
    high = pd.Series([True, False, True, True], index=frame.index)
    low = pd.Series([False, True, False, False], index=frame.index)
    result = _paired(frame, high, low)
    assert result.match_id.tolist() == [1, 1]
    assert result.cohort.tolist() == ["pressure", "baseline"]


def test_bowler_metric_uses_recognized_wickets_per_event_and_blocks_conventional_rates():
    frame = pd.DataFrame({"bowler_wicket_event": [True, False, False]})
    metrics = _metric_rows(frame, "bowler")
    assert metrics["recognized_wickets"] == 1
    assert metrics["recognized_wickets_per_observed_event"] == 1 / 3
    assert metrics["bowler_conceded_runs"] is None
    assert metrics["economy_rate"] is None
    assert metrics["bowling_strike_rate"] is None


def test_batter_metrics_do_not_impute_missing_runs():
    frame = pd.DataFrame({
        "ordinary_delivery": [True, True, False],
        "batter_runs_verified_subset": [4, None, None],
        "dot_ball_verified_subset": [False, False, False],
        "boundary_event": [True, False, False],
    })
    metrics = _metric_rows(frame, "batter")
    assert metrics["metric_events"] == 2
    assert metrics["known_run_events"] == 1
    assert metrics["missing_run_events"] == 1
    assert metrics["ordinary_subset_sr"] == 400
