"""Role-aware comparison and readable player profile helpers."""
import pandas as pd

def compare_players(frame: pd.DataFrame, player_column: str, players: list[str], metrics: list[str], role_column: str | None = None) -> pd.DataFrame:
    """Return selected metric values for players, optionally limiting to one role."""
    required = {player_column, *metrics}
    if not required.issubset(frame.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(frame.columns))}")
    subset = frame.loc[frame[player_column].isin(players)].copy()
    if role_column and role_column in subset:
        subset = subset.drop_duplicates([player_column, role_column])
    return subset[[player_column] + ([role_column] if role_column and role_column in subset else []) + metrics]

def player_profile(row: pd.Series, metrics: list[str]) -> dict[str, object]:
    """Build an interpretable profile from existing fields only."""
    return {"player": row.get("player_name", row.name), "metrics": {m: row.get(m) for m in metrics if m in row.index}}
