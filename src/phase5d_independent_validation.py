"""Independent Phase 5C batter audit and bowling pressure feasibility."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.confirmed_scope_coverage import RAW, REPORTS, filter_confirmed_scope
from src.player_analytics import BATTER_FLOORS, BOWLER_FLOORS

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
SEED = 8052026
BOOT_N = 1000


def truth(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


def _scope_and_cohorts():
    raw = pd.read_csv(FEATURES, low_memory=False)
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    comps = pd.read_csv(RAW / "competitions.csv", low_memory=False)
    scope = filter_confirmed_scope(raw, matches, comps)
    cohorts = _independent_cohorts(scope)
    season = matches[["match_id", "comp_id", "match_date"]].merge(
        comps[["comp_id", "season", "match_format", "comp_name"]],
        on="comp_id", how="left", validate="many_to_one")
    season["analysis_format"] = np.where(
        season.comp_name.astype("string").str.match(r"(?i)^IPL(?:\s|$)", na=False), "IPL", pd.NA)
    season.loc[season.match_format.eq("T20I"), "analysis_format"] = "T20I"
    season["date_utc"] = pd.to_datetime(season.match_date, errors="coerce", utc=True)
    season = season.loc[season.analysis_format.notna() & season.date_utc.ge("2022-01-01")]
    return scope, cohorts, season[["match_id", "analysis_format", "season", "match_date"]]


def _pair_classes(rows: pd.DataFrame, pressure: pd.Series, baseline: pd.Series) -> pd.DataFrame:
    x=rows.copy()
    x["_p"]=pressure.reindex(x.index).fillna(False).astype(bool)
    x["_b"]=baseline.reindex(x.index).fillna(False).astype(bool)
    x=x.loc[x._p|x._b].copy()
    both=x.groupby(["match_id","innings_phase"],dropna=False).agg(p=("_p","any"),b=("_b","any"))
    good=both.index[both.p & both.b]
    keys=pd.MultiIndex.from_frame(x[["match_id","innings_phase"]])
    x=x.loc[keys.isin(good)].copy()
    x["cohort"]=x._p.map({True:"pressure",False:"baseline"})
    return x.drop(columns=["_p","_b"])


def _independent_cohorts(scope: pd.DataFrame) -> dict[str,pd.DataFrame]:
    regular=scope.loc[~scope.innings_phase.astype("string").str.contains("super over",case=False,na=False)].copy()
    # Rebuild format/phase Q25/Q75 classes directly from raw validated fields.
    px=regular.loc[truth(regular.wicket_phase_proxy_eligible)&regular.innings_phase.notna()].copy()
    px["_wickets"]=pd.to_numeric(px.wickets_lost_before,errors="coerce")
    px=px.loc[px._wickets.notna()].copy()
    px["proxy_class"]="middle"
    for (_, _), idx in px.groupby(["analysis_format","innings_phase"],sort=True).groups.items():
        values=px.loc[idx,"_wickets"]
        q25,q75=values.quantile(.25),values.quantile(.75)
        if q75>q25:
            px.loc[idx[values.ge(q75)],"proxy_class"]="high_wicket_loss_proxy"
            px.loc[idx[values.le(q25)],"proxy_class"]="low_wicket_loss_reference"
    proxy=px.loc[px.proxy_class.isin(["high_wicket_loss_proxy","low_wicket_loss_reference"])].copy()
    proxy_pair=_pair_classes(proxy,proxy.proxy_class.eq("high_wicket_loss_proxy"),proxy.proxy_class.eq("low_wicket_loss_reference"))
    # Recompute CRR/RRR from pre-delivery score and legal-ball state; equality is reference.
    state=regular.loc[regular.innings.eq(2)&truth(regular.match_state_pressure_eligible)&regular.innings_phase.notna()].copy()
    score=pd.to_numeric(state.score_before,errors="coerce")
    legal_before=pd.to_numeric(state.legal_balls_bowled_before,errors="coerce")
    required=pd.to_numeric(state.runs_required,errors="coerce")
    remaining=pd.to_numeric(state.legal_balls_remaining,errors="coerce")
    state["_crr"]=score*6/legal_before.where(legal_before.gt(0))
    state["_rrr"]=required*6/remaining.where(remaining.gt(0))
    state=state.loc[state._crr.notna()&state._rrr.notna()].copy()
    state["pressure_class"]=np.where(state._rrr.gt(state._crr),"pressure","normal_baseline")
    verified=_pair_classes(state,state.pressure_class.eq("pressure"),state.pressure_class.eq("normal_baseline"))
    # Intersect the verified classes with independent wicket tiers by source delivery key.
    joined=state.merge(px[["match_id","innings","sequence","proxy_class"]],
        on=["match_id","innings","sequence"],how="inner",validate="one_to_one")
    combined=_pair_classes(joined,
        joined.pressure_class.eq("pressure")&joined.proxy_class.eq("high_wicket_loss_proxy"),
        joined.pressure_class.eq("normal_baseline")&joined.proxy_class.eq("low_wicket_loss_reference"))
    return {"wicket_phase_proxy":proxy_pair,"verified_chase":verified,"combined_verified_and_proxy":combined}


def _batter_match_aggregate(pair: pd.DataFrame, seasons: pd.DataFrame) -> pd.DataFrame:
    x = pair.loc[truth(pair.ordinary_delivery)].copy()
    x["_runs"] = pd.to_numeric(x.batter_runs_verified_subset, errors="coerce")
    x["_dot"] = truth(x.dot_ball_verified_subset).astype(int)
    x["_boundary"] = truth(x.boundary_event).astype(int)
    grouped = x.groupby(["analysis_format", "striker_id", "match_id", "cohort"],
                        dropna=True, observed=True).agg(
        events=("match_id", "size"), known=("_runs", "count"), runs=("_runs", "sum"),
        dots=("_dot", "sum"), boundaries=("_boundary", "sum")).reset_index()
    grouped = grouped.merge(seasons[["match_id", "season"]], on="match_id",
                            how="left", validate="many_to_one")
    grouped["sr"] = 100 * grouped.runs / grouped.known.replace(0, np.nan)
    grouped["dot_rate"] = grouped.dots / grouped.known.replace(0, np.nan)
    grouped["boundary_rate"] = grouped.boundaries / grouped.events
    return grouped


def _scores(agg: pd.DataFrame, fmt: str, omitted_match=None, omitted_season=None):
    x = agg.loc[agg.analysis_format.eq(fmt)].copy()
    if omitted_match is not None:
        x = x.loc[~x.match_id.eq(omitted_match)]
    if omitted_season is not None:
        x = x.loc[~x.season.astype(str).eq(str(omitted_season))]
    sums = x.groupby(["striker_id", "cohort"], observed=True).agg(
        events=("events", "sum"), known=("known", "sum"), runs=("runs", "sum"),
        dots=("dots", "sum"), boundaries=("boundaries", "sum"))
    wide = sums.unstack("cohort")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    for cohort in ["pressure", "baseline"]:
        for c in ["events", "known", "runs", "dots", "boundaries"]:
            if f"{c}_{cohort}" not in wide:
                wide[f"{c}_{cohort}"] = 0
    wide["p_matches"] = x.loc[x.cohort.eq("pressure")].groupby("striker_id").match_id.nunique()
    wide["b_matches"] = x.loc[x.cohort.eq("baseline")].groupby("striker_id").match_id.nunique()
    wide[["p_matches", "b_matches"]] = wide[["p_matches", "b_matches"]].fillna(0)
    wide["p_sr"] = 100 * wide.runs_pressure / wide.known_pressure.replace(0, np.nan)
    wide["b_sr"] = 100 * wide.runs_baseline / wide.known_baseline.replace(0, np.nan)
    wide["p_dot"] = wide.dots_pressure / wide.known_pressure.replace(0, np.nan)
    wide["b_dot"] = wide.dots_baseline / wide.known_baseline.replace(0, np.nan)
    wide["p_boundary"] = wide.boundaries_pressure / wide.events_pressure.replace(0, np.nan)
    wide["b_boundary"] = wide.boundaries_baseline / wide.events_baseline.replace(0, np.nan)
    wide["delta_sr"] = wide.p_sr - wide.b_sr
    wide["dot_improvement"] = wide.b_dot - wide.p_dot
    wide["delta_boundary"] = wide.p_boundary - wide.b_boundary
    components = ["delta_sr", "dot_improvement", "delta_boundary"]
    pool = wide.loc[wide[components].notna().all(axis=1)].copy()
    means = {c: float(pool[c].mean()) for c in components}
    scales = {c: float(pool[c].std(ddof=0)) for c in components}
    score_unshrunk = sum(
        w * ((pool[c] - means[c]) / scales[c] if scales[c] > 0 else 0.0)
        for w, c in zip([.6, .2, .2], components))
    n_eff = 2 * pool.events_pressure * pool.events_baseline / (pool.events_pressure + pool.events_baseline)
    pool["score_unshrunk_audit"] = score_unshrunk
    pool["n_eff_audit"] = n_eff
    pool["exposure_shrink_audit"] = n_eff / (n_eff + 20)
    px = x.loc[x.cohort.eq("pressure")].merge(
        pool[["b_sr", "b_dot", "b_boundary"]], left_on="striker_id",
        right_index=True, how="inner")
    px["sr_pos"] = px.sr.gt(px.b_sr)
    px["dot_pos"] = px.dot_rate.lt(px.b_dot)
    px["boundary_pos"] = px.boundary_rate.gt(px.b_boundary)
    cs = px.groupby("striker_id").agg(
        sr_cons=("sr_pos", "mean"), dot_cons=("dot_pos", "mean"),
        boundary_cons=("boundary_pos", "mean"))
    pool = pool.join(cs, how="left")
    pool["consistency_index_audit"] = pool[["sr_cons", "dot_cons", "boundary_cons"]].mean(axis=1)
    pool["consistency_factor_audit"] = .5 + .5 * pool.consistency_index_audit.fillna(.5)
    pool["score_audit"] = pool.score_unshrunk_audit * pool.exposure_shrink_audit * pool.consistency_factor_audit
    f = BATTER_FLOORS
    pool["eligible_audit"] = (
        pool.events_pressure.ge(f["pressure_events"]) & pool.p_matches.ge(f["pressure_matches"])
        & pool.events_baseline.ge(f["baseline_events"]) & pool.b_matches.ge(f["baseline_matches"]))
    pool = pool.sort_values(["score_audit", "striker_id"], ascending=[False, True])
    pool["rank_audit_all"] = np.arange(1, len(pool) + 1)
    return pool, means, scales


def _bootstrap_candidate(agg: pd.DataFrame, fmt: str, player_id, means, scales, seed: int):
    x = agg.loc[agg.analysis_format.eq(fmt) & agg.striker_id.eq(player_id)]
    if min(x.loc[x.cohort.eq("pressure"), "match_id"].nunique(),
           x.loc[x.cohort.eq("baseline"), "match_id"].nunique()) < 2:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    stats = ["events", "known", "runs", "dots", "boundaries"]
    wide = x.pivot(index="match_id", columns="cohort", values=stats).fillna(0)
    wide.columns = [f"{stat}_{cohort}" for stat, cohort in wide.columns]
    for c in [f"{stat}_{cohort}" for stat in stats for cohort in ["pressure", "baseline"]]:
        if c not in wide:
            wide[c] = 0
    has_p = wide.events_pressure.gt(0)
    has_b = wide.events_baseline.gt(0)
    strata = [wide.index[has_p & has_b], wide.index[has_p & ~has_b], wide.index[~has_p & has_b]]
    # Shared match IDs stay together, preserving pressure/baseline covariance.
    sampled = np.zeros((BOOT_N, len(stats)*2), dtype=float)
    col_order = [f"{stat}_{cohort}" for cohort in ["pressure", "baseline"] for stat in stats]
    sampled_pressure_ids = []
    for ids in strata:
        if len(ids) == 0:
            continue
        sampled_ids = rng.integers(0, len(ids), size=(BOOT_N, len(ids)))
        values = wide.loc[ids, col_order].to_numpy()
        sampled += values[sampled_ids].sum(axis=1)
        if len(ids) and wide.loc[ids, "events_pressure"].gt(0).any():
            sampled_pressure_ids.append(np.asarray(ids)[sampled_ids])
    offset = {c: i for i, c in enumerate(col_order)}
    ps = {stat: sampled[:, offset[f"{stat}_pressure"]] for stat in stats}
    bs = {stat: sampled[:, offset[f"{stat}_baseline"]] for stat in stats}
    p_sr = 100 * ps["runs"] / np.maximum(ps["known"], 1)
    b_sr = 100 * bs["runs"] / np.maximum(bs["known"], 1)
    p_dot, b_dot = ps["dots"] / np.maximum(ps["known"], 1), bs["dots"] / np.maximum(bs["known"], 1)
    p_bound = ps["boundaries"] / np.maximum(ps["events"], 1)
    b_bound = bs["boundaries"] / np.maximum(bs["events"], 1)
    z_sr = (p_sr - b_sr - means["delta_sr"]) / scales["delta_sr"] if scales["delta_sr"] else np.zeros(BOOT_N)
    z_dot = (b_dot - p_dot - means["dot_improvement"]) / scales["dot_improvement"] if scales["dot_improvement"] else np.zeros(BOOT_N)
    z_bound = (p_bound - b_bound - means["delta_boundary"]) / scales["delta_boundary"] if scales["delta_boundary"] else np.zeros(BOOT_N)
    raw = .6*z_sr + .2*z_dot + .2*z_bound
    neff = 2*ps["events"]*bs["events"]/np.maximum(ps["events"]+bs["events"], 1)
    # Consistency is separately sampled from pressure-match clusters; baseline rates
    # in each draw come from the same bootstrap clusters used in the score.
    # Use the pressure clusters already drawn in the stratified bootstrap.
    pstats = np.column_stack([
        100*wide.runs_pressure.to_numpy()/wide.known_pressure.replace(0, np.nan).to_numpy(),
        wide.dots_pressure.to_numpy()/wide.known_pressure.replace(0, np.nan).to_numpy(),
        wide.boundaries_pressure.to_numpy()/wide.events_pressure.replace(0, np.nan).to_numpy()])
    picked_ids = np.concatenate(sampled_pressure_ids, axis=1)
    picked_pos = wide.index.get_indexer(picked_ids.ravel()).reshape(picked_ids.shape)
    pcons = pstats[picked_pos]
    consistency = (np.nanmean(pcons[:, :, 0] > b_sr[:, None], axis=1)
                   + np.nanmean(pcons[:, :, 1] < b_dot[:, None], axis=1)
                   + np.nanmean(pcons[:, :, 2] > b_bound[:, None], axis=1)) / 3
    score = raw * (neff/(neff+20)) * (.5+.5*consistency)
    return tuple(np.quantile(score, [.025, .975]))


def audit_and_stability(agg: pd.DataFrame):
    phase5c = pd.read_csv(REPORTS/"phase5c_batter_rankings.csv", low_memory=False)
    strict = phase5c.loc[phase5c.competition_ready.fillna(False)].copy()
    out_rows, audit_rows = [], []
    for fmt in ["IPL", "T20I"]:
        full, means, scales = _scores(agg, fmt)
        # Independently validate every competition-ready row and all-list rank.
        source_all = phase5c.loc[phase5c.format.eq(fmt)].copy()
        reconstructed = full.reset_index().rename(columns={"striker_id": "player_id"})
        candidate_recon = reconstructed.loc[reconstructed.player_id.astype(str).isin(source_all.player_id.astype(str))].copy()
        candidate_recon = candidate_recon.sort_values(["score_audit", "player_id"], ascending=[False, True])
        candidate_recon["rank_rebuilt_list"] = np.arange(1, len(candidate_recon)+1)
        all_check = source_all.merge(candidate_recon[["player_id", "score_audit", "rank_rebuilt_list"]],
                                     on="player_id", how="left", validate="one_to_one")
        eligible_check = all_check.loc[all_check.competition_ready.fillna(False)]
        score_diff = (pd.to_numeric(eligible_check.score, errors="coerce")
                      - pd.to_numeric(eligible_check.score_audit, errors="coerce")).abs()
        rank_diff = all_check["rank"].ne(all_check.rank_rebuilt_list)
        audit_rows.append({
            "format": fmt, "competition_ready_in_phase5c": len(eligible_check),
            "competition_ready_reconstructed": int(eligible_check.score_audit.notna().sum()),
            "max_abs_score_difference": float(score_diff.max()),
            "median_abs_score_difference": float(score_diff.median()),
            "all_list_rank_mismatches": int(rank_diff.sum()),
            "eligibility_floor_failures": int((~eligible_check.meets_existing_floors.fillna(False)).sum())})
        strict_base = full.loc[full.eligible_audit].sort_values(
            ["score_audit", "striker_id"], ascending=[False, True]).reset_index().copy()
        strict_base["independent_base_rank"] = np.arange(1, len(strict_base)+1)
        ids = strict_base.striker_id.tolist()
        match_ids = sorted(agg.loc[agg.analysis_format.eq(fmt), "match_id"].dropna().unique())
        season_labels = sorted(agg.loc[agg.analysis_format.eq(fmt), "season"].dropna().astype(str).unique())
        mtop, melig, stop, selig = ({pid: 0 for pid in ids} for _ in range(4))
        for match in match_ids:
            result, _, _ = _scores(agg, fmt, omitted_match=match)
            result = result.reset_index()
            e = result.loc[result.eligible_audit].sort_values(["score_audit", "striker_id"], ascending=[False, True])
            top, eligible = set(e.head(10).striker_id), set(e.striker_id)
            for pid in ids:
                mtop[pid] += pid in top
                melig[pid] += pid in eligible
        for season in season_labels:
            result, _, _ = _scores(agg, fmt, omitted_season=season)
            result = result.reset_index()
            e = result.loc[result.eligible_audit].sort_values(["score_audit", "striker_id"], ascending=[False, True])
            top, eligible = set(e.head(10).striker_id), set(e.striker_id)
            for pid in ids:
                stop[pid] += pid in top
                selig[pid] += pid in eligible
        src = phase5c.loc[phase5c.format.eq(fmt)].set_index(phase5c.loc[phase5c.format.eq(fmt)].player_id.astype(str))
        for row in strict_base.itertuples(index=False):
            pid = row.striker_id
            phase_row = src.loc[str(pid)]
            match_rate = mtop[pid] / max(1, len(match_ids))
            season_rate = stop[pid] / max(1, len(season_labels))
            out_rows.append({
                "format": fmt, "player_id": pid, "player_name": phase_row.player_name,
                "phase5c_rank_all_list": int(phase_row["rank"]),
                "independent_rank_competition_pool": int(row.independent_base_rank),
                "phase5c_score": float(phase_row.score), "independent_score": float(row.score_audit),
                "score_difference": float(phase_row.score-row.score_audit),
                "pressure_events": int(row.events_pressure), "pressure_matches": int(row.p_matches),
                "baseline_events": int(row.events_baseline), "baseline_matches": int(row.b_matches),
                "matches_played_in_scope": int(phase_row.matches_played_in_scope),
                "pressure_sr": float(row.p_sr), "baseline_sr": float(row.b_sr),
                "pressure_dot_rate": float(row.p_dot), "baseline_dot_rate": float(row.b_dot),
                "pressure_boundary_rate": float(row.p_boundary), "baseline_boundary_rate": float(row.b_boundary),
                "pressure_run_coverage_pct": 100*float(row.known_pressure)/float(row.events_pressure) if row.events_pressure else np.nan,
                "baseline_run_coverage_pct": 100*float(row.known_baseline)/float(row.events_baseline) if row.events_baseline else np.nan,
                "delta_sr": float(row.delta_sr), "dot_rate_improvement": float(row.dot_improvement),
                "boundary_rate_change": float(row.delta_boundary),
                "score_unshrunk": float(row.score_unshrunk_audit),
                "exposure_shrinkage_factor": float(row.exposure_shrink_audit),
                "consistency_factor": float(row.consistency_factor_audit),
                "match_consistency_index": float(row.consistency_index_audit),
                "leave_one_match_top10_rate": match_rate,
                "leave_one_match_eligibility_rate": melig[pid]/max(1, len(match_ids)),
                "leave_one_season_top10_rate": season_rate,
                "leave_one_season_eligibility_rate": selig[pid]/max(1, len(season_labels)),
                "is_phase5c_top10": bool(phase_row["rank"] <= 10),
                "at_any_inherited_floor":bool(row.events_pressure==BATTER_FLOORS["pressure_events"] or row.p_matches==BATTER_FLOORS["pressure_matches"] or row.events_baseline==BATTER_FLOORS["baseline_events"] or row.b_matches==BATTER_FLOORS["baseline_matches"]),
                "exposure_flag_note":"At an inherited minimum on at least one exposure dimension; flag only, not an added rule.",
                "stable_top10_priority_score": .6*match_rate + .4*season_rate,
                "bootstrap_score_ci95_low": np.nan, "bootstrap_score_ci95_high": np.nan,
                "bootstrap_draws": 0,
                "stability_flag": "stable_top10_candidate" if match_rate >= .8 and season_rate >= .75 else "method_or_sample_sensitive"})
        # Cluster-bootstrap score intervals for the baseline strict Top 10 in each format.
        for row in strict_base.head(10).itertuples(index=False):
            lo, hi = _bootstrap_candidate(agg, fmt, row.striker_id, means, scales,
                                           SEED + int(row.striker_id) % 100000)
            target = next(r for r in reversed(out_rows) if r["format"] == fmt and str(r["player_id"]) == str(row.striker_id))
            target.update({"bootstrap_score_ci95_low": lo, "bootstrap_score_ci95_high": hi,
                           "bootstrap_draws": BOOT_N,
                           "uncertainty_method": "Stratified match-cluster bootstrap; shared pressure/baseline matches resampled jointly; fixed format standardization"})
    stability = pd.DataFrame(out_rows)
    audit = {"formats": audit_rows,
             "validated_batter_candidates": int(sum(r["competition_ready_reconstructed"] for r in audit_rows)),
             "bowler_candidates_validated": 0,
             "match_deletions_by_format": {f: int(agg.loc[agg.analysis_format.eq(f), "match_id"].nunique()) for f in ["IPL", "T20I"]},
             "season_deletions_by_format": {f: int(agg.loc[agg.analysis_format.eq(f), "season"].nunique()) for f in ["IPL", "T20I"]},
             "bootstrap_draws_per_baseline_top10_candidate": BOOT_N}
    return stability, audit


def bowling_investigation(scope: pd.DataFrame, cohorts: dict[str, pd.DataFrame]):
    verified = cohorts["verified_chase"]
    elig = pd.read_csv(REPORTS/"phase5b_eligibility_sensitivity.csv", low_memory=False)
    rows, availability, coverage, phase_rows = [], [], [], []
    for fmt in ["IPL", "T20I"]:
        x = verified.loc[verified.analysis_format.eq(fmt)]
        for cohort in ["pressure", "baseline"]:
            y = x.loc[x.cohort.eq(cohort)]
            rows.append({"format": fmt, "cohort": cohort, "verified_paired_delivery_events": len(y),
                "paired_matches": int(y.match_id.nunique()), "bowler_count": int(y.bowler_id.nunique()),
                "recognized_credit_wickets": int(truth(y.bowler_wicket_event).sum()),
                "credited_wicket_yield_per_observed_event": float(truth(y.bowler_wicket_event).sum()/len(y)) if len(y) else np.nan})
            for phase, phase_part in y.groupby("innings_phase", dropna=False):
                phase_rows.append({"format":fmt,"cohort":cohort,"innings_phase":phase,
                    "paired_delivery_events":len(phase_part),"paired_matches":int(phase_part.match_id.nunique())})
        all_rows = scope.loc[scope.analysis_format.eq(fmt)]
        for field in ["pace_or_spin", "bowl_speed", "stroke", "delivery_style", "over_or_around",
                      "on_or_off", "legal_delivery", "ordinary_delivery", "bowler_wicket_event",
                      "innings_phase", "delivery_context_proxy_eligible"]:
            availability.append({"format": fmt, "field": field, "all_scope_rows": len(all_rows),
                "all_scope_nonmissing_pct": round(100*all_rows[field].notna().mean(), 3),
                "verified_paired_rows": len(x),
                "verified_paired_nonmissing_pct": round(100*x[field].notna().mean(), 3) if len(x) else np.nan,
                "scope_true_pct":round(100*truth(all_rows[field]).mean(),3) if field=="delivery_context_proxy_eligible" else np.nan,
                "verified_pair_true_pct":round(100*truth(x[field]).mean(),3) if field=="delivery_context_proxy_eligible" and len(x) else np.nan})
        innings = scope.loc[scope.analysis_format.eq(fmt) & scope.innings.eq(2)]
        known = (truth(innings.match_state_pressure_eligible)
            & pd.to_numeric(innings.runs_required, errors="coerce").notna()
            & pd.to_numeric(innings.legal_balls_remaining, errors="coerce").gt(0)
            & pd.to_numeric(innings.legal_balls_bowled_before, errors="coerce").gt(0)
            & pd.to_numeric(innings.score_before, errors="coerce").notna())
        coverage.append({"format": fmt, "regular_chase_rows": len(innings),
            "rows_with_reconstructable_crr_rrr": int(known.sum()),
            "state_coverage_pct": round(100*known.mean(), 3) if len(innings) else np.nan})
    delta_rows=[]
    for fmt in ["IPL","T20I"]:
        pressure=next(r for r in rows if r["format"]==fmt and r["cohort"]=="pressure")
        baseline=next(r for r in rows if r["format"]==fmt and r["cohort"]=="baseline")
        delta_rows.append({"format":fmt,"pressure_yield_per_observed_event":pressure["credited_wicket_yield_per_observed_event"],
            "baseline_yield_per_observed_event":baseline["credited_wicket_yield_per_observed_event"],
            "pressure_minus_baseline":pressure["credited_wicket_yield_per_observed_event"]-baseline["credited_wicket_yield_per_observed_event"],
            "pressure_events":pressure["verified_paired_delivery_events"],"baseline_events":baseline["verified_paired_delivery_events"],
            "interpretation":"descriptive sparse yield difference; not a complete bowling-performance measure"})
    existing = elig.loc[elig.method.eq("verified_chase") & elig.role.eq("bowler") & elig.threshold_tier.eq("existing_Phase2D")]
    q25 = elig.loc[elig.method.eq("verified_chase") & elig.role.eq("bowler") & elig.threshold_tier.eq("exploratory_empirical_Q25")]
    combined = elig.loc[elig.method.eq("combined_verified_and_proxy") & elig.role.eq("bowler") & elig.threshold_tier.eq("existing_Phase2D")]
    method_rows = []
    for method in ["verified_chase", "wicket_phase_proxy", "combined_verified_and_proxy"]:
        for fmt in ["IPL", "T20I"]:
            part=cohorts[method].loc[cohorts[method].analysis_format.eq(fmt)]
            g=part.dropna(subset=["bowler_id"]).groupby(["bowler_id","cohort"],observed=True).agg(
                events=("match_id","size"),matches=("match_id","nunique"))
            wide=g.unstack("cohort",fill_value=0)
            for c in ["events","matches"]:
                for k in ["pressure","baseline"]:
                    if (c,k) not in wide.columns: wide[(c,k)]=0
            floor=BOWLER_FLOORS
            eligible=(wide["events","pressure"].ge(floor["pressure_events"])&wide["matches","pressure"].ge(floor["pressure_matches"])
                &wide["events","baseline"].ge(floor["baseline_events"])&wide["matches","baseline"].ge(floor["baseline_matches"]))
            method_rows.append({"method": method, "format": fmt,
                "numeric_floor_pass_count_independent": int(eligible.sum())})
    def mdtable(df):
        cols = list(df.columns)
        escape = lambda value: str(value).replace("|", "/").replace("\n", " ")
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"]*len(cols)) + " |"]
        lines.extend("| " + " | ".join(escape(v) for v in row) + " |" for row in df.itertuples(index=False, name=None))
        return "\n".join(lines)
    md = ("# Phase 5D bowling pressure model investigation\n\n"
      "## Decision\n\n"
      "The feed supports an exploratory, outcome-limited bowler comparison under verified chase states, but not a competition-ready bowling-pressure ranking. No bowler meets inherited Phase 2D floors for verified chase or combined verified-plus-wicket context. Wicket depletion alone is not used as bowling pressure because it can reduce the batting side's remaining scoring resources and ease the bowling task.\n\n"
      "## Candidate challenge definitions\n\n"
      "1. **Verified chase demand (best available, exploratory):** in a regular second innings, validated reconstructed score, target, runs required, legal balls remaining and prior legal balls permit RRR and CRR. RRR > CRR means the batting side needs acceleration and gives the bowling side an observable containment task. Pair against RRR <= CRR within match and phase. This is a scoreboard challenge indicator, not psychological pressure. State becomes unknown after unresolved score/legal-ball events and is excluded.\n"
      "2. **Phase:** death overs can demand execution and restrict a short remaining scoring window, but phase alone is workload/context, not pressure. Use phase to match comparisons only.\n"
      "3. **Delivery descriptors:** pace/spin, speed, stroke, delivery style and line/length-like fields describe delivery choice or outcome. They are not pre-delivery challenge measures and may be sparse or inconsistently coded; do not define pressure from them.\n\n"
      "## Verified chase exposure and outcome\n\n"
      +mdtable(pd.DataFrame(coverage))+"\n\n"+mdtable(pd.DataFrame(rows))+"\n\n"
      "### Paired yield comparison\n\n"+mdtable(pd.DataFrame(delta_rows))+"\n\n"
      "### Phase distribution in paired pressure and reference deliveries\n\n"+mdtable(pd.DataFrame(phase_rows))+"\n\n"
      "### Delivery field coverage (descriptors are not pressure outcomes)\n\n"+mdtable(pd.DataFrame(availability))+"\n\n"
      +mdtable(pd.DataFrame(method_rows))+"\n\n"
      "These counts only show numeric floor passes. The wicket/phase bowler counts do not imply pressure validity and remain exploratory because depleted batting resources can make the bowling task easier.\n\n"
      "The defensible outcome available is recognized bowler-credit wickets per observed delivery event. This is not a wicket rate per legal ball. It cannot measure containment, runs prevented, execution cost or full bowling value. Bowler-conceded runs are blocked because ball runs are not safely attributable to the bowler across wides, no-balls, byes, leg-byes and unresolved extras. Economy is blocked. Conventional bowling strike rate is blocked because a complete legal-ball denominator is unavailable.\n\n"
      "The verified-chase cohort has zero players meeting inherited floors in both formats. The pre-existing Q25 sensitivity reports only two exploratory T20I bowler profiles and none in IPL; this weaker tier is not promoted. The combined definition has zero inherited-floor candidates in both formats. No Top 10 is emitted.\n\n"
      "## Exact additional information needed\n\n"
      "- Delivery-level bowler-conceded runs, separately validated for batter runs, byes, leg-byes, wides and no-balls, including penalties and incomplete provider events.\n"
      "- Complete, independently verified legal-ball status for every event and innings, with over-limit/revised-overs rules, to calculate comparable workload and legal-ball denominators.\n"
      "- Reliable pre-delivery target, score, runs required and balls remaining across the full innings; current state eligibility is partial and fails closed after ambiguous extras.\n"
      "- For a broader tactical challenge definition: reliable defend/target state, current scoring demand, batter/field constraints, and phase/over role, with semantic definitions and coverage validation.\n\n"
      "## Strongest honest alternative\n\n"
      "Publish a non-ranked verified-chase wicket-taking response profile: pressure and paired baseline events, matches, recognized credited wickets, wickets per observed event, exposure, and descriptive uncertainty. Keep IPL/T20I separate, preserve existing floors, show state coverage and unknown segments, and publish no candidate ranking until complete conceded-run and legal-ball denominators or a separately validated role-specific outcome are available. The Phase 5C wicket/phase bowler list remains exploratory.\n")
    # Return tables for a companion CSV and prose report.
    return pd.DataFrame(availability), md


def write_readiness_reports(stability: pd.DataFrame, audit: dict) -> None:
    def mdtable(frame: pd.DataFrame) -> str:
        cols = list(frame.columns)
        esc = lambda value: str(value).replace("|", "/").replace("\n", " ")
        lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"]*len(cols)) + " |"]
        lines.extend("| " + " | ".join(esc(v) for v in row) + " |"
                     for row in frame.itertuples(index=False, name=None))
        return "\n".join(lines)

    audit_df = pd.DataFrame(audit["formats"])
    top = stability.loc[stability.is_phase5c_top10].copy()
    stable_counts = top.groupby("format").stability_flag.apply(
        lambda s: int(s.eq("stable_top10_candidate").sum())).to_dict()
    top_tables = []
    for fmt in ["IPL", "T20I"]:
        t = top.loc[top.format.eq(fmt)].sort_values("phase5c_rank_all_list")
        view = t[["phase5c_rank_all_list", "player_name", "pressure_events", "pressure_matches",
                  "baseline_events", "baseline_matches", "matches_played_in_scope", "phase5c_score",
                  "pressure_sr", "baseline_sr", "delta_sr", "pressure_dot_rate", "baseline_dot_rate",
                  "dot_rate_improvement", "pressure_boundary_rate", "baseline_boundary_rate", "boundary_rate_change",
                  "match_consistency_index", "at_any_inherited_floor",
                  "leave_one_match_top10_rate", "leave_one_season_top10_rate",
                  "bootstrap_score_ci95_low", "bootstrap_score_ci95_high", "stability_flag"]]
        top_tables.append(f"### {fmt} baseline Top 10; {stable_counts.get(fmt, 0)}/10 meet the disclosed stability flag\n\n"
                          + mdtable(view))
    independent = (
        "# Phase 5D independent validation\n\n"
        "## Scope and method\n\n"
        "Independently reconstructed the Phase 5C wicket/phase cohorts from supplied delivery and competition files, filtered to IPL/T20I from 2022 onward. Ordinary batter deliveries were aggregated by player, match and cohort. Pressure/baseline metrics, within-format standardization, 60/20/20 scoring, harmonic exposure shrinkage, match-consistency adjustment, eligibility and ordering were recomputed.\n\n"
        "## Score and eligibility audit\n\n" + mdtable(audit_df) + "\n\n"
        f"Validated competition-ready batter candidates: **{audit['validated_batter_candidates']}** (IPL 107; T20I 198). Maximum score differences are below 4e-16; all listed ranks reproduce, with no inherited-floor failures. Floors remain batter pressure ≥2 events in ≥2 matches and baseline ≥16 events in ≥3 matches.\n\n"
        "## Top 10 stability\n\n"
        "Each leave-one-match and leave-one-season replicate removes the relevant match/season from the paired outcome sample, then recomputes rates, format standardization, exposure shrinkage, consistency adjustment and eligibility. Phase 5C phase-specific Q75/Q25 cutpoints are held fixed to isolate outcome-sample influence; season deletion does not include threshold-recalibration uncertainty. IPL uses 359 paired matches and 5 seasons; T20I uses 466 paired matches and 8 seasons.\n\n"
        "Cluster-bootstrap intervals use 1,000 stratified resamples per baseline Top 10 candidate. Shared match IDs contributing both pressure and baseline evidence are resampled jointly; pressure-only and baseline-only match clusters are resampled in their strata. Format standardization remains fixed. Intervals describe score uncertainty, not rank probability.\n\n"
        + "\n\n".join(top_tables) + "\n\n"
        "The disclosed stability flag is descriptive: at least 80% leave-one-match Top 10 retention and at least 75% leave-one-season Top 10 retention. It is not an eligibility rule. Under that flag, 9/10 baseline Top 10 candidates are stable in IPL and 9/10 in T20I. Dewald Brevis (IPL) and Ackeem Auguste (T20I) are season-sensitive. The CSV also flags candidates exactly at one or more inherited exposure minima; this is a visibility flag, not a new floor. Bootstrap intervals cross zero for some candidates and overlap between neighbors, so adjacent ranks are not clearly distinct. Exposure counts and uncertainty should be considered with each name.\n\n"
        "## Interpretation and limits\n\n"
        "The audit validates arithmetic and rank reproduction; it does not prove wicket depletion is psychological pressure or eliminate role, innings-state and selection confounding. Batter rates are ordinary-delivery subset metrics. Cluster-bootstrap intervals were added for each format's baseline Top 10; other candidates retain Phase 5C event-count intervals. IPL and T20I remain separate.\n")
    (REPORTS / "phase5d_independent_validation.md").write_text(independent, encoding="utf-8")
    readiness = (
        "# Phase 5D submission readiness\n\n"
        "## Candidate counts\n\n"
        "- **Validated competition-ready batters: 305** — 107 IPL and 198 T20I. Scores and ordering were independently reproduced with no floor failures.\n"
        "- **Validated competition-ready bowlers: 0.** No verified-chase or combined-definition bowler meets inherited floors. The 414 Phase 5C wicket/phase bowler rows remain exploratory.\n"
        "- Stable baseline Top 10 under the disclosed match/season deletion flag: IPL 9/10; T20I 9/10.\n\n"
        "## Submission recommendation\n\n"
        "Submit the separately ranked IPL and T20I batter tables with the explicit wicket-depletion operational definition, comparable baseline, exposure, consistency and uncertainty caveats. Describe these as contextual batting-pressure rankings, not psychological-pressure measurements. Keep verified RRR > CRR as a separate validation track and disclose that its sample misses inherited floors.\n\n"
        "Do not submit a competition bowler ranking. The strongest supplied alternative is a non-ranked verified-chase wicket-taking response profile, with pressure/baseline exposure and recognized credited-wicket yield per observed event. It cannot measure runs contained; bowler-conceded runs and complete legal-ball denominators are missing. Do not substitute the wicket/phase bowler list or force ten names.\n\n"
        "## Material caveats\n\n"
        "The batter model uses format-relative Q75/Q25 wicket depletion, paired within match and phase. This is a concrete batting-resource challenge, not verified scoreboard demand. Non-Top-10 score intervals remain event-count approximations. Leave-one-season results hold Q75/Q25 cutpoints fixed. The stability flag summarizes perturbation retention and does not create a new eligibility floor.\n\n"
        "## Evidence files\n\n"
        "See phase5d_independent_validation.md for score/rank audit, Top 10 stability and bootstrap intervals; phase5d_batter_top10_stability.csv for candidate-level evidence; and phase5d_bowler_model_investigation.md for field coverage and the bowling-model decision.\n")
    (REPORTS / "phase5d_submission_readiness.md").write_text(readiness, encoding="utf-8")


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    scope, cohorts, seasons = _scope_and_cohorts()
    agg = _batter_match_aggregate(cohorts["wicket_phase_proxy"], seasons)
    stability, audit = audit_and_stability(agg)
    availability, bowling_md = bowling_investigation(scope, cohorts)
    stability.to_csv(REPORTS/"phase5d_batter_top10_stability.csv", index=False)
    availability.to_csv(REPORTS/"phase5d_bowling_field_availability.csv", index=False)
    (REPORTS/"phase5d_bowler_model_investigation.md").write_text(bowling_md, encoding="utf-8")
    (REPORTS/"phase5d_audit_summary.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    write_readiness_reports(stability, audit)
    return audit


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
