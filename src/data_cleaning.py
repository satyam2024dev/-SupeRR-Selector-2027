"""Non-destructive data quality diagnostics."""
import pandas as pd

def data_quality_report(frame: pd.DataFrame, player_name_column: str | None = None) -> dict[str, object]:
    """Report nulls, exact duplicates, object/numeric type hints and name variants."""
    invalid = [str(c) for c in frame.columns if frame[c].dtype == "object" and frame[c].dropna().map(lambda x: isinstance(x, (int, float))).any()]
    names: dict[str, list[str]] = {}
    if player_name_column and player_name_column in frame:
        grouped: dict[str, set[str]] = {}
        for value in frame[player_name_column].dropna().astype(str):
            grouped.setdefault(" ".join(value.casefold().split()), set()).add(value)
        names = {key: sorted(values) for key, values in grouped.items() if len(values) > 1}
    return {"rows": len(frame), "columns": len(frame.columns), "missing_by_column": frame.isna().sum().to_dict(),
            "duplicate_rows": int(frame.duplicated().sum()), "possible_mixed_type_columns": invalid,
            "inconsistent_player_names": names}

def missing_value_report(frame: pd.DataFrame) -> pd.Series:
    """Count missing values per column without dropping records."""
    return frame.isna().sum()

def duplicate_row_count(frame: pd.DataFrame) -> int:
    """Count exact duplicate rows without removing them."""
    return int(frame.duplicated().sum())
