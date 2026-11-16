import pandas as pd

from src.phase4e_data_recovery import pilot_recovery_rows, unresolved_event_groups


def _scope_frames():
    competitions = pd.DataFrame([
        {"comp_id": 1, "comp_name": "IPL 2022", "match_format": "T20", "season": "2022"},
        {"comp_id": 2, "comp_name": "Ireland T20I 2022", "match_format": "T20I", "season": "2022"},
        {"comp_id": 3, "comp_name": "Domestic Cup 2022", "match_format": "T20", "season": "2022"},
    ])
    matches = pd.DataFrame([
        {"match_id": 10, "comp_id": 1, "match_date": "2022-04-01"},
        {"match_id": 20, "comp_id": 2, "match_date": "2022-06-01"},
        {"match_id": 30, "comp_id": 3, "match_date": "2022-06-01"},
    ])
    deliveries = pd.DataFrame([
        {"match_id": 10, "innings": 1, "overid": 1, "over_ball_num": 1, "innings_ball_num": 1,
         "runs": 0, "extras_type": "wide", "extras1_runs": 2, "extras_2_runs": 0, "is_wicket": False,
         "striker_id": 1, "bowler_id": 2},
        {"match_id": 10, "innings": 1, "overid": 1, "over_ball_num": 2, "innings_ball_num": 2,
         "runs": 1, "extras_type": None, "extras1_runs": 6, "extras_2_runs": 0, "is_wicket": False,
         "striker_id": 1, "bowler_id": 2},
        {"match_id": 20, "innings": 2, "overid": 1, "over_ball_num": 1, "innings_ball_num": 1,
         "runs": 0, "extras_type": "byes", "extras1_runs": 4, "extras_2_runs": 0, "is_wicket": False,
         "striker_id": 3, "bowler_id": 4},
        {"match_id": 30, "innings": 1, "overid": 1, "over_ball_num": 1, "innings_ball_num": 1,
         "runs": 2, "extras_type": "wide", "extras1_runs": 2, "extras_2_runs": 0, "is_wicket": False,
         "striker_id": 5, "bowler_id": 6},
    ])
    return deliveries, matches, competitions


def test_unresolved_groups_respect_official_scope_and_delivery_grain():
    deliveries, matches, competitions = _scope_frames()
    grouped = unresolved_event_groups(deliveries, matches, competitions)

    assert grouped.event_count.sum() == 2
    assert set(grouped.analysis_format) == {"IPL", "T20I"}
    assert set(grouped.match_id) == {10, 20}
    assert set(grouped.extras_type_group) == {"wide", "byes"}
    assert grouped.available_source_fields.str.contains("extras_2_runs").all()
    assert grouped.queue_row_type.eq("unresolved_event_group").all()


def test_pilot_rows_remain_unresolved_and_keep_exact_gate_blockers():
    acceptance = pd.DataFrame([{
        "official_match_id": 10, "competition": "IPL 2022", "format": "T20",
        "season": 2022, "match_date": "2022-04-01", "home_team": "A", "away_team": "B",
        "pilot_role": "control", "external_file_status": "downloaded",
        "external_match_id": "external-1", "external_filename": "one.json", "source_url": "url",
        "source_sha256": "hash", "acceptance_status": "unresolved",
        "blocking_checks": "player_identity;delivery_totals",
    }])
    reconciliation = pd.DataFrame([{
        "official_match_id": 10, "match_reconciliation_status": "partial-match",
        "delivery_exact_count": 0, "delivery_partial_count": 1,
        "delivery_mismatch_count": 0, "delivery_unresolved_count": 0,
        "player_identity_status": "unresolved", "venue_identity_status": "verified",
        "total_runs_status": "unavailable", "legal_balls_status": "exact",
        "innings_totals_status": "unresolved", "target_status": "unresolved",
        "bowling_figures_status": "unresolved", "result_status": "exact",
    }])
    queue = pilot_recovery_rows(acceptance, reconciliation)

    row = queue.loc[queue.queue_row_type.eq("pilot_match")].iloc[0]
    assert row.acceptance_status == "unresolved"
    assert row.blocking_checks == "player_identity;delivery_totals"
    assert row.conditional_coverage_gain.startswith("not counted")
    assert row.action_priority.startswith("P1")

