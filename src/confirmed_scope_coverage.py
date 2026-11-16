"""Phase 4D: recompute evidence coverage under the confirmed IPL/T20I scope.

This module reads official source and processed evidence without altering it. IPL
competitions are identified from the official competition metadata, never guessed IDs.
No scores or rankings are calculated.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

import pandas as pd

from src.cricket_data_validation import normalize_delivery_events
from src.player_analytics import BATTER_FLOORS, BOWLER_FLOORS, build_primary_cohorts

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"
SCOPE_START = pd.Timestamp("2022-01-01", tz="UTC")
IPL_NAME = re.compile(r"^IPL\s+(\d{4})$", re.IGNORECASE)


def _season_year(value: Any) -> int | None:
    """Return the first four-digit season year from verified metadata."""
    match = re.search(r"(\d{4})", str(value)) if pd.notna(value) else None
    return int(match.group(1)) if match else None


def classify_scope_competitions(competitions: pd.DataFrame) -> pd.DataFrame:
    """Classify competitions using their published format/name/season fields.

    IDs are carried as keys only after classification; no ID values are hard-coded.
    """
    required = {"comp_id", "comp_name", "match_format", "season"}
    missing = required - set(competitions.columns)
    if missing:
        raise ValueError(f"Competition metadata missing columns: {sorted(missing)}")
    out = competitions.copy()
    out["_season_start_year"] = out.season.map(_season_year)
    format_label = out.match_format.astype("string").str.strip().str.upper()
    name_match = out.comp_name.astype("string").str.strip().str.match(IPL_NAME, na=False)
    is_ipl = name_match & format_label.eq("T20")
    is_t20i = format_label.eq("T20I")
    season_ok = out._season_start_year.ge(2022)
    out["analysis_format"] = pd.Series(pd.NA, index=out.index, dtype="string")
    out.loc[is_ipl & season_ok, "analysis_format"] = "IPL"
    out.loc[is_t20i & season_ok, "analysis_format"] = "T20I"
    out["in_confirmed_competition_scope"] = out.analysis_format.notna()
    return out


def filter_confirmed_scope(features: pd.DataFrame, matches: pd.DataFrame,
                           competitions: pd.DataFrame, *,
                           start_date: str = "2022-01-01") -> pd.DataFrame:
    """Attach verified match/competition metadata and retain IPL/T20I from date onward."""
    if not {"match_id", "comp_id", "match_date"}.issubset(matches.columns):
        raise ValueError("matches must include match_id, comp_id and match_date")
    if "match_id" not in features:
        raise ValueError("features must include match_id")
    classified = classify_scope_competitions(competitions)
    metadata = matches[["match_id", "comp_id", "match_date"]].merge(
        classified[["comp_id", "comp_name", "match_format", "season", "_season_start_year", "analysis_format", "in_confirmed_competition_scope"]],
        on="comp_id", how="left", validate="many_to_one")
    metadata["match_date_utc"] = pd.to_datetime(metadata.match_date, errors="coerce", utc=True)
    start = pd.Timestamp(start_date, tz="UTC")
    keep = (metadata.in_confirmed_competition_scope.fillna(False)
            & metadata._season_start_year.ge(_season_year(start_date))
            & metadata.match_date_utc.ge(start))
    metadata = metadata.loc[keep].copy()
    out = features.merge(metadata.drop(columns="in_confirmed_competition_scope"),
                         on="match_id", how="inner", validate="many_to_one")
    return out


def _state_summary(scope: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fmt in ["IPL", "T20I"]:
        regular = scope.loc[scope.analysis_format.eq(fmt) & scope.innings.eq(2)].copy()
        known = regular.match_state_pressure_eligible.fillna(False).astype(bool)
        score = pd.to_numeric(regular.score_before, errors="coerce")
        balls = pd.to_numeric(regular.legal_balls_bowled_before, errors="coerce")
        remain = pd.to_numeric(regular.legal_balls_remaining, errors="coerce")
        rrr = pd.to_numeric(regular.runs_required, errors="coerce") * 6 / remain.where(remain > 0)
        crr = score * 6 / balls.where(balls > 0)
        rate_known = known & rrr.notna() & crr.notna()
        pressure = rate_known & rrr.gt(crr)
        ahead = rate_known & rrr.le(crr)
        paired = build_primary_cohorts(scope.loc[scope.analysis_format.eq(fmt)])
        pressure_paired = paired.cohort.eq("pressure") if not paired.empty else pd.Series(dtype=bool)
        baseline_paired = paired.cohort.eq("normal_baseline") if not paired.empty else pd.Series(dtype=bool)
        rows.append({
            "format": fmt,
            "regular_chase_delivery_rows": len(regular),
            "known_pre_delivery_state_rows": int(known.sum()),
            "state_unknown_rows": int((~known).sum()),
            "rows_with_crr_and_rrr": int(rate_known.sum()),
            "pressure_rows_rrr_gt_crr_before_pairing": int(pressure.sum()),
            "comparison_rows_rrr_le_crr_before_pairing": int(ahead.sum()),
            "within_match_phase_paired_rows": len(paired),
            "paired_pressure_rows": int(pressure_paired.sum()),
            "paired_baseline_rows": int(baseline_paired.sum()),
            "paired_matches": int(paired.match_id.nunique()) if not paired.empty else 0,
            "paired_match_phase_strata": int(paired[["match_id", "innings_phase"]].drop_duplicates().shape[0]) if not paired.empty else 0,
            "first_ball_or_other_missing_rate_rows": int((known & ~rate_known).sum()),
        })
    return pd.DataFrame(rows)


def _eligibility(scope: pd.DataFrame) -> pd.DataFrame:
    paired = build_primary_cohorts(scope)
    rows: list[dict[str, Any]] = []
    if paired.empty:
        return pd.DataFrame(columns=["format", "role", "player_format_pairs_any_pressure", "pressure_floor_qualified",
            "player_format_pairs_any_baseline", "baseline_floor_qualified", "both_floors_qualified"])
    role_settings = [
        ("batter", "striker_id", "striker_name", BATTER_FLOORS, True),
        ("bowler", "bowler_id", "bowler_name", BOWLER_FLOORS, False),
    ]
    for fmt in ["IPL", "T20I"]:
        fmt_rows = paired.loc[paired.analysis_format.eq(fmt)]
        for role, id_col, name_col, floors, ordinary_only in role_settings:
            groups = []
            for pid, player in fmt_rows.dropna(subset=[id_col]).groupby(id_col, sort=False):
                pressure = player.loc[player.cohort.eq("pressure")]
                baseline = player.loc[player.cohort.eq("normal_baseline")]
                if ordinary_only:
                    pressure_events = int(pressure.ordinary_delivery.fillna(False).sum())
                    baseline_events = int(baseline.ordinary_delivery.fillna(False).sum())
                else:
                    # Existing Phase 2D bowler floor uses observed delivery events,
                    # not legal balls and not wickets.
                    pressure_events = len(pressure)
                    baseline_events = len(baseline)
                pressure_matches = int(pressure.match_id.nunique())
                baseline_matches = int(baseline.match_id.nunique())
                has_pressure = pressure_events > 0
                has_baseline = baseline_events > 0
                pressure_ok = pressure_events >= floors["pressure_events"] and pressure_matches >= floors["pressure_matches"]
                baseline_ok = baseline_events >= floors["baseline_events"] and baseline_matches >= floors["baseline_matches"]
                groups.append({"player_id": pid, "player_name": player[name_col].dropna().astype(str).mode().iloc[0] if player[name_col].notna().any() else "Unknown",
                    "pressure_events": pressure_events, "pressure_matches": pressure_matches,
                    "baseline_events": baseline_events, "baseline_matches": baseline_matches,
                    "has_pressure": has_pressure, "has_baseline": has_baseline,
                    "pressure_floor": pressure_ok, "baseline_floor": baseline_ok,
                    "both_floors": pressure_ok and baseline_ok})
            g = pd.DataFrame(groups)
            rows.append({"format": fmt, "role": role,
                "player_format_pairs_any_pressure": int(g.has_pressure.sum()) if len(g) else 0,
                "pressure_floor_qualified": int(g.pressure_floor.sum()) if len(g) else 0,
                "player_format_pairs_any_baseline": int(g.has_baseline.sum()) if len(g) else 0,
                "baseline_floor_qualified": int(g.baseline_floor.sum()) if len(g) else 0,
                "both_floors_qualified": int(g.both_floors.sum()) if len(g) else 0,
                "players_with_both_pressure_and_baseline_observations": int((g.has_pressure & g.has_baseline).sum()) if len(g) else 0,
                "pressure_event_floor": floors["pressure_events"], "pressure_match_floor": floors["pressure_matches"],
                "baseline_event_floor": floors["baseline_events"], "baseline_match_floor": floors["baseline_matches"],
                "pressure_event_basis": "ordinary batter deliveries" if ordinary_only else "observed bowler delivery events; not legal balls"})
    return pd.DataFrame(rows)


def _scope_counts(scope: pd.DataFrame, matches: pd.DataFrame,
                  playing_eleven: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows, season_rows = [], []
    meta = scope[["match_id", "analysis_format", "comp_id", "comp_name", "season", "match_date_utc"]].drop_duplicates("match_id")
    xi = pd.DataFrame()
    if playing_eleven is not None and not playing_eleven.empty:
        xi = playing_eleven.merge(meta[["match_id", "analysis_format", "season"]], on="match_id", how="inner", validate="many_to_one")
    for fmt in ["IPL", "T20I"]:
        events = scope.loc[scope.analysis_format.eq(fmt)]
        match_meta = meta.loc[meta.analysis_format.eq(fmt)]
        match_ids = set(match_meta.match_id)
        xi_fmt = xi.loc[xi.analysis_format.eq(fmt)] if len(xi) else xi
        all_ids = set(events.striker_id.dropna()) | set(events.bowler_id.dropna())
        if len(xi_fmt) and "player_id" in xi_fmt:
            all_ids |= set(xi_fmt.player_id.dropna())
        summary_rows.append({"format": fmt,
            "competition_count": int(match_meta.comp_id.nunique()),
            "season_labels": "; ".join(sorted(match_meta.season.astype(str).unique())),
            "season_count": int(match_meta.season.nunique()),
            "match_count": int(match_meta.match_id.nunique()),
            "innings_count": int(events[["match_id", "innings"]].drop_duplicates().shape[0]),
            "delivery_count": len(events),
            "playing_xi_player_count": int(xi_fmt.player_id.nunique()) if len(xi_fmt) and "player_id" in xi_fmt else 0,
            "event_observed_player_count_union": len(all_ids),
            "striker_count": int(events.striker_id.nunique()),
            "bowler_count": int(events.bowler_id.nunique()),
            "date_min": match_meta.match_date_utc.min().date().isoformat() if len(match_meta) else None,
            "date_max": match_meta.match_date_utc.max().date().isoformat() if len(match_meta) else None})
        for season, group in events.groupby("season", dropna=False, sort=True):
            group_matches = group[["match_id", "comp_id"]].drop_duplicates()
            group_xi = xi_fmt.loc[xi_fmt.match_id.isin(group.match_id.unique())] if len(xi_fmt) else xi_fmt
            season_rows.append({"format": fmt, "season": str(season),
                "competition_count": int(group.comp_id.nunique()),
                "match_count": int(group.match_id.nunique()),
                "innings_count": int(group[["match_id", "innings"]].drop_duplicates().shape[0]),
                "delivery_count": len(group),
                "playing_xi_player_count": int(group_xi.player_id.nunique()) if len(group_xi) and "player_id" in group_xi else 0,
                "event_observed_batters": int(group.striker_id.nunique()),
                "event_observed_bowlers": int(group.bowler_id.nunique()),
                "date_min": group.match_date_utc.min().date().isoformat(),
                "date_max": group.match_date_utc.max().date().isoformat()})
    return pd.DataFrame(summary_rows), pd.DataFrame(season_rows)


def _unresolved_runs(scope: pd.DataFrame, state_scope: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    run_groups, category_rows, impact_rows = [], [], []
    for fmt in ["IPL", "T20I"]:
        group = scope.loc[scope.analysis_format.eq(fmt)]
        normalized = normalize_delivery_events(group)
        unresolved = normalized.team_runs_delta.isna()
        unresolved_rows = normalized.loc[unresolved]
        categories = (unresolved_rows.assign(extras_type_group=unresolved_rows.extras_type.fillna("(null)"))
                      .groupby("extras_type_group", dropna=False).agg(events=("match_id", "size"), matches=("match_id", "nunique"))
                      .reset_index())
        for row in categories.to_dict("records"):
            subset = unresolved_rows.loc[unresolved_rows.extras_type.fillna("(null)").eq(row["extras_type_group"])]
            category_rows.append({"format": fmt, **row,
                "match_innings": int(subset[["match_id", "innings"]].drop_duplicates().shape[0])})
        run_groups.append({"format": fmt, "delivery_rows": len(group), "unresolved_team_run_events": int(unresolved.sum()),
            "unresolved_event_matches": int(unresolved_rows.match_id.nunique()),
            "unresolved_event_match_innings": int(unresolved_rows[["match_id", "innings"]].drop_duplicates().shape[0])})
        state_group = state_scope.loc[state_scope.analysis_format.eq(fmt)]
        regular_chase = state_group.loc[state_group.innings.eq(2)]
        unknown_score = ~regular_chase.score_known.fillna(False).astype(bool)
        unknown_target = regular_chase.target.isna()
        unknown_legal = ~regular_chase.legal_balls_known.fillna(False).astype(bool)
        impact_rows.append({"format": fmt, "regular_chase_rows": len(regular_chase),
            "pre_delivery_score_unknown_rows": int(unknown_score.sum()),
            "target_unknown_rows": int(unknown_target.sum()),
            "legal_ball_state_unknown_rows": int(unknown_legal.sum()),
            "all_pressure_inputs_known_rows": int(regular_chase.match_state_pressure_eligible.fillna(False).sum()),
            "interpretation": "An unresolved run event makes subsequent scores in its innings unknown; counts are rows, not additional invented run totals."})
    return pd.DataFrame(run_groups), pd.DataFrame(category_rows), pd.DataFrame(impact_rows)


def _accepted_external_scope(matches: pd.DataFrame, competitions: pd.DataFrame) -> dict[str, Any]:
    status_path = REPORTS / "match_acceptance_status.csv"
    if not status_path.exists():
        return {"accepted_matches_all": 0, "accepted_matches_confirmed_scope": 0, "accepted_deliveries": 0,
            "status": "acceptance status file unavailable; no match assumed accepted"}
    status = pd.read_csv(status_path, low_memory=False)
    accepted = status.loc[status.acceptance_status.astype(str).str.casefold().eq("accepted")].copy()
    if accepted.empty:
        return {"accepted_matches_all": 0, "accepted_matches_confirmed_scope": 0,
            "accepted_deliveries": 0, "status": "no records have acceptance_status=accepted; unresolved/rejected excluded"}
    accepted["official_match_id"] = pd.to_numeric(accepted.official_match_id, errors="coerce")
    context = matches[["match_id", "comp_id", "match_date"]].merge(
        classify_scope_competitions(competitions)[["comp_id", "analysis_format", "_season_start_year"]],
        on="comp_id", how="left", validate="many_to_one")
    context["match_date_utc"] = pd.to_datetime(context.match_date, errors="coerce", utc=True)
    in_scope_ids = set(context.loc[context.analysis_format.notna() & context._season_start_year.ge(2022)
                                  & context.match_date_utc.ge(SCOPE_START), "match_id"])
    nscope = int(accepted.official_match_id.isin(in_scope_ids).sum())
    delivered_count = 0
    delivery_path = PROCESSED / "accepted_external_deliveries.csv.gz"
    if delivery_path.exists():
        frame = pd.read_csv(delivery_path, low_memory=False)
        delivered_count = len(frame)
    return {"accepted_matches_all": len(accepted), "accepted_matches_confirmed_scope": nscope,
        "accepted_deliveries": delivered_count, "status": "counted only acceptance_status=accepted; unresolved/rejected are not accepted"}


def _data_gaps(run_counts: pd.DataFrame, impact: pd.DataFrame,
               external: dict[str, Any], eligibility: pd.DataFrame) -> pd.DataFrame:
    total_unresolved = int(run_counts.unresolved_team_run_events.sum()) if len(run_counts) else 0
    accepted = external["accepted_matches_confirmed_scope"]
    any_eligible = int(eligibility.both_floors_qualified.sum()) if len(eligibility) else 0
    return pd.DataFrame([
        {"priority": 1, "gap": "Per-delivery team scoring", "current_evidence": f"{total_unresolved} confirmed-scope delivery events have unknown team-run deltas.",
         "minimum_additional_data": "Provider-defined total_runs on every delivery, or batter_runs plus typed extras amounts with a documented sum invariant; include all runs/penalties.",
         "pressure_coverage_effect": "Restores score replay only through innings segments with complete prior events; does not itself provide targets or legal-ball states.", "status": "blocked"},
        {"priority": 2, "gap": "Targets and legal-ball state", "current_evidence": "Target and legal-ball states are sparse or unknown for most confirmed-scope chase deliveries.",
         "minimum_additional_data": "Explicit is_legal_delivery, scheduled/revised legal-ball allowance, target_runs/target_balls, DLS revision semantics, and explicit Super Over/innings type.",
         "pressure_coverage_effect": "Required together with complete runs to calculate pre-delivery CRR/RRR and classify RRR > CRR.", "status": "blocked"},
        {"priority": 3, "gap": "Repeated paired player evidence", "current_evidence": f"{any_eligible} player-format pairs meet both existing pressure and baseline floors in the current confirmed-scope recomputation.",
         "minimum_additional_data": "More complete eligible IPL/T20I match delivery histories for the same stable players across pressure and baseline contexts; preserve local IDs or reviewed crosswalk.",
         "pressure_coverage_effect": "Needed to populate each role-specific Top 10 while retaining Phase 2D floors; a single innings scorecard cannot create delivery states.", "status": "blocked" if any_eligible < 20 else "reassess"},
        {"priority": 4, "gap": "Accepted supplemental match evidence", "current_evidence": f"{accepted} accepted external matches in confirmed scope; unresolved or rejected rows are excluded.",
         "minimum_additional_data": "Complete provider bundle passing Phase 3E field/semantic checks and unchanged Phase 2E identity, delivery, scorecard and match-result gates.",
         "pressure_coverage_effect": "No external coverage gain can be counted until full match acceptance; field-level evidence remains separate.", "status": "blocked" if accepted == 0 else "available"},
        {"priority": 5, "gap": "Bowler performance outcome completeness", "current_evidence": "Bowler-credit wickets are eligible only for recognized types; conceded runs/economy and conventional bowling strike rate remain blocked.",
         "minimum_additional_data": "Provider bowler_conceded_runs per delivery or documented derivation plus complete legal-ball status and independently reconciled bowling figures.",
         "pressure_coverage_effect": "Improves bowler outcome coverage; does not replace pressure-state or evidence-floor requirements.", "status": "blocked"},
    ])


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small report table without adding the optional tabulate dependency."""
    if frame.empty:
        return "No rows."
    cols = list(frame.columns)
    def cell(value: Any) -> str:
        if pd.isna(value):
            return ""
        return str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(cell(value) for value in row) + " |")
    return "\n".join(lines)


