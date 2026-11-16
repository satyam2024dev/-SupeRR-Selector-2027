"""Project paths and conservative defaults."""
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = ROOT / "data" / "raw"
PROCESSED_DATA_DIR = ROOT / "data" / "processed"
REFERENCE_DATE = date(2027, 1, 1)
