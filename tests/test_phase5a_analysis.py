import pandas as pd

from src.phase5a_analysis import build_states, build_primary_pair, bat_metrics, build_proxy


def _state_rows():
    rows = []
    # At delivery 2 and 3, rate is known; one is behind, one at/ahead.
    # Wickets differ to verify the primary pairing does not silently exact-match wickets.
    for match, seq, runs_required, score, balls, wickets, innings, phase, eligible in [
        (1, 1, 100, 0, 0, 0, 2, "powerplay", True),  # CRR undefined
        (1, 2, 100, 5, 6, 0, 2, "middle", True),     # RRR > CRR
        (1, 3, 60, 60, 60, 3, 2, "middle", True),    # RRR <= CRR, different wicket state
        (2, 4, 50, 10, 12, 2, 2, "middle", False),   # unknown state flag
        (3, 5, 10, 0, 6, 0, 4, "super over", True),  # excluded
    ]:
        rows.append({
            "match_id": match, "innings": innings, "sequence": seq, "analysis_format": "T20I",
            "innings_phase": phase, "match_state_pressure_eligible": eligible,
            "score_before": score, "runs_required": runs_required,
            "legal_balls_remaining": 60, "legal_balls_bowled_before": balls,
            "wickets_lost_before": wickets, "wickets_remaining": 10-wickets,
        })
    return pd.DataFrame(rows)


def test_primary_pressure_uses_known_regular_chase_rrr_greater_than_crr_only():
    states = build_states(_state_rows())
    assert states.sequence.tolist() == [2, 3]
    assert states.pressure_class.tolist() == ["pressure", "normal_baseline"]


def test_primary_pair_matches_within_match_phase_and_keeps_wicket_difference_visible():
    source = _state_rows()
    # Keep one phase for the two known comparison observations.
    pair = build_primary_pair(source)
    assert pair.sequence.tolist() == [2, 3]
    assert pair.cohort.tolist() == ["pressure", "normal_baseline"]
    assert pair.wickets_lost_before.tolist() == [0, 3]


def test_batting_metrics_use_ordinary_events_and_do_not_impute_missing_runs():
    rows = pd.DataFrame({
        "ordinary_delivery": [True, True, True, False],
        "batter_runs_verified_subset": [4, 0, None, None],
        "dot_ball_verified_subset": [False, True, False, False],
        "boundary_event": [True, False, False, False],
    })
    result = bat_metrics(rows)
    assert result["ordinary_events"] == 3
    assert result["known_runs_events"] == 2
    assert result["missing_runs_events"] == 1
    assert result["ordinary_runs"] == 4
    assert result["ordinary_subset_strike_rate"] == 200
    assert result["ordinary_dot_rate"] == 0.5
    assert result["ordinary_boundary_rate"] == 1/3


def test_wicket_phase_proxy_excludes_super_over_and_labels_as_exploratory():
    rows = []
    for i, wicket in enumerate([0, 0, 1, 2, 3, 4]):
        rows.append({"match_id": i, "analysis_format": "IPL", "innings_phase": "middle",
                     "wickets_lost_before": wicket, "wicket_phase_proxy_eligible": True})
    rows.append({"match_id": 99, "analysis_format": "IPL", "innings_phase": "super over",
                 "wickets_lost_before": 2, "wicket_phase_proxy_eligible": True})
    proxy, thresholds = build_proxy(pd.DataFrame(rows))
    assert len(proxy) == 6
    assert "high_wicket_loss_proxy" in set(proxy.proxy_class)
    assert thresholds.interpretation.str.contains("not verified").all()