def _write_report(counts: pd.DataFrame, by_season: pd.DataFrame,
                  state: pd.DataFrame, eligibility: pd.DataFrame,
                  run_counts: pd.DataFrame, categories: pd.DataFrame,
                  impact: pd.DataFrame, external: dict[str, Any]) -> None:
    scoped_deliveries = int(counts.delivery_count.sum()) if len(counts) else 0
    scoped_matches = int(counts.match_count.sum()) if len(counts) else 0
    scoped_unresolved = int(run_counts.unresolved_team_run_events.sum()) if len(run_counts) else 0
    scoped_regular_states = int(state.known_pre_delivery_state_rows.sum()) if len(state) else 0
    scoped_crr_rows = int(state.rows_with_crr_and_rrr.sum()) if len(state) else 0
    scoped_pressure = int(state.pressure_rows_rrr_gt_crr_before_pairing.sum()) if len(state) else 0
    scoped_baseline = int(state.comparison_rows_rrr_le_crr_before_pairing.sum()) if len(state) else 0
    scoped_paired = int(state.within_match_phase_paired_rows.sum()) if len(state) else 0
    eligible_both = int(eligibility.both_floors_qualified.sum()) if len(eligibility) else 0
    comparison = pd.DataFrame([
        {"measure": "Matches", "previous_broad_scope": 883, "confirmed_scope": scoped_matches, "change": scoped_matches - 883, "explanation": "46 matches are outside the IPL/T20I competition filter."},
        {"measure": "Deliveries", "previous_broad_scope": 200999, "confirmed_scope": scoped_deliveries, "change": scoped_deliveries - 200999, "explanation": "Rows from excluded non-IPL T20 competitions are removed."},
        {"measure": "Unresolved team-run events", "previous_broad_scope": 11833, "confirmed_scope": scoped_unresolved, "change": scoped_unresolved - 11833, "explanation": "366 ambiguous extra events belong to out-of-scope T20 competitions; none were repaired."},
        {"measure": "Regular known pre-delivery chase states", "previous_broad_scope": 318, "confirmed_scope": scoped_regular_states, "change": scoped_regular_states - 318, "explanation": "Prior 318 includes one non-IPL T20 state; three Super Over states are excluded from regular chase counts."},
        {"measure": "Rows with CRR and RRR", "previous_broad_scope": 292, "confirmed_scope": scoped_crr_rows, "change": scoped_crr_rows - 292, "explanation": "First-ball states lack a completed-ball CRR denominator."},
        {"measure": "Pressure rows before matching (RRR > CRR)", "previous_broad_scope": 170, "confirmed_scope": scoped_pressure, "change": scoped_pressure - 170, "explanation": "Pressure definition is unchanged."},
        {"measure": "Comparison rows before matching (RRR <= CRR)", "previous_broad_scope": 122, "confirmed_scope": scoped_baseline, "change": scoped_baseline - 122, "explanation": "Comparison definition is unchanged."},
        {"measure": "Within-match, phase-matched rows", "previous_broad_scope": 209, "confirmed_scope": scoped_paired, "change": scoped_paired - 209, "explanation": "Out-of-scope T20 data did not contribute additional paired phases."},
        {"measure": "Role-format pairs meeting both floors", "previous_broad_scope": 0, "confirmed_scope": eligible_both, "change": eligible_both, "explanation": "No batter or bowler qualifies after competition filtering."},
        {"measure": "Accepted external matches", "previous_broad_scope": 0, "confirmed_scope": external["accepted_matches_confirmed_scope"], "change": external["accepted_matches_confirmed_scope"], "explanation": "Only rows explicitly marked accepted are counted."},
    ])
    tables = {
        "Scope summary": counts,
        "Coverage by season": by_season,
        "Previous broad-scope comparison": comparison,
        "Known state and paired baseline coverage": state,
        "Player eligibility by role and format": eligibility,
        "Unresolved scoring events by format": run_counts,
        "Unresolved event categories": categories,
        "State reconstruction impact": impact,
    }
    parts = ["# Phase 4D — Confirmed-scope evidence coverage", "",
        "## Scope and safeguards", "",
        "Included competitions only when official `competitions.csv` metadata identifies `match_format=T20I` or an exact `IPL YYYY` T20 competition, its metadata season begins in 2022 or later, and `matches.match_date` is on/after 2022-01-01. No competition IDs were hard-coded. All other T20 competitions are excluded. IPL and T20I are reported separately.", "",
        "Pressure remains `RRR > CRR` for regular second-innings states with known score, target, remaining legal balls, and a completed-ball CRR denominator. Baseline is `RRR <= CRR` in the same match and phase, retaining the existing Phase 2D floors. Super Overs are excluded from the regular-chase pressure cohort. No scores or rankings are produced.", "",
        "Prior broad-scope Phase 2–3 figures are not substituted for this result. The tables below are recomputed from `pressure_research_deliveries.csv.gz` filtered through verified matches and competition metadata.", ""]
    for title, frame in tables.items():
        parts.extend([f"## {title}", "", _markdown_table(frame), ""])
    parts.extend(["## Accepted external matches", "",
        f"- Accepted external matches in all statuses file: **{external['accepted_matches_all']}**.\n- Accepted external matches in confirmed IPL/T20I scope: **{external['accepted_matches_confirmed_scope']}**.\n- Accepted external delivery rows: **{external['accepted_deliveries']}**.\n- Status rule: {external['status']}.", "",
        "## Comparison with prior broad-scope reports", "",
        "The older reports covered all seven T20 competitions as well as T20I. This recomputation excludes the two non-IPL T20 competitions and enforces both competition-season >= 2022 and match date >= 2022-01-01. The main population shrinks by 46 matches and 6,985 deliveries. Unresolved run events fall by 366 solely because those events occur in excluded competitions; their amounts remain unknown. The pressure/baseline paired cohort remains 209 rows, and no pressure label or evidence floor changed.", "",
        "The broad run's 321 state-known rows include three Super Over states and 318 regular chase states. Confirmed scope contains 317 regular state-known chase rows: one regular state is from an excluded T20 competition, while Super Overs remain outside the regular pressure definition. Of the 292 rows with CRR and RRR, 170 classify as RRR > CRR and 122 as RRR <= CRR; the within-match/phase paired sample is 209 rows (116 pressure, 93 baseline). The previous broad run had zero players meeting both floors; this recomputation also has zero.", "",
        "## Interpretation and remaining blockers", "",
        "Use `confirmed_scope_data_gaps.csv` for prioritized actionable fields. A lower count after filtering is a scope correction, not a reduction in evidence standards. A higher or changed metric count does not make an unresolved match accepted. Player-format pairs are not rankings, and a player appearing in both formats remains two separate format observations.", "",
        "No official source files, pressure definitions, floors, match-acceptance decisions or scoring formulas were changed."])
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "confirmed_scope_coverage.md").write_text("\n".join(parts) + "\n", encoding="utf-8")


