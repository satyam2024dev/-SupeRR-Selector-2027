"""Verification tests ensuring complete alignment with Claude's verified pressure analysis."""
import json
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
SUBMISSION = ROOT / "submission"


def test_artifact_counts_and_presence():
    """Verify that all required ranking CSVs exist and contain exact eligible player counts."""
    bat_file = REPORTS / "ranking_batters_all_eligible.csv"
    bowl_file = REPORTS / "ranking_bowlers_all_eligible.csv"
    top_bat_file = REPORTS / "ranking_batters_top10.csv"
    top_bowl_file = REPORTS / "ranking_bowlers_top10.csv"

    assert bat_file.is_file(), "ranking_batters_all_eligible.csv missing"
    assert bowl_file.is_file(), "ranking_bowlers_all_eligible.csv missing"
    assert top_bat_file.is_file(), "ranking_batters_top10.csv missing"
    assert top_bowl_file.is_file(), "ranking_bowlers_top10.csv missing"

    bat_df = pd.read_csv(bat_file)
    bowl_df = pd.read_csv(bowl_file)
    top_bat = pd.read_csv(top_bat_file)
    top_bowl = pd.read_csv(top_bowl_file)

    assert len(bat_df) == 106, f"Expected 106 eligible batters, got {len(bat_df)}"
    assert len(bowl_df) == 89, f"Expected 89 eligible bowlers, got {len(bowl_df)}"
    assert len(top_bat) == 10, f"Expected 10 top batters, got {len(top_bat)}"
    assert len(top_bowl) == 10, f"Expected 10 top bowlers, got {len(top_bowl)}"


def test_top10_batters_benchmarks():
    """Verify exact Top 10 batter benchmarks from Claude's analysis."""
    top_bat = pd.read_csv(REPORTS / "ranking_batters_top10.csv")
    expected = [
        (1, "Vaibhav Sooryavanshi", 38.4, 2.06, 0.69),
        (2, "Heinrich Klaasen", 34.1, 2.05, 0.83),
        (3, "Rovman Powell", 28.7, 1.59, 0.57),
        (4, "Kusal Mendis", 26.5, 1.55, 0.29),
        (5, "Mohammad Nawaz", 28.2, 1.54, 0.55),
        (6, "Daryl Mitchell", 30.0, 1.52, 0.47),
        (7, "Matthew Wade", 27.7, 1.44, 0.53),
        (8, "Rinku Singh", 25.6, 1.35, 0.54),
        (9, "Dinesh Karthik", 25.9, 1.27, 0.36),
        (10, "Prabhsimran Singh", 20.3, 1.26, 0.31),
    ]

    for rank, name, shrunk_a, score, p10 in expected:
        row = top_bat[top_bat["rank"] == rank].iloc[0]
        assert row["player_name"] == name, f"At rank {rank}, expected {name}, got {row['player_name']}"
        assert abs(float(row["metric_a"]) - shrunk_a) < 0.15, f"At rank {rank}, expected Shrunk A {shrunk_a}, got {row['metric_a']}"
        assert abs(float(row["composite_score"]) - score) < 0.05, f"At rank {rank}, expected score {score}, got {row['composite_score']}"
        assert abs(float(row["p_top10"]) - p10) < 0.05, f"At rank {rank}, expected P(Top10) {p10}, got {row['p_top10']}"


def test_top10_bowlers_benchmarks():
    """Verify exact Top 10 bowler benchmarks from Claude's analysis."""
    top_bowl = pd.read_csv(REPORTS / "ranking_bowlers_top10.csv")
    expected = [
        (1, "Sunil Narine", 45.2, 3.36, 0.99),
        (2, "Rashid Khan", 29.3, 1.87, 0.75),
        (3, "Mitchell Santner", 32.4, 1.80, 0.65),
        (4, "Josh Hazlewood", 22.6, 1.70, 0.69),
        (5, "Mohsin Khan", 22.3, 1.51, 0.69),
        (6, "Adam Zampa", 18.7, 1.30, 0.49),
        (7, "Taskin Ahmed", 19.9, 1.28, 0.37),
        (8, "Shoriful Islam", 19.1, 1.18, 0.45),
        (9, "Maheesh Theekshana", 14.4, 1.17, 0.25),
        (10, "Lockie Ferguson", 24.1, 1.14, 0.38),
    ]

    for rank, name, shrunk_a, score, p10 in expected:
        row = top_bowl[top_bowl["rank"] == rank].iloc[0]
        assert row["player_name"] == name, f"At rank {rank}, expected {name}, got {row['player_name']}"
        assert abs(float(row["metric_a"]) - shrunk_a) < 0.15, f"At rank {rank}, expected Shrunk A {shrunk_a}, got {row['metric_a']}"
        assert abs(float(row["composite_score"]) - score) < 0.05, f"At rank {rank}, expected score {score}, got {row['composite_score']}"
        assert abs(float(row["p_top10"]) - p10) < 0.05, f"At rank {rank}, expected P(Top10) {p10}, got {row['p_top10']}"


def test_all_rounder_mohammad_nawaz():
    """Verify Mohammad Nawaz is ranked #5 in batting and #16 in bowling."""
    bat_df = pd.read_csv(REPORTS / "ranking_batters_all_eligible.csv")
    bowl_df = pd.read_csv(REPORTS / "ranking_bowlers_all_eligible.csv")

    nawaz_bat = bat_df[bat_df["player_name"].str.contains("Mohammad Nawaz", case=False, na=False)]
    nawaz_bowl = bowl_df[bowl_df["player_name"].str.contains("Mohammad Nawaz", case=False, na=False)]

    assert not nawaz_bat.empty, "Mohammad Nawaz missing from eligible batters"
    assert not nawaz_bowl.empty, "Mohammad Nawaz missing from eligible bowlers"

    assert int(nawaz_bat.iloc[0]["rank"]) == 5, f"Expected Nawaz batting rank 5, got {nawaz_bat.iloc[0]['rank']}"
    assert int(nawaz_bowl.iloc[0]["rank"]) == 16, f"Expected Nawaz bowling rank 16, got {nawaz_bowl.iloc[0]['rank']}"


def test_robustness_and_reliability_metadata():
    """Verify robustness and split-half reliability metadata."""
    rob_path = REPORTS / "robustness_bootstrap_results.json"
    assert rob_path.is_file(), "robustness_bootstrap_results.json missing"
    with rob_path.open(encoding="utf-8") as f:
        data = json.load(f)

    assert data["bootstrap_iterations"] == 150
    assert data["split_half_iterations"] == 200
    assert abs(data["split_half_reliability"]["batters_shrunk"] - 0.21) < 0.05
    assert abs(data["split_half_reliability"]["bowlers_shrunk"] - 0.20) < 0.05
