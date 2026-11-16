"""Load supported tabular data without modifying source files."""
from pathlib import Path
from typing import Any
import json
import pandas as pd

SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json"}

def load_dataset(path: str | Path) -> pd.DataFrame:
    """Load CSV, Excel, or JSON as a DataFrame; return empty frame for missing input.

    Unsupported extensions raise ValueError; malformed files raise their parser error.
    """
    file_path = Path(path)
    if not file_path.exists():
        return pd.DataFrame()
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(file_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)
    if suffix == ".json":
        try:
            return pd.read_json(file_path)
        except ValueError:
            with file_path.open(encoding="utf-8") as stream:
                value: Any = json.load(stream)
            return pd.json_normalize(value)
    raise ValueError(f"Unsupported file type: {suffix or '(no extension)'}")

def dataset_summary(frame: pd.DataFrame) -> dict[str, object]:
    """Return row count, column count, and column names for a dataset."""
    return {"rows": len(frame), "columns_count": len(frame.columns), "columns": list(frame.columns)}
