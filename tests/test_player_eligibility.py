"""Tests for role-separated player exposure and evidence gates."""
import pandas as pd

from src.player_eligibility import build_player_eligibility


def _features():
    rows = []
    seq = 0
    # Player 1 has ordinary baseline plus verified pressure in two matches.
    for match_id, pressure, count in [(1, False, 4), (2, True, 2), (3, True, 2)]:
        for _ in range(count):
            seq += 1
            rows.append({"match_id": match_id, "innings": 2, "sequence": seq, "striker_id": 1,
                "striker_name": "Batter A", "bowler_id": 11, "bowler_name": "Bowler A", "runs": 4,
                "is_four": True, "is_six": False, "is_wicket": False, "dismissed_player_id": pd.NA,
                "batter_dismissal_event": False, "bowler_wicket_event": False, "legal_delivery": True,
                "ordinary_delivery": True, "batter_runs_verified_subset": 4, "balls_faced_verified_subset": 1,
                "dot_ball_verified_subset": False, "match_state_pressure_eligible": pressure,
                "wicket_phase_proxy_eligible": True})
    # Add a recognized bowler wicket to the second participant's bowling sample.
    rows.append({"match_id": 1, "innings": 1, "sequence": 99, "striker_id": 2,
        "striker_name": "Batter B", "bowler_id": 12, "bowler_name": "Bowler B", "runs": 0,
        "is_four": False, "is_six": False, "is_wicket": True, "dismissed_player_id": 2,
        "batter_dismissal_event": True, "bowler_wicket_event": True, "legal_delivery": True,
        "ordinary_delivery": True, "batter_runs_verified_subset": 0, "balls_faced_verified_subset": 1,
        "dot_ball_verified_subset": True, "match_state_pressure_eligible": False,
        "wicket_phase_proxy_eligible": True})
    return pd.DataFrame(rows)


def test_batter_and_bowler_tables_separate_role_exposure_and_pressure_matches():
    batters, bowlers, scoring, thresholds = build_player_eligibility(_features())
    batter = batters.set_index("player_id").loc[1]
    bowler = bowlers.set_index("player_id").loc[11]
    assert batter["deliveries_observed"] == 8
    assert batter["verified_pressure_deliveries"] == 4
    assert batter["verified_pressure_matches"] == 2
    assert bool(batter["verified_pressure_evidence_eligible"])
    assert bowler["deliveries_observed"] == 8
    assert bowler["verified_pressure_deliveries"] == 4
    assert thresholds["batter"]["pressure_matches_min"] == 2
    assert "Bowler-conceded runs / economy" in set(scoring["metric"])


def test_partial_batter_pressure_rates_do_not_claim_normal_baseline_retention():
    batters, _, scoring, _ = build_player_eligibility(_features())
    batter = batters.set_index("player_id").loc[1]
    assert batter["pressure_ordinary_boundary_rate"] == 1.0
    assert batter["pressure_retention_status"] == "not calculated; baseline cannot be classified as normal"
    row = scoring[scoring["metric"].eq("Boundary-rate retention (ordinary subset)")].iloc[0]
    assert row["feasibility"] == "Candidate formula; blocked"


def test_dismissal_only_player_does_not_get_invented_delivery_exposure():
    features = _features()
    # Make dismissed batter ID absent from all striker rows.
    features.loc[features["dismissed_player_id"].notna(), "dismissed_player_id"] = 999
    batters, _, _, _ = build_player_eligibility(features)
    dismissed_only = batters.set_index("player_id").loc[999]
    assert dismissed_only["deliveries_observed"] == 0
    assert dismissed_only["batter_dismissals"] == 1
    assert not bool(dismissed_only["baseline_evidence_eligible"])
