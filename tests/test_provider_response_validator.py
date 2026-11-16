"""Synthetic-only tests for Phase 3E provider intake validation."""
import hashlib
import json
from pathlib import Path

import pandas as pd

from src.provider_response_validator import (
    EXPECTED_FIELDS,
    pressure_coverage_gate,
    validate_deliveries,
    validate_dictionary,
    write_bundle_validation,
    ROOT,
)


def synthetic_delivery(**changes):
    row = {
        "official_match_id": "SYN-M1", "provider_match_id": "SYN-P1", "innings": 2,
        "innings_type": "regular", "sequence": 1, "over": 1, "delivery_position": 1,
        "batter_id": "SYN-B1", "non_striker_id": "SYN-B2", "bowler_id": "SYN-B3",
        "batter_runs": 1, "wides_runs": 0, "noballs_runs": 0, "byes_runs": 0,
        "legbyes_runs": 0, "penalty_runs": 0, "other_extras_runs": 0, "total_runs": 1,
        "is_legal_delivery": True, "is_wicket": False, "team_wicket_lost": False,
        "bowler_credited_wicket": False, "dismissal_type": None, "dismissed_player_id": None,
        "target_runs": 150, "target_balls": 120, "revised_target": False,
        "scheduled_legal_balls": 120, "innings_total_runs": 149, "innings_wickets": 8,
        "is_super_over": False,
    }
    row.update(changes)
    return row


def decisions(frame):
    return {row["field"]: row for row in validate_deliveries(frame)}


def test_synthetic_ordinary_delivery_and_component_total_pass():
    result = decisions(pd.DataFrame([synthetic_delivery()]))
    assert result["total_runs"]["status"] == "pass"
    assert result["legal_ball_semantics"]["status"] == "pass"
    assert result["targets"]["status"] == "pass"
    assert result["player_ids"]["status"] == "pass"


def test_synthetic_extras_strata_account_for_team_total():
    rows = [
        synthetic_delivery(sequence=1, batter_runs=0, wides_runs=1, total_runs=1, is_legal_delivery=False),
        synthetic_delivery(sequence=2, batter_runs=0, noballs_runs=1, total_runs=1, is_legal_delivery=False),
        synthetic_delivery(sequence=3, batter_runs=0, byes_runs=1, total_runs=1),
        synthetic_delivery(sequence=4, batter_runs=0, legbyes_runs=1, total_runs=1),
    ]
    result = decisions(pd.DataFrame(rows))
    assert result["total_runs"]["status"] == "pass"
    assert result["legal_ball_semantics"]["status"] == "pass"


def test_synthetic_wrong_total_and_illegal_ball_flag_fail():
    result = decisions(pd.DataFrame([synthetic_delivery(total_runs=3, wides_runs=1, is_legal_delivery=True)]))
    assert result["total_runs"]["status"] == "fail"
    assert result["legal_ball_semantics"]["status"] == "fail"


def test_synthetic_missing_target_and_player_id_are_not_filled():
    result = decisions(pd.DataFrame([synthetic_delivery(target_runs=None, batter_id=None)]))
    assert result["targets"]["status"] == "unresolved"
    assert result["player_ids"]["status"] == "fail"


def test_synthetic_duplicate_delivery_key_fails():
    result = decisions(pd.DataFrame([synthetic_delivery(), synthetic_delivery()]))
    assert result["delivery_key"]["status"] == "fail"


def test_synthetic_retired_hurt_and_retired_out_keep_team_wicket_semantics_distinct():
    hurt = synthetic_delivery(is_wicket=True, dismissal_type="retired hurt", dismissed_player_id="SYN-B1")
    out = synthetic_delivery(sequence=2, is_wicket=True, team_wicket_lost=True,
                             dismissal_type="retired out", dismissed_player_id="SYN-B2")
    result = decisions(pd.DataFrame([hurt, out]))
    assert result["wicket_semantics"]["status"] == "pass"


def test_synthetic_super_over_identity_mismatch_fails():
    result = decisions(pd.DataFrame([synthetic_delivery(innings=3, innings_type="super_over", is_super_over=True)]))
    assert result["super_over"]["status"] == "pass"
    bad = decisions(pd.DataFrame([synthetic_delivery(innings=3, innings_type="regular", is_super_over=True)]))
    assert bad["super_over"]["status"] == "fail"


