"""Tests for local-only source-scope and external-coverage ceiling calculations."""
import pandas as pd

from src.external_data_feasibility import inspect_local_scope


def test_scope_ceiling_excludes_afghanistan_and_non_ipl_t20_competitions():
    matches = pd.DataFrame({
        "match_id": [1, 2, 3, 4], "comp_id": [10, 10, 20, 30],
        "home_team": ["A", "B", "Afghanistan", "C"],
        "away_team": ["D", "E", "F", "G"],
    })
    competitions = pd.DataFrame({
        "comp_id": [10, 20, 30], "match_format": ["T20", "T20I", "T20"],
        "comp_name": ["IPL 2024", "Series", "Domestic Cup"], "season": ["2024", "2024", "2024"],
    })
    balls = pd.DataFrame({"match_id": [1, 3, 4]})
    result = inspect_local_scope(matches, competitions, balls)
    assert result["match_records"] == 4
    assert result["matches_with_ball_by_ball"] == 3
    assert result["ipl_matches"] == 2
    assert result["t20i_matches_involving_afghanistan"] == 1
    assert result["potentially_covered_matches_upper_bound"] == 2
    assert result["potentially_covered_matches_already_have_ball_by_ball"] == 1
    assert result["potentially_covered_matches_missing_ball_by_ball"] == 1
    assert result["potentially_coverable_regulation_innings_upper_bound"] == 4
