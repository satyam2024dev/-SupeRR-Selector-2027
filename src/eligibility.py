"""Evidence-driven eligibility utilities; no competition rule is assumed."""
from datetime import date, datetime
import pandas as pd

def calculate_age(dob: date | datetime | str | pd.Timestamp, reference_date: date | datetime | str) -> int:
    """Calculate completed years at a reference date; reject invalid/future DOBs."""
    birth, ref = pd.Timestamp(dob).date(), pd.Timestamp(reference_date).date()
    if birth > ref:
        raise ValueError("Date of birth is after reference date")
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))

def verify_uncapped(frame: pd.DataFrame, *, rule: str | None = None, identifier_column: str | None = None,
                    dob_column: str | None = None, reference_date: date | None = None) -> pd.DataFrame:
    """Attach review flags; uncapped status is unknown until an explicit rule is supplied.

    `rule` documents the competition definition but is not executed as code. A domain
    owner must provide verified status in the source data to establish eligibility.
    """
    result = frame.copy()
    result["eligibility_status"] = "unverified"
    result["eligibility_reason"] = "Competition rule or verified status not supplied"
    if identifier_column and identifier_column in result:
        duplicated = result[identifier_column].notna() & result[identifier_column].duplicated(keep=False)
        result.loc[duplicated, "eligibility_reason"] = "Duplicate player identifier requires review"
    if dob_column and dob_column in result and reference_date:
        result["age_years"] = pd.to_datetime(result[dob_column], errors="coerce").map(
            lambda d: calculate_age(d, reference_date) if pd.notna(d) else pd.NA)
    if rule:
        result["eligibility_reason"] = "Rule documented; verified uncapped evidence still required"
    return result
