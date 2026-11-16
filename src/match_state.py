"""Pre-delivery match state reconstruction with uncertainty propagation.

The engine is generic over *normalized* event columns. If a delivery's score or legal
ball status is unknown, it marks that state unknown from that point onward instead of
carrying a misleading partial total.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import pandas as pd

STATE_COLUMNS = ["score_before", "score_known", "wickets_lost_before", "legal_balls_bowled_before",
                 "legal_balls_known", "legal_balls_remaining", "target", "runs_required",
                 "current_run_rate", "required_run_rate", "state_status"]


def reconstruct_match_states(deliveries: pd.DataFrame, match_info: Mapping[str, object] | None = None,
                             *, default_overs: int = 20, super_over_innings: set[int] | None = None) -> pd.DataFrame:
    """Compute state immediately before each supplied delivery.

    Required columns: match_id, innings, sequence, team_runs_delta, legal_delivery,
    wicket_event. `match_info` may include `revised_target`, `first_inn_revised_overs`,
    and `second_inn_revised_overs`. Missing or ambiguous values stay nullable.
    """
    required = {"match_id", "innings", "sequence", "team_runs_delta", "legal_delivery", "wicket_event"}
    missing = required - set(deliveries.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if default_overs <= 0:
        raise ValueError("default_overs must be positive")
    super_set = super_over_innings or {3, 4}
    out = deliveries.copy()
    out["_input_order"] = range(len(out))
    out = out.sort_values(["match_id", "innings", "sequence", "_input_order"], kind="stable")
    info = dict(match_info or {})
    revised_target = _optional_number(info.get("revised_target"))

    rows: list[dict[str, object]] = []
    for match_id, match_group in out.groupby("match_id", sort=False, dropna=False):
        previous_innings_total: float | None = None
        previous_total_known = False
        for innings, group in match_group.groupby("innings", sort=True, dropna=False):
            inning_num = int(innings)
            max_balls = _innings_ball_limit(inning_num, info, default_overs, super_set)
            over_cap = max_balls / 6 if max_balls is not None else None
            target: float | None = None
            if inning_num == 2:
                target = revised_target if revised_target is not None else (previous_innings_total + 1 if previous_total_known and previous_innings_total is not None else None)
            elif inning_num >= 4 and inning_num in super_set:
                target = previous_innings_total + 1 if previous_total_known and previous_innings_total is not None else None

            score = 0.0
            score_known = True
            legal_balls = 0
            legal_known = True
            wickets = 0
            group_start = len(rows)
            for row in group.itertuples(index=False):
                state = {
                    "match_id": match_id, "innings": inning_num, "sequence": getattr(row, "sequence"),
                    "score_before": score if score_known else pd.NA,
                    "score_known": score_known,
                    "wickets_lost_before": wickets,
                    "legal_balls_bowled_before": legal_balls if legal_known else pd.NA,
                    "legal_balls_known": legal_known,
                    "legal_balls_remaining": max(0, max_balls - legal_balls) if legal_known and max_balls is not None else pd.NA,
                    "target": target if target is not None else pd.NA,
                    "runs_required": max(0.0, target - score) if target is not None and score_known else pd.NA,
                    "current_run_rate": (score * 6 / legal_balls) if score_known and legal_known and legal_balls > 0 else pd.NA,
                    "required_run_rate": ((max(0.0, target - score) * 6 / (max_balls - legal_balls))
                        if target is not None and score_known and legal_known and max_balls is not None and max_balls > legal_balls else pd.NA),
                    "state_status": "complete" if score_known and legal_known else ("score unknown" if not score_known else "legal ball count unknown"),
                }
                rows.append(state)
                delta = _optional_number(getattr(row, "team_runs_delta"))
                if delta is None:
                    score_known = False
                elif score_known:
                    score += delta
                legal = _optional_bool(getattr(row, "legal_delivery"))
                if legal is None:
                    legal_known = False
                elif legal_known and legal:
                    legal_balls += 1
                wicket = _optional_bool(getattr(row, "wicket_event"))
                if wicket:
                    wickets += 1

            # Add terminal metadata to each event without inventing terminal rows.
            final_score = score if score_known else None
            if final_score is not None:
                previous_innings_total, previous_total_known = final_score, True
            else:
                previous_innings_total, previous_total_known = None, False
            target_reached = target is not None and final_score is not None and final_score >= target
            wickets_limit = 2 if inning_num in super_set else 10
            if target_reached:
                end_status = "target reached"
            elif wickets >= wickets_limit:
                end_status = "all out / super over wickets limit"
            elif legal_known and max_balls is not None and legal_balls >= max_balls:
                end_status = "scheduled legal balls completed"
            elif not score_known or not legal_known:
                end_status = "incomplete: source accounting ambiguity"
            else:
                end_status = "incomplete or end condition not present in delivery file"
            for state in rows[group_start:]:
                state["innings_overs_limit"] = over_cap if over_cap is not None else pd.NA
                state["innings_balls_limit"] = max_balls if max_balls is not None else pd.NA
                state["innings_end_status"] = end_status
                state["innings_final_score_if_known"] = final_score if final_score is not None else pd.NA

    state_frame = pd.DataFrame(rows)
    out = out.merge(state_frame, on=["match_id", "innings", "sequence"], how="left", validate="many_to_one", sort=False)
    return out.sort_values("_input_order", kind="stable").drop(columns=["_input_order"]).reset_index(drop=True)


def _innings_ball_limit(innings: int, info: Mapping[str, object], default_overs: int,
                        super_over_innings: set[int]) -> int | None:
    if innings in super_over_innings:
        return 6
    field = "first_inn_revised_overs" if innings == 1 else "second_inn_revised_overs" if innings == 2 else None
    revised = _optional_number(info.get(field)) if field else None
    if revised is not None and revised > 0:
        # In the supplied feed every revised value is an integer multiple of six
        # between 30 and 114, while cricket innings cannot have 30+ overs. The observed
        # field therefore stores a ball allowance despite the `_overs` column name.
        if revised > 20 and revised.is_integer() and int(revised) % 6 == 0:
            return int(revised)
        # Allow conventional whole-over values only when they are within a T20 innings.
        if revised <= 20 and revised.is_integer():
            return int(revised * 6)
        return None
    return int(default_overs * 6)


def _optional_number(value: object) -> float | None:
    if value is None or value is pd.NA:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_bool(value: object) -> bool | None:
    if value is None or value is pd.NA or pd.isna(value):
        return None
    return bool(value)