def test_synthetic_dictionary_requires_all_fields_and_semantic_definitions():
    dictionary = pd.DataFrame([
        {"field_name": name, "type": spec["type"], "nullable": spec["nullable"],
         "definition": spec["definition"], "units": "synthetic", "grain": "synthetic", "enum_values": ""}
        for name, spec in EXPECTED_FIELDS.items()
    ])
    assert all(item["status"] == "pass" for item in validate_dictionary(dictionary))
    reduced = dictionary[dictionary.field_name != "target_runs"]
    assert {x["field"]: x["status"] for x in validate_dictionary(reduced)}["target_runs"] == "unresolved"


def test_synthetic_pressure_coverage_remains_blocked_until_every_state_gate_passes():
    checks = [{"field": "total_runs", "status": "pass"}, {"field": "legal_ball_semantics", "status": "pass"},
              {"field": "targets", "status": "unresolved"}, {"field": "super_over", "status": "pass"}]
    result = pressure_coverage_gate(checks, [])
    assert result["status"] == "blocked_unresolved"
    assert result["coverage_rows"] is None


def test_synthetic_pressure_gate_only_opens_after_required_field_checks_pass():
    names = ["total_runs", "legal_ball_semantics", "targets", "super_over", "stratum_ordinary",
             "stratum_wides", "stratum_no_balls", "stratum_byes", "stratum_legbyes",
             "stratum_penalties", "stratum_other_extras", "stratum_wickets", "stratum_super_overs", "stratum_revised_targets"]
    checks = [{"field": name, "status": "pass"} for name in names]
    result = pressure_coverage_gate(checks, [], semantic_review_passed=True)
    assert result["status"] == "eligible_to_estimate"
    assert result["coverage_rows"] == "requires complete source-backed delivery replay"


def test_synthetic_provider_dictionary_alone_cannot_authorize_pressure_coverage():
    names = ["total_runs", "legal_ball_semantics", "targets", "super_over", "stratum_ordinary",
             "stratum_wides", "stratum_no_balls", "stratum_byes", "stratum_legbyes",
             "stratum_penalties", "stratum_other_extras", "stratum_wickets", "stratum_super_overs", "stratum_revised_targets"]
    checks = [{"field": name, "status": "pass"} for name in names]
    assert pressure_coverage_gate(checks, [])["status"] == "blocked_unresolved"


def test_bundle_validation_writes_isolated_audit_and_never_changes_inputs_or_accepted_layer(tmp_path):
    bundle = tmp_path / "incoming" / "provider-v1"
    bundle.mkdir(parents=True)
    manifest = bundle / "manifest.json"
    manifest.write_text(json.dumps({"provider": "Synthetic Fixture", "schema_version": "v1"}), encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    accepted_layer = ROOT / "data" / "processed" / "accepted_external_deliveries.csv.gz"
    accepted_hash = hashlib.sha256(accepted_layer.read_bytes()).hexdigest() if accepted_layer.exists() else None
    output_dir = tmp_path / "audit"

    gate = write_bundle_validation(bundle, output_dir)

    assert gate["status"] == "blocked_unresolved"
    assert (output_dir / "provider_response_field_checks.csv").exists()
    assert (output_dir / "provider_response_validation_spec.md").exists()
    assert (output_dir / "provider_response_gate.json").exists()
    assert hashlib.sha256(manifest.read_bytes()).hexdigest() == manifest_hash
    assert not (bundle / "data_dictionary.csv").exists()
    if accepted_hash is not None:
        assert hashlib.sha256(accepted_layer.read_bytes()).hexdigest() == accepted_hash


def test_bundle_validation_refuses_output_inside_provider_bundle(tmp_path):
    bundle = tmp_path / "incoming" / "provider-v1"
    bundle.mkdir(parents=True)
    manifest = bundle / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": "v1"}), encoding="utf-8")
    original = manifest.read_bytes()

    try:
        write_bundle_validation(bundle, bundle / "validation")
    except ValueError as exc:
        assert "outside the provider bundle" in str(exc)
    else:
        raise AssertionError("validator should refuse to write into provider originals")
    assert manifest.read_bytes() == original


def test_bundle_validation_refuses_raw_or_processed_output_directories(tmp_path):
    bundle = tmp_path / "incoming" / "provider-v1"
    bundle.mkdir(parents=True)
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "v1"}), encoding="utf-8")
    for protected in [ROOT / "data" / "raw", ROOT / "data" / "processed"]:
        try:
            write_bundle_validation(bundle, protected)
        except ValueError as exc:
            assert "data/raw, and data/processed" in str(exc)
        else:
            raise AssertionError(f"validator should refuse protected output path {protected}")
