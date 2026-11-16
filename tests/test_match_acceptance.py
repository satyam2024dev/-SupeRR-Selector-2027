from src.match_acceptance import MANDATORY_GATES, assess_match, decide_match


def passing_gates():
    return {name: "pass" for name in MANDATORY_GATES}


def baseline_match(**overrides):
    row = {
        "official_match_id": "999", "external_file_status": "downloaded", "external_filename": "",
        "external_source_url": "https://example.test/match.zip", "match_identity_status": "exact",
        "external_date_match": "True", "external_teams_match": "True", "external_format_match": "True",
        "external_competition_family_match": "True", "delivery_sequence_status": "exact",
        "aligned_deliveries": "1", "external_delivery_rows": "1", "official_local_delivery_rows": "1",
        "batter_runs_status": "exact", "legal_balls_status": "exact", "wickets_status": "exact",
        "result_status": "exact", "player_identity_status": "verified_namespace",
    }
    row.update(overrides)
    return row


def test_complete_mandatory_gate_set_is_accepted():
    assert decide_match(passing_gates()) == (
        "accepted", "all mandatory Phase 2E checks passed with zero unexplained differences"
    )


def test_confirmed_scoring_failure_rejects_match():
    gates = passing_gates()
    gates["typed_extras"] = "fail"
    status, reason = decide_match(gates)
    assert status == "rejected"
    assert "typed_extras" in reason


def test_incomplete_player_mapping_cannot_pass_identity_gate():
    score = [{"match_id": "999", "batter_runs_status": "exact", "legal_delivery_external_candidate": "True"}]
    result = assess_match(baseline_match(), [{"status": "candidate"}], {"status": "verified"}, score, {})
    assert result["player_mapping_candidate_count"] == 1
    assert result["gate_player_identity"] == "unresolved"
    assert result["acceptance_status"] == "unresolved"


def test_missing_scorecard_leaves_innings_total_gate_unresolved():
    score = [{"match_id": "999", "batter_runs_status": "exact", "legal_delivery_external_candidate": "True"}]
    result = assess_match(baseline_match(), [{"status": "verified"}], {"status": "verified"}, score, {})
    assert result["gate_innings_totals"] == "unresolved"
    assert result["acceptance_status"] == "unresolved"


def test_missing_local_scoring_fields_do_not_pass_total_or_extras_gates():
    score = [{"match_id": "999", "batter_runs_status": "exact", "legal_delivery_external_candidate": "True",
              "scorecard_comparison": "confirmed", "scorecard_total": "100"}]
    result = assess_match(baseline_match(), [{"status": "verified"}], {"status": "verified"}, score, {})
    assert result["gate_typed_extras"] == "unresolved"
    assert result["gate_delivery_totals"] == "unresolved"
