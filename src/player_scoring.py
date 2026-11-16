"""Configurable, role-specific scoring scaffolding without default player rankings."""
from collections.abc import Mapping
import pandas as pd

SUPPORTED_ROLES = {"batter", "bowler", "all_rounder", "wicketkeeper"}

def score_players(frame: pd.DataFrame, role: str, weights: Mapping[str, float], *, min_observations: int = 1) -> pd.DataFrame:
    """Weighted mean of supplied normalized metric columns; caller owns normalization.

    Age is deliberately excluded. Correlated metrics should be reviewed before weights
    are configured; this function rejects duplicate weight keys by construction of Mapping.
    """
    if role not in SUPPORTED_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    if not weights or any(weight < 0 for weight in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Weights must be non-negative with a positive total")
    missing = set(weights) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing score columns: {sorted(missing)}")
    result = frame.copy()
    values = result[list(weights)].apply(pd.to_numeric, errors="coerce")
    weighted = values.mul(pd.Series(weights)).sum(axis=1, min_count=1)
    weight_present = values.notna().mul(pd.Series(weights)).sum(axis=1)
    result["performance_score"] = weighted.div(weight_present.replace(0, pd.NA))
    result["age_rank"] = result["age_years"].rank(method="min", ascending=True) if "age_years" in result else pd.NA
    result["performance_rank"] = result["performance_score"].rank(method="min", ascending=False)
    result.attrs["role"] = role
    result.attrs["minimum_observations_note"] = min_observations
    return result
