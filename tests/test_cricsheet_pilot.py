from io import BytesIO
import zipfile
import pandas as pd
import pytest
from urllib.error import HTTPError

import src.cricsheet_pilot as pilot

from src.cricsheet_pilot import (
    _match_index_candidates,
    _make_crosswalk,
    _metadata_identity,
    _numeric_json_entries,
    _parse_info_member,
    _json_payload,
    _load_match_index_archive,
    accept_match,
    compare_deliveries,
)


def _local_delivery(**overrides):
    row = {
        "match_id": 77,
        "innings": 1,
        "innings_ball_num": 1,
        "overid": 1,
        "over_ball_num": 1,
        "striker_id": 10,
        "striker_name": "Batter One",
        "non_striker_id": 11,
        "non_striker_name": "Batter Two",
        "bowler_id": 20,
        "bowler_name": "Bowler One",
        "runs": 1,
        "extras_type": None,
        "extras1_runs": 0,
        "extras_2_runs": 0,
        "is_wicket": 0,
        "dismissal_type": None,
        "dismissed_player_id": None,
        "legal_delivery": True,
        "legal_delivery_status": "verified",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def _external_delivery(**overrides):
    row = {
        "innings": 1,
        "over": 1,
        "delivery_position": 1,
        "batter_name_external": "Batter One",
        "non_striker_name_external": "Batter Two",
        "bowler_name_external": "Bowler One",
        "batter_runs_external": 1,
        "extras_total_external": 0,
        "total_runs_external": 1,
        "extras_keys": "",
        "extras_json": "{}",
        "wickets_json": "[]",
        "wicket_count_external": 0,
        "dismissal_kinds_external": "",
        "dismissed_names_external": "",
        "legal_delivery_external_candidate": True,
        "innings_super_over_external": False,
    }
    row.update(overrides)
    return [row]


def _all_exact_checks():
    return {
        "external_file_status": "downloaded",
        "match_identity_status": "exact",
        "genuine_mismatch_count": 0,
        "player_identity_status": "exact",
        "venue_identity_status": "exact",
        "delivery_sequence_status": "exact",
        "batter_runs_status": "exact",
        "extras_amounts_status": "exact",
        "total_runs_status": "exact",
        "legal_balls_status": "exact",
        "wickets_status": "exact",
        "innings_totals_status": "exact",
        "target_status": "exact",
        "bowling_figures_status": "exact",
        "result_status": "exact",
    }


def test_metadata_identity_requires_date_teams_format_and_competition():
    local = pd.Series({
        "match_date": "2024-05-01",
        "home_team": "Rajasthan Royals",
        "away_team": "Mumbai Indians",
        "comp_name": "IPL 2024",
        "season": 2024,
        "venue_id": 12,
        "venue_country": "India",
    })
    payload = {"info": {
        "dates": ["2024-05-01"],
        "teams": ["Mumbai Indians", "Rajasthan Royals"],
        "match_type": "T20",
        "event": {"name": "Indian Premier League 2024"},
        "venue": "Jaipur",
        "outcome": {},
    }}
    identity = _metadata_identity(local, payload)
    assert identity["date_match"]
    assert identity["teams_match"]
    assert identity["format_match"]
    assert identity["competition_family_match"]
    assert identity["venue_comparison_status"].startswith("unresolved")


def test_bilateral_t20i_competition_label_variants_are_mapped_by_both_teams():
    local = pd.Series({
        "match_date": "2022-01-22",
        "home_team": "West Indies",
        "away_team": "England",
        "comp_name": "England in West Indies T20I Series 2022",
        "season": 2022,
        "venue_id": 54,
        "venue_country": "West Indies",
    })
    payload = {"info": {
        "dates": ["2022-01-22"],
        "teams": ["West Indies", "England"],
        "match_type": "T20",
        "event": {"name": "England tour of West Indies"},
        "venue": "Kensington Oval",
    }}
    identity = _metadata_identity(local, payload)
    assert identity["teams_match"]
    assert identity["competition_family_match"]
    assert identity["competition_match_basis"] == "both_local_teams_in_external_bilateral_event"


def test_numeric_json_member_is_resolved_by_date_and_team_match_index():
    index = pd.DataFrame(
        _parse_info_member(b"info,team,Rajasthan Royals\ninfo,team,Mumbai Indians\ninfo,date,2024/05/01\ninfo,match_id,1234567\n")
        + _parse_info_member(b"info,team,Rajasthan Royals\ninfo,team,Mumbai Indians\ninfo,date,2024/05/02\ninfo,match_id,7654321\n")
    )
    local = pd.Series({
        "match_date": "2024-05-01",
        "home_team": "Mumbai Indians",
        "away_team": "Rajasthan Royals",
        "comp_name": "IPL 2024",
    })
    ids = _match_index_candidates(index, local)
    assert ids == ["1234567"]
    entries = [
        {"filename": "1234567.json"},
        {"filename": "7654321.json"},
        {"filename": "README.txt"},
    ]
    assert [x["filename"] for x in _numeric_json_entries(entries, ids)] == ["1234567.json"]


def test_duplicate_date_and_team_candidates_are_ambiguous_not_forced():
    index = pd.DataFrame(
        _parse_info_member(b"info,team,Rajasthan Royals\ninfo,team,Mumbai Indians\ninfo,date,2024/05/01\ninfo,match_id,1234567\n")
        + _parse_info_member(b"info,team,Mumbai Indians\ninfo,team,Rajasthan Royals\ninfo,date,2024/05/01\ninfo,match_id,7654321\n")
    )
    local = pd.Series({
        "match_date": "2024-05-01",
        "home_team": "Rajasthan Royals",
        "away_team": "Mumbai Indians",
    })
    assert _match_index_candidates(index, local) == ["1234567", "7654321"]


def test_cricsheet_info_member_resolves_numeric_id_and_filters_t20i_gender():
    info = (
        b"version,2.4.0\ninfo,team,England\ninfo,team,Pakistan\n"
        b"info,gender,male\ninfo,date,2024/05/22\ninfo,match_id,1500001\n"
    )
    records = _parse_info_member(info, "9999999")
    assert records == [{
        "match_id": "1500001",
        "start_date": "2024-05-22",
        "team_pair_key": tuple(sorted(("england", "pakistan"))),
        "gender": "male",
    }]
    index = pd.DataFrame(records + [{**records[0], "match_id": "1500002", "gender": "female"}])
    local = pd.Series({
        "match_date": "2024-05-22",
        "home_team": "England",
        "away_team": "Pakistan",
        "match_format": "T20I",
    })
    assert _match_index_candidates(index, local) == ["1500001"]


def test_match_index_archive_reads_info_members_only(monkeypatch):
    archive_buffer = BytesIO()
    info = (
        "version,2.4.0\ninfo,team,India\ninfo,team,Sri Lanka\n"
        "info,gender,male\ninfo,date,2024/07/30\ninfo,match_id,1500003\n"
    )
    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("1500003_info.csv", info)
        archive.writestr("1500003.csv", "this delivery data is deliberately not parsed")

    class Response(BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda request, timeout: Response(archive_buffer.getvalue()))
    frame, sha, count = _load_match_index_archive("https://example.test/metadata.zip")
    assert frame.loc[0, "match_id"] == "1500003"
    assert count == 1
    assert len(sha) == 64


def test_unindexed_candidate_stays_unresolved_not_not_found():
    status, _ = accept_match({"external_file_status": "unresolved_no_match_index_entry"})
    assert status == "unresolved"


def test_json_error_body_and_invalid_structure_are_rejected():
    with pytest.raises(ValueError, match="Invalid JSON response"):
        _json_payload(b"<html>502 Bad Gateway</html>", "fake.json")
    with pytest.raises(ValueError, match="Unexpected Cricsheet JSON structure"):
        _json_payload(b"{\"error\":\"not a match\"}", "fake.json")


def test_http_errors_propagate_from_archive_metadata_request(monkeypatch):
    def fail_request(request, timeout):
        raise HTTPError(request.full_url, 503, "upstream unavailable", {}, None)

    monkeypatch.setattr(pilot.urllib.request, "urlopen", fail_request)
    with pytest.raises(HTTPError, match="upstream unavailable"):
        pilot.zip_directory("https://cricsheet.org/downloads/ipl_json.zip")


def test_delivery_comparison_marks_compared_runs_exact_and_names_are_not_id_join():
    compared = compare_deliveries(77, _local_delivery(), _external_delivery(), {})
    assert compared.loc[0, "batter_runs_status"] == "exact"
    assert compared.loc[0, "batter_name_content_match"]
    assert compared.loc[0, "batter_id_mapping_status"] == "unresolved"
    assert compared.loc[0, "delivery_reconciliation_status"] == "partial_match"


def test_delivery_comparison_surfaces_batter_run_disagreement():
    compared = compare_deliveries(
        77, _local_delivery(), _external_delivery(batter_runs_external=4), {}
    )
    assert compared.loc[0, "batter_runs_status"] == "mismatch"
    assert compared.loc[0, "delivery_reconciliation_status"] == "mismatch"


@pytest.mark.parametrize(
    ("kind", "local_wicket", "expected_team_wickets", "expected_bowler_credit", "expected_status"),
    [
        ("retired hurt", 0, 0, 0, "exact"),
        ("retired out", 0, 1, 0, "mismatch"),
        ("bowled", 0, 1, 1, "mismatch"),
    ],
)
def test_wicket_comparison_separates_retirement_and_bowler_credit(
    kind, local_wicket, expected_team_wickets, expected_bowler_credit, expected_status
):
    wickets = [{"kind": kind, "player_out": "Batter One"}]
    external = _external_delivery(
        wickets_json=__import__("json").dumps(wickets),
        wicket_count_external=1,
        team_wicket_count_external=pilot._team_wickets_lost(wickets),
        bowler_credited_wicket_count_external=pilot._bowler_credited_wickets(wickets),
        dismissal_kinds_external=kind,
        dismissed_names_external="Batter One",
    )
    compared = compare_deliveries(
        77, _local_delivery(is_wicket=local_wicket), external, {}
    )
    assert compared.loc[0, "team_wicket_count_external"] == expected_team_wickets
    assert compared.loc[0, "bowler_credited_wicket_count_external"] == expected_bowler_credit
    assert compared.loc[0, "wicket_count_status"] == expected_status
    if kind == "retired hurt":
        assert compared.loc[0, "dismissal_kind_status"].startswith("non_wicket_retirement")


def test_retired_out_is_team_wicket_but_not_bowler_credited():
    wickets = [{"kind": "retired out", "player_out": "Batter One"}]
    assert pilot._team_wickets_lost(wickets) == 1
    assert pilot._bowler_credited_wickets(wickets) == 0


def test_ordinary_bowler_dismissal_is_team_wicket_and_bowler_credited():
    wickets = [{"kind": "caught and bowled", "player_out": "Batter One"}]
    assert pilot._team_wickets_lost(wickets) == 1
    assert pilot._bowler_credited_wickets(wickets) == 1


def test_duplicate_external_delivery_coordinate_is_rejected():
    duplicate = _external_delivery() * 2
    with pytest.raises(ValueError, match="Duplicate external delivery coordinates"):
        compare_deliveries(77, _local_delivery(), duplicate, {})


def test_duplicate_local_delivery_coordinate_is_rejected():
    duplicate = pd.concat([_local_delivery(), _local_delivery()], ignore_index=True)
    with pytest.raises(ValueError, match="Duplicate local delivery coordinates"):
        compare_deliveries(77, duplicate, _external_delivery(), {})


def test_ambiguous_player_registry_id_is_not_joined():
    local = _local_delivery()
    people = pd.DataFrame([
        {"identifier": "cs-person-1", "name": "Batter One", "key_bcci": "10"},
        {"identifier": "cs-person-2", "name": "Batter One", "key_bcci": "10"},
    ])
    payloads = {77: {"info": {"registry": {"people": {"Batter One": "cs-person-1", "Batter Two": "cs-person-2"}}}}}
    crosswalk, state = _make_crosswalk(local, payloads, people)
    batter = crosswalk[crosswalk.official_player_id.eq(10)].iloc[0]
    assert batter.identity_status == "ambiguous_exact_id_maps_to_multiple_register_people"
    assert state[(77, 10)] == "ambiguous"


def test_acceptance_gate_accepts_only_complete_exact_record_and_rejects_mismatch():
    assert accept_match(_all_exact_checks())[0] == "accepted"
    bad = _all_exact_checks()
    bad["genuine_mismatch_count"] = 1
    assert accept_match(bad)[0] == "rejected"
    incomplete = _all_exact_checks()
    incomplete["player_identity_status"] = "unresolved"
    assert accept_match(incomplete)[0] == "unresolved"
