"""Phase 3C pressure-state coverage opportunities and data-gap quantification."""
from __future__ import annotations

from pathlib import Path
import json
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
PROCESSED = ROOT / "data" / "processed"
EXTERNAL_MATCHES = ROOT / "data" / "external" / "cricsheet" / "pilot" / "matches"


def paired_state_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return known regular chase states and phase-paired pressure/baseline rows."""
    f = frame.copy()
    f["score_before"] = pd.to_numeric(f.score_before, errors="coerce")
    f["legal_balls_remaining"] = pd.to_numeric(f.legal_balls_remaining, errors="coerce")
    f["legal_balls_bowled_before"] = pd.to_numeric(f.legal_balls_bowled_before, errors="coerce")
    f["runs_required"] = pd.to_numeric(f.runs_required, errors="coerce")
    f["rrr"] = 6 * f.runs_required / f.legal_balls_remaining.where(f.legal_balls_remaining > 0)
    f["crr"] = 6 * f.score_before / f.legal_balls_bowled_before.where(f.legal_balls_bowled_before > 0)
    valid = (f.analysis_format.isin(["IPL", "T20I"]) & pd.to_numeric(f.innings, errors="coerce").eq(2)
             & f.match_state_pressure_eligible.fillna(False) & f.innings_phase.notna()
             & f.rrr.notna() & f.crr.notna())
    f = f.loc[valid].copy()
    f["pressure_class"] = f.rrr.gt(f.crr).map({True: "pressure", False: "baseline"})
    strata = f.groupby(["match_id", "innings_phase"], dropna=False).pressure_class.nunique()
    pair_keys = strata[strata.eq(2)].reset_index()[["match_id", "innings_phase"]]
    return f.merge(pair_keys, on=["match_id", "innings_phase"], how="inner", validate="many_to_one")


def cricsheet_chase_states(payload: dict) -> pd.DataFrame:
    """Build candidate pre-delivery RRR/CRR states from a Cricsheet JSON match.

    This function is research-only. Its output is not eligible for the accepted
    layer until every Phase 2E gate passes.
    """
    innings = payload.get("innings", [])
    if len(innings) < 2:
        return pd.DataFrame()
    first = innings[0]
    first_deliveries = [d for over in first.get("overs", []) for d in over.get("deliveries", [])]
    first_total = sum(int(d.get("runs", {}).get("total", 0) or 0) for d in first_deliveries)
    penalties = first.get("penalty_runs", {}) or {}
    first_total += int(penalties.get("pre", 0) or 0) + int(penalties.get("post", 0) or 0)
    chase = innings[1]
    if chase.get("super_over", False):
        return pd.DataFrame()
    target_info = chase.get("target", {}) or {}
    target = target_info.get("runs")
    if target is None:
        target = first_total + 1
    overs = target_info.get("overs") or payload.get("info", {}).get("overs")
    if target is None or overs is None:
        return pd.DataFrame()
    try:
        target, ball_limit = int(target), int(round(float(overs) * 6))
    except (TypeError, ValueError):
        return pd.DataFrame()
    score = legal_balls = 0
    records = []
    for over in chase.get("overs", []):
        over_number = int(over.get("over", 0)) + 1
        phase = "powerplay (overs 1-6)" if over_number <= 6 else "middle (overs 7-15)" if over_number <= 15 else "death (overs 16-20)"
        for position, delivery in enumerate(over.get("deliveries", []), start=1):
            remaining = ball_limit - legal_balls
            if remaining > 0 and legal_balls > 0:
                runs_required = target - score
                rrr = runs_required * 6 / remaining
                crr = score * 6 / legal_balls
                records.append({"innings": 2, "over": over_number, "delivery_position": position,
                    "phase": phase, "score_before": score, "target": target,
                    "runs_required": runs_required, "legal_balls_remaining": remaining,
                    "current_run_rate": crr, "required_run_rate": rrr,
                    "pressure_class": "pressure" if rrr > crr else "baseline"})
            extras = delivery.get("extras", {}) or {}
            total = delivery.get("runs", {}).get("total", 0)
            score += int(total or 0)
            if not int(extras.get("wides", 0) or 0) and not int(extras.get("noballs", 0) or 0):
                legal_balls += 1
    out = pd.DataFrame(records)
    if out.empty:
        return out
    strata = out.groupby("phase").pressure_class.nunique()
    paired = set(strata[strata.eq(2)].index)
    out["phase_paired"] = out.phase.isin(paired)
    return out


def _profile_context() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(PROCESSED / "pressure_research_deliveries.csv.gz", low_memory=False)
    matches = pd.read_csv(ROOT / "data" / "raw" / "matches.csv")
    comps = pd.read_csv(ROOT / "data" / "raw" / "competitions.csv")
    comp = comps[["comp_id", "match_format", "comp_name", "season"]]
    context = matches[["match_id", "comp_id", "match_date", "home_team", "away_team", "revised_target"]].merge(comp, on="comp_id", how="left", validate="many_to_one")
    f = features.merge(context, on="match_id", how="left", validate="many_to_one")
    f["analysis_format"] = pd.NA
    is_ipl = f.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False)
    f.loc[is_ipl, "analysis_format"] = "IPL"
    f.loc[f.match_format.eq("T20I"), "analysis_format"] = "T20I"
    return f, matches, comps


def _player_minimum_matches(exposure: pd.DataFrame) -> pd.DataFrame:
    """Optimistic extra-match lower bounds using observed per-match event yields."""
    rows = []
    for (role, fmt), g in exposure.groupby(["role", "format"], sort=True):
        if role == "batter":
            pf, pm, bf, bm = 2, 2, 16, 3
            pe_col, be_col = "pressure_evidence_events_for_phase2d_floor", "baseline_evidence_events_for_phase2d_floor"
        else:
            pf, pm, bf, bm = 5, 2, 37, 2
            pe_col, be_col = "pressure_evidence_events_for_phase2d_floor", "baseline_evidence_events_for_phase2d_floor"
        pp = g[pe_col] / g.pressure_matches.replace(0, pd.NA)
        bp = g[be_col] / g.baseline_matches.replace(0, pd.NA)
        typical_p = float(pp.dropna().median()) if pp.notna().any() else 0.0
        typical_b = float(bp.dropna().median()) if bp.notna().any() else 0.0
        need = []
        for r in g.itertuples(index=False):
            p_match_deficit = max(0, pm - int(r.pressure_matches))
            b_match_deficit = max(0, bm - int(r.baseline_matches))
            p_event_deficit = max(0, pf - int(getattr(r, pe_col)))
            b_event_deficit = max(0, bf - int(getattr(r, be_col)))
            p_event_matches = math.ceil(p_event_deficit / typical_p) if typical_p > 0 else (1 if p_event_deficit else 0)
            b_event_matches = math.ceil(b_event_deficit / typical_b) if typical_b > 0 else (1 if b_event_deficit else 0)
            # One future match may contribute to both cohorts for a player only if
            # their observations include both classes in a paired phase.
            need.append(max(p_match_deficit, b_match_deficit, p_event_matches, b_event_matches))
        rows.append({"role": role, "format": fmt, "observed_player_format_pairs": len(g),
            "pressure_floor_events": pf, "pressure_floor_matches": pm,
            "baseline_floor_events": bf, "baseline_floor_matches": bm,
            "median_pressure_events_per_pressure_match": round(typical_p, 3),
            "median_baseline_events_per_baseline_match": round(typical_b, 3),
            "minimum_additional_matches_lower_bound_median": int(pd.Series(need).median()) if need else 0,
            "minimum_additional_matches_lower_bound_q75": int(math.ceil(pd.Series(need).quantile(.75))) if need else 0,
            "pairs_already_meeting_all_floors": int(g.sufficient_evidence_for_future_pressure_comparison.sum()),
            "assumption": "optimistic floor-only lower bound: each added verified match features the same player in paired pressure/baseline contexts and yields the observed median events per context; not a guarantee"})
    return pd.DataFrame(rows)


def build_gap_tables(features: pd.DataFrame, matches: pd.DataFrame, comps: pd.DataFrame,
                     exposure: pd.DataFrame, candidate_rows: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    paired = paired_state_rows(features)
    summaries = []
    current = features.loc[features.analysis_format.isin(["IPL", "T20I"])].copy()
    for fmt in ("IPL", "T20I"):
        g = current.loc[current.analysis_format.eq(fmt)]
        regular_known = g.loc[(pd.to_numeric(g.innings, errors="coerce").eq(2)) & g.match_state_pressure_eligible.fillna(False)].copy()
        chase_rows = g.loc[pd.to_numeric(g.innings, errors="coerce").eq(2)].copy()
        regular_known["legal_balls_bowled"] = pd.to_numeric(regular_known.legal_balls_bowled_before, errors="coerce")
        rrr = pd.to_numeric(regular_known.runs_required, errors="coerce") * 6 / pd.to_numeric(regular_known.legal_balls_remaining, errors="coerce")
        crr = pd.to_numeric(regular_known.score_before, errors="coerce") * 6 / regular_known.legal_balls_bowled.where(regular_known.legal_balls_bowled > 0)
        pressure_mask = rrr.gt(crr) & crr.notna()
        baseline_mask = rrr.le(crr) & crr.notna()
        pg = paired.loc[paired.analysis_format.eq(fmt)]
        p_paired = int(pg.pressure_class.eq("pressure").sum())
        b_paired = int(pg.pressure_class.eq("baseline").sum())
        p_matches = int(pg.loc[pg.pressure_class.eq("pressure"), "match_id"].nunique())
        b_matches = int(pg.loc[pg.pressure_class.eq("baseline"), "match_id"].nunique())
        match_ids_with_rows = set(g.match_id.dropna().unique())
        missing = matches.loc[~matches.match_id.isin(features.match_id.unique())].merge(comps[["comp_id", "match_format", "comp_name"]], on="comp_id", how="left")
        missing_ipl = missing.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False)
        missing_count = int((missing_ipl if fmt == "IPL" else missing.match_format.eq("T20I")).sum())
        diagnostic = {"regular_chase_source_rows": len(chase_rows),
            "score_state_known_rows": int(chase_rows.score_known.fillna(False).sum()),
            "target_known_rows": int(chase_rows.target.notna().sum()),
            "legal_ball_state_known_rows": int(chase_rows.legal_balls_known.fillna(False).sum()),
            "all_required_state_inputs_known_rows": int(chase_rows.match_state_pressure_eligible.fillna(False).sum())}
        summaries.extend([
            {"format": fmt, "opportunity": "current_known_regular_chase_state", "current_rows": int(len(regular_known)), "pressure_rows": int(pressure_mask.sum()), "baseline_rows": int(baseline_mask.sum()), "matches_represented": int(regular_known.match_id.nunique()), "additional_rows_conditional": 0, "additional_pressure_rows_conditional": 0, "additional_baseline_rows_conditional": 0, "additional_matches_conditional": 0, "evidence_status": "official local reconstruction; known only"},
            {"format": fmt, "opportunity": "primary_within_match_phase_paired", "current_rows": len(pg), "pressure_rows": p_paired, "baseline_rows": b_paired, "matches_represented": int(pg.match_id.nunique()), "additional_rows_conditional": 0, "additional_pressure_rows_conditional": 0, "additional_baseline_rows_conditional": 0, "additional_matches_conditional": 0, "evidence_status": "official local known states; approved primary baseline design"},
            {"format": fmt, "opportunity": "local_matches_without_delivery_rows", "current_rows": 0, "pressure_rows": 0, "baseline_rows": 0, "matches_represented": 0, "additional_rows_conditional": "unknown", "additional_pressure_rows_conditional": "unknown", "additional_baseline_rows_conditional": "unknown", "additional_matches_conditional": missing_count, "evidence_status": "16 total matches have no local deliveries; 0 recovered in Phase 2F pilot; current Cricsheet match-index candidates unresolved"},
            {"format": fmt, "opportunity": "accepted_external_layer", "current_rows": 0, "pressure_rows": 0, "baseline_rows": 0, "matches_represented": 0, "additional_rows_conditional": 0, "additional_pressure_rows_conditional": 0, "additional_baseline_rows_conditional": 0, "additional_matches_conditional": 0, "evidence_status": "0 Phase 2E matches accepted; validated coverage gain is zero"},
        ])
        summaries[-4].update(diagnostic)
    # Conditional candidate comparison for the four downloaded controls.
    candidate_detail = candidate_rows
    for fmt in ("IPL", "T20I"):
        cg = candidate_detail.loc[candidate_detail.format.eq(fmt)] if not candidate_detail.empty else candidate_detail
        summaries.append({"format": fmt, "opportunity": "four_control_cricsheet_candidates_if_fully_accepted", "current_rows": int(cg.current_known_state_rows.sum()) if len(cg) else 0,
            "pressure_rows": int(cg.candidate_paired_pressure_rows.sum()) if len(cg) else 0,
            "baseline_rows": int(cg.candidate_paired_baseline_rows.sum()) if len(cg) else 0,
            "matches_represented": int(cg.official_match_id.nunique()) if len(cg) else 0,
            "additional_rows_conditional": int(cg.additional_state_rows.sum()) if len(cg) else 0,
            "additional_pressure_rows_conditional": int(cg.additional_paired_pressure_rows.sum()) if len(cg) else 0,
            "additional_baseline_rows_conditional": int(cg.additional_paired_baseline_rows.sum()) if len(cg) else 0,
            "additional_matches_conditional": 0,
            "evidence_status": "unaccepted Cricsheet candidate only; research ceiling if every Phase 2E gate later passes"})
    opportunities = pd.DataFrame(summaries)
    requirements = _player_minimum_matches(exposure)
    metadata = {"paired": paired, "requirements": requirements, "current_format_state_counts": current.groupby("analysis_format").match_state_pressure_eligible.sum().to_dict()}
    return opportunities, requirements, metadata


def _cricsheet_candidates(features: pd.DataFrame, matches: pd.DataFrame, comps: pd.DataFrame) -> pd.DataFrame:
    rec_path = REPORTS / "match_reconciliation.csv"
    if not rec_path.is_file():
        return pd.DataFrame()
    rec = pd.read_csv(rec_path, low_memory=False)
    f = features.copy()
    f["format"] = pd.NA
    f.loc[f.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False), "format"] = "IPL"
    f.loc[f.match_format.eq("T20I"), "format"] = "T20I"
    local = f.copy()
    local["position"] = local.groupby(["match_id", "innings", "overid"], sort=False).cumcount() + 1
    rows = []
    for r in rec.loc[rec.pilot_role.eq("control")].itertuples(index=False):
        path = EXTERNAL_MATCHES / str(r.external_filename)
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        cand = cricsheet_chase_states(payload)
        if cand.empty:
            continue
        lg = local.loc[(local.match_id.eq(r.official_match_id)) & pd.to_numeric(local.innings, errors="coerce").eq(2)].copy()
        # candidate phase rows are paired within match/phase only; unpaired states do not count.
        cand = cand.loc[cand.phase_paired].copy()
        local_key = lg.set_index(["innings", "overid", "position"])
        known_coords, known_classes = set(), {}
        for key, row in local_key.iterrows():
            if bool(row.match_state_pressure_eligible):
                known_coords.add(key)
                score = float(row.score_before)
                balls = float(row.legal_balls_bowled_before)
                if balls > 0 and float(row.legal_balls_remaining) > 0:
                    cls = "pressure" if float(row.runs_required) * 6 / float(row.legal_balls_remaining) > score * 6 / balls else "baseline"
                    known_classes[key] = cls
        cand["coordinate"] = list(zip(cand.innings, cand.over, cand.delivery_position))
        added = ~cand.coordinate.isin(known_coords)
        agree = 0
        for cr in cand.loc[~added].itertuples(index=False):
            if known_classes.get(cr.coordinate) == cr.pressure_class:
                agree += 1
        rows.append({"official_match_id": r.official_match_id, "format": "IPL" if str(r.competition).startswith("IPL") else str(r.format),
            "candidate_state_rows": len(cand), "candidate_paired_pressure_rows": int(cand.pressure_class.eq("pressure").sum()),
            "candidate_paired_baseline_rows": int(cand.pressure_class.eq("baseline").sum()),
            "current_known_state_rows": len(known_coords), "additional_state_rows": int(added.sum()),
            "additional_paired_pressure_rows": int((added & cand.pressure_class.eq("pressure")).sum()),
            "additional_paired_baseline_rows": int((added & cand.pressure_class.eq("baseline")).sum()),
            "candidate_rows_overlapping_current_known": int((~added).sum()), "known_state_pressure_class_agreements": agree,
            "acceptance_status": str(getattr(r, "acceptance_status", "unresolved")), "not_accepted": True})
    return pd.DataFrame(rows)


def _requirements_report(requirements: pd.DataFrame) -> pd.DataFrame:
    records = [
        ("Verified total runs per delivery", "score_before cannot continue after unresolved extras; local runs is batter-run candidate only", "per-delivery team total or documented batter/extras amounts by type", "Pressure-state reconstruction", "Highest: fixes cascading score-state loss in existing innings", "High, if provider documentation plus independent reconciliation"),
        ("Verified legal-delivery flag per event", "266 local events unresolved; Overstep semantics are inferred", "provider-defined is_legal_delivery including Overstep/other/penalty and revised ball limit", "Required/current/remaining run rates and over position", "High for state completeness and bowling exposure", "Medium; simple feed field but needs taxonomy validation"),
        ("Target and revised innings allowance", "revised_target is sparse; target often depends on first-innings total; DLS and super overs special", "innings target, revised target, target overs/balls, DLS/par context, innings type", "Required run rate and comparable regular chase states", "High where target is otherwise missing", "Medium; scorecards can supply final target but not per-ball scores"),
        ("Full innings totals and outcome status", "only 18/1,724 innings have known final scores; matches.csv result is not a score", "independent innings total, wickets, all out/declared/abandoned status, DLS/SO designation", "Target checks and end-state validation", "Medium; enables validation but cannot alone reconstruct pre-ball score", "Medium, scorecards are accessible but formats/coverage vary"),
        ("Accepted event-level external delivery records", "4 Cricsheet control JSONs downloaded; 0 accepted; 16 missing-local candidates unresolved in index", "match identity, typed extras, total runs, legal balls, target, player/venue identity and independent scorecard gates", "Would recover complete state in matched accepted matches", "Potentially high per match; current validated gain is zero", "High implementation/reconciliation cost; ODC-BY attribution and separate storage required"),
        ("Authoritative local player-ID namespace/crosswalk", "official player IDs do not map to Cricsheet registry IDs; candidates are not accepted", "provider ID namespace or auditable official ID mapping with team/season context", "Player-level pressure and baseline exposure by correct player", "Essential for player comparison; cannot create delivery-state coverage", "High benefit, moderate research cost; names-only joins risky"),
        ("Verified venue ID/name dimension", "official venue IDs are opaque; all pilot venue maps unresolved/candidate", "authoritative venue_id-to-venue identity and history", "Match identity acceptance and venue-stratified analysis", "Unblocks acceptance but not scoring by itself", "Moderate; relatively focused lookup, risks venue renaming/neutral grounds"),
        ("Independent bowling figures and player identity", "bowler-conceded runs absent; only 8/8 detailed-control innings corroborated for candidates", "bowler runs conceded, legal balls, bowler-credit wickets and player crosswalk", "Economy and comparable bowler outcome validation", "Essential for reliable bowler analysis", "High; complete player scorecards/source mappings needed"),
    ]
    return pd.DataFrame(records, columns=["requirement", "current_gap", "minimum_additional_fields_or_evidence", "unlocks", "expected_coverage_effect", "acquisition_cost_and_risk"])


def _report(opportunities: pd.DataFrame, requirements: pd.DataFrame, min_matches: pd.DataFrame,
            features: pd.DataFrame, candidates: pd.DataFrame) -> str:
    format_rows = opportunities.loc[opportunities.opportunity.isin(["current_known_regular_chase_state", "primary_within_match_phase_paired", "local_matches_without_delivery_rows", "accepted_external_layer"])]
    def md(df: pd.DataFrame) -> str:
        cols = list(df.columns)
        lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
        for row in df.fillna("").astype(str).itertuples(index=False, name=None):
            lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in row) + " |")
        return "\n".join(lines)
    current_all = int(features.match_state_pressure_eligible.fillna(False).sum())
    format_states = format_rows.loc[format_rows.opportunity.eq("current_known_regular_chase_state")]
    paired_rows = format_rows.loc[format_rows.opportunity.eq("primary_within_match_phase_paired")]
    pilot_add = int(candidates.additional_state_rows.sum()) if len(candidates) else 0
    format_table = []
    for r in format_states.itertuples(index=False):
        p = paired_rows.loc[paired_rows.format.eq(r.format)]
        format_table.append(f"| {r.format} | {r.current_rows} | {r.pressure_rows} | {r.baseline_rows} | {int(p.current_rows.iloc[0]) if len(p) else 0} | {int(p.pressure_rows.iloc[0]) if len(p) else 0} | {int(p.baseline_rows.iloc[0]) if len(p) else 0} | {int(p.matches_represented.iloc[0]) if len(p) else 0} |")
    diag_rows = []
    for r in format_states.itertuples(index=False):
        diag_rows.append(f"| {r.format} | {r.regular_chase_source_rows} | {r.score_state_known_rows} | {r.target_known_rows} | {r.legal_ball_state_known_rows} | {r.all_required_state_inputs_known_rows} |")
    return f'''# Phase 3C — Pressure evidence expansion and data gap analysis

## Findings

There are **{current_all}** rows with reconstructed score, target, runs required and remaining legal balls, including super-over rows that are excluded from regulation chase analysis. Phase 2C's 321 consists of 318 regular chase states plus 3 Super Over states. The format-specific comparison below is IPL and T20I only; one regular T20 state belongs to a non-IPL T20 competition and is excluded from these two format views. The regular second-innings subset contains **{int(format_states.current_rows.sum())}** IPL/T20I states. Of these, **{int(format_states.pressure_rows.sum())}** have an observed current run rate and classify as `RRR > CRR`, and **{int(format_states.baseline_rows.sum())}** classify as at/ahead. The rest include first-ball states where CRR has no completed-ball denominator. Under the approved within-match/phase pairing, only **{int(paired_rows.current_rows.sum())}** states remain ({int(paired_rows.pressure_rows.sum())} pressure and {int(paired_rows.baseline_rows.sum())} baseline).

The 321 figure is not a failure to detect late-over pressure. It is the consequence of the state engine's conservative propagation: `runs` is only a batter-run candidate; `extras1_runs` is category-coded; `extras_2_runs` is undocumented; and 11,833 source events have unresolved team-run amounts. After an unresolved score event, later pre-delivery scores in that innings remain unknown. Missing innings totals also prevent deriving targets for many chases. A further 266 events have unresolved legal status, with `Overstep` inferred rather than documented. The 16 matches with no local delivery rows have no local state stream at all.

## Format-specific current and conditional coverage

| Format | Current known chase states | Pressure | Baseline | Phase/within-match paired rows | Paired pressure | Paired baseline | Paired matches |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(format_table)}

State-input diagnostic for all local second-innings deliveries in these formats:

| Format | Source chase rows | Score known | Target known | Legal-ball state known | All pressure-state inputs known |
|---|---:|---:|---:|---:|---:|
{chr(10).join(diag_rows)}

All four downloaded Cricsheet controls are still unresolved under Phase 2E: **zero accepted matches** and **zero validated coverage gain**. Research-only replay of their explicit delivery totals, legal-ball events and target fields would conditionally expose **{pilot_add} additional aligned state rows** in the paired pressure/baseline comparison, if every mandatory identity, scoring, wicket, target and independent-scorecard gate passes. Candidate rows and pressure/baseline counts are separately itemized by match and format in `pressure_coverage_opportunities.csv`; they are not imported or accepted. The 16 missing-local-delivery candidates remain unresolved: the Phase 2F index lookup returned no unique candidate for any of them, but did not establish confirmed archive absence.

No safe additional pressure or baseline rows can be created from local final scores or match result text alone. A scorecard can establish an innings total, target, DLS revision, wickets and bowling figures; without the score after each delivery, it cannot recover per-delivery CRR/RRR classes. Cricsheet's documented JSON has `runs.batter`, `runs.extras`, `runs.total`, typed extras, targets and delivery events, and is structurally suitable for a candidate replay. Its records remain external until reconciled and accepted. The four controls show why a complete data record matters: all align on batter runs, but player IDs, venues, local extras, totals/targets and some event semantics still block acceptance.

## Minimum additional verified matches

The attached estimates retain Phase 2D Q1 floors: batters 2 pressure events in 2 matches plus 16 baseline events in 3 matches; bowlers 5 pressure events in 2 matches plus 37 baseline events in 2 matches. The table uses current player-format exposure and median eligible events per pressure/baseline match to calculate an **optimistic lower bound** on new verified matches. It assumes each new match features that same player in both cohorts and supplies the observed median event yield; real opportunities will require more matches because a player may not appear in a paired phase or state class. This is a floor estimate, not an evidence-threshold change or a promise of eligibility.

{md(min_matches)}

No player currently meets both cohort floors in either format. One accepted match may improve state coverage but usually cannot establish repeated pressure and baseline exposure for many players; meaningful comparisons require repeated accepted matches with resolved player IDs and enough same-player paired observations.

## Data sources and acquisition economics

Official IPL match centres expose scorecards with innings totals, overs, wickets and match context (example [official IPL scorecard, MI v KKR, 3 May 2024](https://www.iplt20.com/matches/2fa5b412-b823-4e31-8e22-00b3e3e5f5e0/More/scorecard)). Such scorecards are relatively low-cost evidence for final totals/targets and bowling figures, but cannot alone yield delivery-by-delivery states. The [Cricsheet JSON format documentation](https://cricsheet.org/format/json/) defines batter, extras and total runs, typed extras, wicket events, and targets; the [Cricsheet downloads page](https://cricsheet.org/downloads/) provides match archives under its stated data terms. This source is high-value for state reconstruction but carries substantial reconciliation cost: match identity, player namespace, venue identity, scorecard checks, DLS/Super Over treatment and ODC-BY attribution must all be handled. The existing pilot's 0 accepted of 4 controls means its current validated benefit remains zero.

| Data option | Expected gain | Acquisition/processing cost | Main risk | Recommendation |
|---|---|---|---|---|
| Provider data dictionary plus complete per-delivery total/legality fields | Highest across all existing local rows; resolves state after extras | Low-to-moderate request; moderate validation | Documentation may not cover historic changes | First priority |
| Official scorecards for known-state sample and controls | Final totals, targets, bowling-figure checks; not delivery state by itself | Low per match, manual for archive | Scorecard coverage/layout varies; source may omit typed extras | Acquire as validation evidence, not as a substitute for ball data |
| Reconcile the four downloaded Cricsheet controls | Conditional recovery for some state rows in four matches | Moderate/high manual crosswalk and adjudication | 0/4 accepted; candidate data can disagree in extras/identity | Complete only after local ID/venue namespace evidence is available |
| Expand Cricsheet to 16 no-row candidates | Could restore entire match event streams if records exist | Search/download plus full acceptance per match | Current index has no unique candidate for all 16; archive absence unresolved | Check current index and archive before investing in manual reconciliation |

## Primary data requirements

`additional_data_requirements.csv` lists each blocker and minimum field request. Highest-impact fields are: (1) documented `total_runs` per delivery and typed extras; (2) provider-defined legal-ball flag and revised ball allowance; (3) innings target/revised target/target overs plus outcome status; (4) authoritative player-ID namespace/crosswalk; and (5) venue-ID crosswalk. Match acceptance criteria are unchanged, and every external match remains provisional until all mandatory checks pass.

The strongest expected coverage gain per unit cost is obtaining a provider definition plus per-delivery total-run and legal-ball fields for the official rows already present. That could restore state after unresolved events without substituting final scores for delivery history. For missing 16 matches, next query a current complete Cricsheet match index; only then decide whether to invest in event-level reconciliation.

No pressure definition, match-acceptance gate or evidence threshold was modified. No player scores or rankings were generated.
'''


def generate() -> dict[str, int]:
    features, matches, comps = _profile_context()
    exposure = pd.read_csv(REPORTS / "player_exposure_summary.csv")
    candidates = _cricsheet_candidates(features, matches, comps)
    opportunities, requirements, _ = build_gap_tables(features, matches, comps, exposure, candidates)
    # Include format-specific lower-bound estimates in opportunity artifact too.
    min_matches = _player_minimum_matches(exposure)
    req = _requirements_report(requirements)
    opportunity_out = opportunities.copy()
    opportunity_out = pd.concat([opportunity_out, min_matches.assign(opportunity="minimum_additional_verified_matches_floor", current_rows=pd.NA,
        pressure_rows=pd.NA, baseline_rows=pd.NA, matches_represented=pd.NA, additional_rows_conditional=pd.NA,
        additional_pressure_rows_conditional=pd.NA, additional_baseline_rows_conditional=pd.NA,
        additional_matches_conditional=min_matches.minimum_additional_matches_lower_bound_median,
        evidence_status=min_matches.assumption)], ignore_index=True, sort=False)
    if len(candidates):
        detailed = candidates.assign(opportunity="four_control_cricsheet_candidate_detail",
            current_rows=candidates.current_known_state_rows,
            pressure_rows=candidates.candidate_paired_pressure_rows,
            baseline_rows=candidates.candidate_paired_baseline_rows,
            matches_represented=1,
            additional_rows_conditional=candidates.additional_state_rows,
            additional_pressure_rows_conditional=candidates.additional_paired_pressure_rows,
            additional_baseline_rows_conditional=candidates.additional_paired_baseline_rows,
            additional_matches_conditional=0,
            evidence_status="conditional only; match remains unaccepted under Phase 2E")
        opportunity_out = pd.concat([opportunity_out, detailed], ignore_index=True, sort=False)
    opportunity_out.to_csv(REPORTS / "pressure_coverage_opportunities.csv", index=False)
    req.to_csv(REPORTS / "additional_data_requirements.csv", index=False)
    (REPORTS / "pressure_evidence_gap_analysis.md").write_text(_report(opportunities, req, min_matches, features, candidates), encoding="utf-8")
    return {"all_state_eligible_rows": int(features.match_state_pressure_eligible.fillna(False).sum()),
        "regular_chase_rows": int(opportunities.loc[opportunities.opportunity.eq("current_known_regular_chase_state"), "current_rows"].sum()),
        "candidate_controls": len(candidates), "candidate_additional_rows": int(candidates.additional_state_rows.sum()) if len(candidates) else 0,
        "accepted_external_matches": 0, "opportunity_rows": len(opportunity_out), "requirement_rows": len(req)}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