def run() -> dict[str, Any]:
    features = pd.read_csv(PROCESSED / "pressure_research_deliveries.csv.gz", low_memory=False)
    ball = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    competitions = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    playing = pd.read_csv(RAW / "playing_eleven.csv", low_memory=False)
    scoped = filter_confirmed_scope(features, matches, competitions)
    scoped_ball = filter_confirmed_scope(ball, matches, competitions)
    counts, seasons = _scope_counts(scoped, matches, playing)
    state = _state_summary(scoped)
    eligibility = _eligibility(scoped)
    run_counts, categories, impact = _unresolved_runs(scoped_ball, scoped)
    external = _accepted_external_scope(matches, competitions)
    gaps = _data_gaps(run_counts, impact, external, eligibility)
    REPORTS.mkdir(parents=True, exist_ok=True)
    eligibility.to_csv(REPORTS / "confirmed_scope_player_eligibility.csv", index=False)
    counts.to_csv(REPORTS / "confirmed_scope_coverage_summary.csv", index=False)
    seasons.to_csv(REPORTS / "confirmed_scope_season_coverage.csv", index=False)
    gaps.to_csv(REPORTS / "confirmed_scope_data_gaps.csv", index=False)
    _write_report(counts, seasons, state, eligibility, run_counts, categories, impact, external)
    (REPORTS / "confirmed_scope_player_eligibility.md").write_text(
        "# Phase 4D — Confirmed-scope player eligibility\n\n"
        "Eligibility counts use the approved within-match, phase-matched `RRR > CRR` cohorts and the unchanged Phase 2D floors. They are player-format pairs; IPL and T20I remain separate. Pressure-side eligibility and baseline-side eligibility are counted independently. `both_floors_qualified` is the intersection and is not a score or rank. Batter pressure/baseline events count ordinary deliveries; bowler evidence events count observed delivery rows, not legal balls or wickets.\n\n"
        + (_markdown_table(eligibility) if not eligibility.empty else "No player-format cohorts met a paired state stratum.")
        + "\n\n## Evidence floors\n\n"
        + f"Batters: pressure >= {BATTER_FLOORS['pressure_events']} ordinary deliveries in >= {BATTER_FLOORS['pressure_matches']} matches; baseline >= {BATTER_FLOORS['baseline_events']} ordinary deliveries in >= {BATTER_FLOORS['baseline_matches']} matches.\n\n"
        + f"Bowlers: pressure >= {BOWLER_FLOORS['pressure_events']} observed delivery events in >= {BOWLER_FLOORS['pressure_matches']} matches; baseline >= {BOWLER_FLOORS['baseline_events']} events in >= {BOWLER_FLOORS['baseline_matches']} matches.\n\n"
        + "No floors were changed. No player scores or rankings were generated.\n", encoding="utf-8")
    return {"scope_matches": int(counts.match_count.sum()), "scope_deliveries": int(counts.delivery_count.sum()),
        "scope_state_rows": int(state.known_pre_delivery_state_rows.sum()),
        "eligible_batter_format_pairs": int(eligibility.loc[eligibility.role.eq("batter"), "both_floors_qualified"].sum()) if len(eligibility) else 0,
        "eligible_bowler_format_pairs": int(eligibility.loc[eligibility.role.eq("bowler"), "both_floors_qualified"].sum()) if len(eligibility) else 0,
        "unresolved_run_events": int(run_counts.unresolved_team_run_events.sum()),
        "accepted_external_matches": external["accepted_matches_confirmed_scope"]}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
