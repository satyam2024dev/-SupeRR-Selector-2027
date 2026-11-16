"""Integrity and plausibility checks for common cricket metrics."""
import pandas as pd

def validate_data(frame: pd.DataFrame) -> dict[str, object]:
    """Flag negative counts, percentage bounds and non-finite numeric values."""
    issues: list[dict[str, object]] = []
    for col in frame.select_dtypes(include="number"):
        values = frame[col]
        if (values < 0).any():
            issues.append({"column": col, "issue": "negative values", "rows": frame.index[values < 0].tolist()})
        if "percentage" in str(col).lower() and ((values < 0) | (values > 100)).any():
            issues.append({"column": col, "issue": "percentage outside 0..100", "rows": frame.index[(values < 0) | (values > 100)].tolist()})
        if (~values.map(lambda x: pd.notna(x) and abs(x) != float("inf"))).any():
            issues.append({"column": col, "issue": "non-finite values", "rows": frame.index[~values.map(lambda x: pd.notna(x) and abs(x) != float("inf"))].tolist()})
    return {"valid": not issues, "issues": issues, "missing_by_column": frame.isna().sum().to_dict()}
