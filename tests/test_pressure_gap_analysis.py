import pandas as pd

from src.pressure_gap_analysis import cricsheet_chase_states, paired_state_rows


def test_paired_state_rows_excludes_unknown_current_rate_and_keeps_pressure_baseline_pair():
    frame = pd.DataFrame({
        "analysis_format": ["IPL", "IPL", "IPL", "IPL"],
        "match_state_pressure_eligible": [True, True, True, True],
        "innings": [2, 2, 2, 2], "match_id": [1, 1, 1, 2],
        "innings_phase": ["middle"] * 4,
        "score_before": [0, 100, 0, 0], "legal_balls_bowled_before": [0, 50, 10, 10],
        "runs_required": [100, 20, 100, 100], "legal_balls_remaining": [60, 10, 60, 60],
    })
    paired = paired_state_rows(frame)
    assert len(paired) == 2
    assert set(paired.pressure_class) == {"pressure", "baseline"}
    assert paired.match_id.nunique() == 1


def test_cricsheet_candidate_replay_uses_pre_delivery_state_and_pairs_by_phase():
    payload = {
        "info": {"overs": 2},
        "innings": [
            {"team": "A", "overs": [{"over": 0, "deliveries": [{"runs": {"batter": 5, "extras": 0, "total": 5}}]}]},
            {"team": "B", "target": {"runs": 6, "overs": 2}, "overs": [{"over": 0, "deliveries": [
                {"runs": {"batter": 0, "extras": 0, "total": 0}},
                {"runs": {"batter": 6, "extras": 0, "total": 6}},
                {"runs": {"batter": 0, "extras": 0, "total": 0}},
            ]}]},
        ],
    }
    states = cricsheet_chase_states(payload)
    assert len(states) == 2  # first delivery has no completed-ball CRR
    assert states.score_before.tolist() == [0, 6]
    assert states.pressure_class.tolist() == ["pressure", "baseline"]
    assert states.phase_paired.all()


def test_candidate_replay_does_not_reconstruct_without_target_or_first_innings():
    assert cricsheet_chase_states({"info": {"overs": 20}, "innings": []}).empty
