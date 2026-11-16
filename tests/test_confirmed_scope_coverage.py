"""Tests for confirmed IPL/T20I competition and date filtering."""
import pandas as pd

from src.confirmed_scope_coverage import classify_scope_competitions, filter_confirmed_scope


def test_competition_scope_is_derived_from_metadata_not_hardcoded_ids():
    competitions = pd.DataFrame([
        {"comp_id": 94101, "comp_name": "IPL 2022", "match_format": "T20", "season": "2022"},
        {"comp_id": 94102, "comp_name": "Example T20I Series 2023", "match_format": "T20I", "season": "2023"},
        {"comp_id": 94103, "comp_name": "T20 Emerging Cup 2024", "match_format": "T20", "season": "2024"},
        {"comp_id": 94104, "comp_name": "IPL 2021", "match_format": "T20", "season": "2021"},
        {"comp_id": 94105, "comp_name": "Other IPL event 2024", "match_format": "T20", "season": "2024"},
    ])
    result = classify_scope_competitions(competitions).set_index("comp_id")
    assert result.loc[94101, "analysis_format"] == "IPL"
    assert result.loc[94102, "analysis_format"] == "T20I"
    assert pd.isna(result.loc[94103, "analysis_format"])
    assert pd.isna(result.loc[94104, "analysis_format"])
    assert pd.isna(result.loc[94105, "analysis_format"])


def test_match_date_boundary_is_inclusive_on_2022_01_01():
    features = pd.DataFrame({"match_id": [1, 2, 3]})
    matches = pd.DataFrame([
        {"match_id": 1, "comp_id": 7701, "match_date": "2021-12-31"},
        {"match_id": 2, "comp_id": 7701, "match_date": "2022-01-01"},
        {"match_id": 3, "comp_id": 7701, "match_date": "2022-01-02"},
    ])
    competitions = pd.DataFrame([
        {"comp_id": 7701, "comp_name": "IPL 2022", "match_format": "T20", "season": "2022"},
    ])
    result = filter_confirmed_scope(features, matches, competitions)
    assert result.match_id.tolist() == [2, 3]


def test_t20i_season_and_match_date_must_both_be_in_scope():
    features = pd.DataFrame({"match_id": [10, 11, 12]})
    matches = pd.DataFrame([
        {"match_id": 10, "comp_id": 8801, "match_date": "2022-01-01"},
        {"match_id": 11, "comp_id": 8802, "match_date": "2022-01-01"},
        {"match_id": 12, "comp_id": 8801, "match_date": "2021-12-31"},
    ])
    competitions = pd.DataFrame([
        {"comp_id": 8801, "comp_name": "Example T20I Series 2022/23", "match_format": "T20I", "season": "2022/23"},
        {"comp_id": 8802, "comp_name": "IPL 2021", "match_format": "T20", "season": "2021"},
    ])
    result = filter_confirmed_scope(features, matches, competitions)
    assert result.match_id.tolist() == [10]
    assert result.analysis_format.tolist() == ["T20I"]
