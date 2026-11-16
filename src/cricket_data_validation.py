"""Inspect delivery-level score fields without silently imputing cricket events.

The feed's extras fields are not sufficiently labelled to recover every extra run.
This module preserves that uncertainty so downstream state reconstruction can fail closed.
"""
from __future__ import annotations

from collections.abc import Iterable
import pandas as pd


EXTRAS_CODE_LABEL = {
    1: "Overstep", 2: "wide", 3: "legbyes", 4: "byes",
    5: "other", 6: "no extras_type label", 7: "Penalty",
}
EXTRA_EVENT_TYPES = {"overstep", "wide", "legbyes", "byes", "other", "penalty"}


def analyze_extras(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Summarize observed extras code, type, and amount patterns.

    No run meaning is assigned to ``extras_2_runs``. The output includes its frequency
    distribution by extras label so a data owner can resolve the encoding.
    """
    required = {"extras_type", "extras1_runs", "extras_2_runs", "runs", "is_wicket"}
    missing = required - set(deliveries.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    frame = deliveries.copy()
    frame["extras_type_label"] = frame["extras_type"].fillna("(null)").astype(str)
    rows = []
    for label, group in frame.groupby("extras_type_label", sort=True, dropna=False):
        code_values = sorted(pd.to_numeric(group["extras1_runs"], errors="coerce").dropna().unique().tolist())
        amount_counts = pd.to_numeric(group["extras_2_runs"], errors="coerce").value_counts(dropna=False).to_dict()
        rows.append({
            "extras_type": label,
            "rows": len(group),
            "extras1_runs_values": ",".join(map(str, code_values)),
            "extras1_runs_is_singleton": len(code_values) == 1,
            "extras_2_runs_distribution": "; ".join(f"{k}:{v}" for k, v in sorted(amount_counts.items(), key=lambda x: str(x[0]))),
            "runs_distribution": "; ".join(f"{k}:{v}" for k, v in sorted(group["runs"].value_counts(dropna=False).items())),
            "runs_sum_observed": int(pd.to_numeric(group["runs"], errors="coerce").sum()),
            "wicket_rows": int(group["is_wicket"].fillna(False).astype(bool).sum()),
            "interpretation": _extras_interpretation(label, code_values),
            "run_amount_status": "unresolved; do not treat extras1_runs or extras_2_runs as a complete amount without source documentation",
        })
    return pd.DataFrame(rows)


def _extras_interpretation(label: str, codes: list[float]) -> str:
    """Describe pattern, explicitly separating observation from inference."""
    code_map = {"(null)": 6, "Overstep": 1, "wide": 2, "legbyes": 3,
                "byes": 4, "other": 5, "Penalty": 7}
    expected = code_map.get(label)
    if expected is not None and codes == [expected]:
        return f"Observed extras1_runs={expected} is a category-like code matching label {label!r}; not a run amount."
    return "Observed values do not establish field meaning."


def normalize_delivery_events(deliveries: pd.DataFrame) -> pd.DataFrame:
    """Add conservative score/ball event fields for state reconstruction.

    Ordinary labelled deliveries with zero ``extras_2_runs`` use ``runs`` as a
    provisional team-run delta. Every extras-labelled event and any nonzero secondary
    amount has unknown team-run delta until the feed semantics are verified.
    ``Overstep`` is treated as a no-ball candidate for legal-ball accounting based on
    its label and cricket terminology; the mapping remains explicitly marked inferred.
    """
    required = {"runs", "extras_type", "extras_2_runs", "is_wicket"}
    missing = required - set(deliveries.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    out = deliveries.copy()
    labels = out["extras_type"].astype("string").str.casefold()
    code = pd.to_numeric(out["extras1_runs"], errors="coerce") if "extras1_runs" in out else pd.Series(pd.NA, index=out.index)
    secondary = pd.to_numeric(out["extras_2_runs"], errors="coerce")
    raw_runs = pd.to_numeric(out["runs"], errors="coerce")

    code_matches = labels.isna() & code.eq(6) | labels.eq("overstep") & code.eq(1) | labels.eq("wide") & code.eq(2) | labels.eq("legbyes") & code.eq(3) | labels.eq("byes") & code.eq(4) | labels.eq("other") & code.eq(5) | labels.eq("penalty") & code.eq(7)
    out["extras_code_pattern_valid"] = code_matches.fillna(False)
    out["batter_runs_candidate"] = raw_runs
    out["batter_runs_status"] = "candidate: source runs field; validate on extras before formal use"
    out.loc[labels.isna() & secondary.eq(0), "batter_runs_status"] = "provisional: ordinary delivery, runs agrees with boundary flags"

    ordinary = labels.isna() & secondary.eq(0) & raw_runs.notna()
    out["team_runs_delta"] = pd.Series(pd.NA, index=out.index, dtype="Float64")
    out.loc[ordinary, "team_runs_delta"] = raw_runs.loc[ordinary].astype(float)
    out["team_runs_status"] = "unknown: extras amount or field meaning is unresolved"
    out.loc[ordinary, "team_runs_status"] = "provisional exact for ordinary delivery only"

    legal = pd.Series(pd.NA, index=out.index, dtype="boolean")
    legal.loc[labels.isna() & secondary.eq(0)] = True
    legal.loc[labels.isin(["wide", "overstep"])] = False
    legal.loc[labels.isin(["byes", "legbyes"])] = True
    legal.loc[labels.isna() & secondary.ne(0)] = pd.NA
    out["legal_delivery"] = legal
    out["legal_delivery_status"] = "unknown: extras category does not determine validity"
    out.loc[labels.isna() & secondary.eq(0), "legal_delivery_status"] = "provisional valid delivery"
    out.loc[labels.eq("wide"), "legal_delivery_status"] = "wide: invalid ball under Laws of Cricket"
    out.loc[labels.eq("overstep"), "legal_delivery_status"] = "inferred no-ball from Overstep label: invalid ball; confirm feed mapping"
    out.loc[labels.isin(["byes", "legbyes"]), "legal_delivery_status"] = "provisional valid delivery: bye/leg-bye are not no-ball labels"
    out.loc[labels.eq("other") | labels.eq("penalty"), "legal_delivery"] = pd.NA
    out.loc[labels.eq("other") | labels.eq("penalty"), "legal_delivery_status"] = "unknown: source category does not specify validity"
    out["wicket_event"] = out["is_wicket"].fillna(False).astype(bool)
    out["wicket_status"] = "event flag; bowler credit requires dismissal-type rules"
    return out


def delivery_validation_summary(deliveries: pd.DataFrame) -> dict[str, object]:
    """Return deterministic cross-field checks and explicit unresolved questions."""
    normalized = normalize_delivery_events(deliveries)
    labels = deliveries["extras_type"].astype("string").str.casefold()
    wicket = deliveries["is_wicket"].fillna(False).astype(bool)
    four_mismatch = deliveries["is_four"].fillna(False).astype(bool) & pd.to_numeric(deliveries["runs"], errors="coerce").ne(4) if "is_four" in deliveries else pd.Series(False, index=deliveries.index)
    six_mismatch = deliveries["is_six"].fillna(False).astype(bool) & pd.to_numeric(deliveries["runs"], errors="coerce").ne(6) if "is_six" in deliveries else pd.Series(False, index=deliveries.index)
    dismissal = deliveries["dismissal_type"].notna() if "dismissal_type" in deliveries else pd.Series(False, index=deliveries.index)
    return {
        "rows": len(deliveries),
        "extras_code_pattern_mismatch_rows": int((~normalized["extras_code_pattern_valid"]).sum()),
        "runs_column_sum_not_total_claim": int(pd.to_numeric(deliveries["runs"], errors="coerce").sum()),
        "extras_2_runs_sum_not_total_claim": int(pd.to_numeric(deliveries["extras_2_runs"], errors="coerce").sum()),
        "wide_rows": int(labels.eq("wide").sum()),
        "overstep_rows": int(labels.eq("overstep").sum()),
        "bye_rows": int(labels.eq("byes").sum()),
        "legbye_rows": int(labels.eq("legbyes").sum()),
        "other_extra_rows": int(labels.eq("other").sum()),
        "unknown_total_run_delta_rows": int(normalized["team_runs_delta"].isna().sum()),
        "unknown_legal_delivery_rows": int(normalized["legal_delivery"].isna().sum()),
        "four_flag_runs_mismatch_rows": int(four_mismatch.sum()),
        "six_flag_runs_mismatch_rows": int(six_mismatch.sum()),
        "wicket_flag_rows": int(wicket.sum()),
        "dismissal_type_nonnull_rows": int(dismissal.sum()),
        "wicket_flag_without_dismissal_type_rows": int((wicket & ~dismissal).sum()),
        "dismissed_player_id_missing_on_wicket_rows": int((wicket & deliveries["dismissed_player_id"].isna()).sum()) if "dismissed_player_id" in deliveries else None,
        "legal_ball_count_status": "ordinary/wide/bye/legbye classifications are pattern-based; Overstep is inferred no-ball; other/Penalty and exotic overlapping events remain unresolved",
        "total_runs_status": "not fully verifiable: extras run amount is absent or ambiguous for extras-labelled rows",
        "bowler_runs_status": "not verifiable from these fields: no complete total extras or bowler-conceded amount",
    }
