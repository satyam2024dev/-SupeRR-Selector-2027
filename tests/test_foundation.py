"""Synthetic fixtures exercise software behavior only; never competition findings."""
import pandas as pd
import pytest
from src.data_loader import load_dataset
from src.data_cleaning import data_quality_report
from src.batting_metrics import batting_average, strike_rate
from src.bowling_metrics import economy_rate, bowling_strike_rate
from src.eligibility import calculate_age
from src.validation import validate_data

def test_csv_loading(tmp_path):
    path = tmp_path / "synthetic_test.csv"
    pd.DataFrame({"runs": [12]}).to_csv(path, index=False)
    assert load_dataset(path).loc[0, "runs"] == 12

def test_excel_loading(tmp_path):
    path = tmp_path / "synthetic_test.xlsx"
    pd.DataFrame({"runs": [12]}).to_excel(path, index=False)
    assert load_dataset(path).loc[0, "runs"] == 12

def test_missing_and_duplicate_detection():
    frame = pd.DataFrame({"x": [None, 1, 1]})
    report = data_quality_report(frame)
    assert report["missing_by_column"]["x"] == 1
    assert report["duplicate_rows"] == 1

def test_batting_formulas():
    assert batting_average(pd.Series([60]), pd.Series([2])).iloc[0] == 30
    assert strike_rate(pd.Series([30]), pd.Series([20])).iloc[0] == 150

def test_bowling_formulas():
    assert economy_rate(pd.Series([30]), pd.Series([24])).iloc[0] == 7.5
    assert bowling_strike_rate(pd.Series([24]), pd.Series([2])).iloc[0] == 12

def test_age():
    assert calculate_age("2000-11-10", "2026-11-09") == 25

def test_invalid_statistics():
    assert not validate_data(pd.DataFrame({"runs": [-1]}))["valid"]

def test_missing_dataset(tmp_path):
    assert load_dataset(tmp_path / "absent.csv").empty

def test_unsupported_file(tmp_path):
    path = tmp_path / "unknown.bin"
    path.write_bytes(b"x")
    with pytest.raises(ValueError):
        load_dataset(path)
