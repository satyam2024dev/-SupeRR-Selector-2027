"""Phase 5C final ratings; competition eligibility stays on inherited floors."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.phase5b_rating_methodology import pressure_cohorts, _metric_rows
from src.player_analytics import BATTER_FLOORS, BOWLER_FLOORS
from src.confirmed_scope_coverage import RAW, filter_confirmed_scope

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
FEATURES = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
SEED = 202605
BOOTSTRAPS = 120


def truth(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


def _metric(rows: pd.DataFrame, role: str) -> dict:
    return _metric_rows(rows, role)


def _by_match(rows: pd.DataFrame, role: str) -> pd.DataFrame:
    out = []
    for match, part in rows.groupby("match_id", sort=True):
        m = _metric(part, role)
        out.append({"match_id": match, **m})
    return pd.DataFrame(out)


def _delta(pressure: dict, baseline: dict, role: str) -> dict:
    if role == "batter":
        return {
            "delta_sr": (pressure["ordinary_subset_sr"] - baseline["ordinary_subset_sr"]
                         if pressure["ordinary_subset_sr"] is not None and baseline["ordinary_subset_sr"] is not None else np.nan),
            "dot_rate_improvement": (baseline["dot_rate"] - pressure["dot_rate"]
                                     if pressure["dot_rate"] is not None and baseline["dot_rate"] is not None else np.nan),
            "boundary_rate_change": (pressure["boundary_event_rate"] - baseline["boundary_event_rate"]
                                     if pressure["boundary_event_rate"] is not None and baseline["boundary_event_rate"] is not None else np.nan),
        }
    p = pressure.get("recognized_wickets_per_observed_event")
    b = baseline.get("recognized_wickets_per_observed_event")
    return {"wicket_yield_delta": p - b if p is not None and b is not None else np.nan}


def _player_rows(features: pd.DataFrame, pair: pd.DataFrame, role: str, fmt: str) -> list[dict]:
    idcol, namecol = (("striker_id", "striker_name") if role == "batter" else ("bowler_id", "bowler_name"))
    floors = BATTER_FLOORS if role == "batter" else BOWLER_FLOORS
    f = features.loc[features.analysis_format.eq(fmt)]
    p = pair.loc[pair.analysis_format.eq(fmt)]
    out = []
    for pid, full in f.dropna(subset=[idcol]).groupby(idcol, sort=True):
        name_vals = full[namecol].dropna().astype(str).mode()
        name = name_vals.iloc[0] if len(name_vals) else "Unknown"
        pr = p.loc[p[idcol].eq(pid) & p.cohort.eq("pressure")]
        bl = p.loc[p[idcol].eq(pid) & p.cohort.eq("baseline")]
        if role == "batter":
            pr = pr.loc[truth(pr.ordinary_delivery)]
            bl = bl.loc[truth(bl.ordinary_delivery)]
        pe, be = len(pr), len(bl)
        pm, bm = int(pr.match_id.nunique()), int(bl.match_id.nunique())
        if not pe or not be:
            continue
        pmets, bmets = _metric(pr, role), _metric(bl, role)
        deltas = _delta(pmets, bmets, role)
        if role == "batter" and (pmets["run_coverage_pct"] is None or bmets["run_coverage_pct"] is None):
            continue
        pmatch, bmatch = _by_match(pr, role), _by_match(bl, role)
        pmatch = pmatch.set_index("match_id")
        bmatch = bmatch.set_index("match_id")
        paired_matches = sorted(set(pmatch.index) & set(bmatch.index))
        match_deltas = []
        for m in paired_matches:
            match_deltas.append(_delta(pmatch.loc[m].to_dict(), bmatch.loc[m].to_dict(), role))
        row = {
            "player_id": pid, "player_name": name, "format": fmt, "role": role,
            "pressure_definition": "wicket_phase_context_Q75_vs_Q25",
            "ranking_status": "exploratory_contextual_only",
            "matches_played_in_scope": int(full.match_id.nunique()),
            "pressure_events": pe, "pressure_matches": pm,
            "baseline_events": be, "baseline_matches": bm,
            "pressure_matches_exposed": pm, "baseline_matches_exposed": bm,
            "paired_pressure_events": pe, "paired_baseline_events": be,
            "paired_pressure_metrics": json.dumps(pmets, sort_keys=True),
            "paired_baseline_metrics": json.dumps(bmets, sort_keys=True),
            "paired_match_count_for_consistency": len(paired_matches),
            "pressure_event_floor": floors["pressure_events"], "pressure_match_floor": floors["pressure_matches"],
            "baseline_event_floor": floors["baseline_events"], "baseline_match_floor": floors["baseline_matches"],
            "meets_competition_floor": bool(pe >= floors["pressure_events"] and pm >= floors["pressure_matches"]
                and be >= floors["baseline_events"] and bm >= floors["baseline_matches"]),
            **deltas,
        }
        if role == "batter":
            row.update({
                "pressure_sr": pmets["ordinary_subset_sr"], "baseline_sr": bmets["ordinary_subset_sr"],
                "pressure_dot_rate": pmets["dot_rate"], "baseline_dot_rate": bmets["dot_rate"],
                "pressure_boundary_event_rate": pmets["boundary_event_rate"], "baseline_boundary_event_rate": bmets["boundary_event_rate"],
                "pressure_run_coverage_pct": pmets["run_coverage_pct"], "baseline_run_coverage_pct": bmets["run_coverage_pct"],
                "pressure_known_run_events": pmets["known_run_events"], "baseline_known_run_events": bmets["known_run_events"],
                "pressure_missing_run_events": pmets["missing_run_events"], "baseline_missing_run_events": bmets["missing_run_events"],
            })
            row["pressure_match_consistency_sr"] = float(np.mean([d["delta_sr"] > 0 for d in match_deltas if pd.notna(d["delta_sr"])])) if match_deltas else np.nan
            row["pressure_match_consistency_dot"] = float(np.mean([d["dot_rate_improvement"] > 0 for d in match_deltas if pd.notna(d["dot_rate_improvement"])])) if match_deltas else np.nan
            row["pressure_match_consistency_boundary"] = float(np.mean([d["boundary_rate_change"] > 0 for d in match_deltas if pd.notna(d["boundary_rate_change"])])) if match_deltas else np.nan
        else:
            row.update({"pressure_recognized_credit_wickets": pmets["recognized_wickets"],
                "baseline_recognized_credit_wickets": bmets["recognized_wickets"],
                "pressure_wicket_yield_per_observed_event": pmets["recognized_wickets_per_observed_event"],
                "baseline_wicket_yield_per_observed_event": bmets["recognized_wickets_per_observed_event"],
                "bowler_conceded_runs": "blocked", "economy_rate": "blocked", "conventional_bowling_strike_rate": "blocked"})
            row["pressure_match_consistency_wicket_yield"] = float(np.mean([d["wicket_yield_delta"] > 0 for d in match_deltas if pd.notna(d["wicket_yield_delta"])])) if match_deltas else np.nan
        out.append(row)
    return out


def _bootstrap_score(row: dict, role: str, rng: np.random.Generator,
                    means: dict[str, float], scales: dict[str, float], weights: list[float]) -> tuple[float, float]:
    """Cluster resample match rows for a raw-effect uncertainty interval."""
    p = row["_pressure_match"]
    b = row["_baseline_match"]
    n = max(len(p), len(b))
    if min(len(p), len(b)) < 2:
        return np.nan, np.nan
    samples = []
    for _ in range(BOOTSTRAPS):
        ps = p.iloc[rng.integers(0, len(p), len(p))]
        bs = b.iloc[rng.integers(0, len(b), len(b))]
        def aggregate(x: pd.DataFrame) -> dict:
            events = int(x.metric_events.sum())
            if role == "batter":
                known = int(x.known_run_events.sum())
                runs = float(x.batter_runs.sum())
                return {"ordinary_subset_sr": 100*runs/known if known else None,
                    "dot_rate": float((x.dot_rate.fillna(0)*x.known_run_events).sum()/known) if known else None,
                    "boundary_event_rate": float((x.boundary_event_rate.fillna(0)*x.metric_events).sum()/events) if events else None}
            wickets = int(x.recognized_wickets.sum())
            return {"recognized_wickets_per_observed_event": wickets/events if events else None}
        pm, bm = aggregate(ps), aggregate(bs)
        d = _delta(pm, bm, role)
        if role == "batter":
            vals = [d[k] for k in ["delta_sr", "dot_rate_improvement", "boundary_rate_change"]]
        else:
            vals = [d["wicket_yield_delta"]]
        z = [(v - means[k]) / scales[k] if pd.notna(v) and scales[k] else np.nan
             for v,k in zip(vals, means)]
        samples.append(float(sum(w*v for w,v in zip(weights,z))) if np.isfinite(z).all() else np.nan)
    return tuple(np.nanquantile(samples, [.025, .975]))


def build_rankings(features: pd.DataFrame, cohorts: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pair = cohorts["wicket_phase_proxy"]
    all_rows = []
    for fmt in ["IPL", "T20I"]:
        for role in ["batter", "bowler"]:
            rows = _player_rows(features, pair, role, fmt)
            idcol = "striker_id" if role == "batter" else "bowler_id"
            for r in rows:
                player = pair.loc[pair.analysis_format.eq(fmt) & pair[idcol].eq(r["player_id"])]
                r["_pressure_match"] = _by_match(player.loc[player.cohort.eq("pressure") & (truth(player.ordinary_delivery) if role == "batter" else True)], role)
                r["_baseline_match"] = _by_match(player.loc[player.cohort.eq("baseline") & (truth(player.ordinary_delivery) if role == "batter" else True)], role)
            df = pd.DataFrame(rows)
            if df.empty:
                continue
            # Empirical Q25 exposure gate from Phase 5B; explicitly exploratory.
            any_both = df.loc[df.pressure_events.gt(0) & df.baseline_events.gt(0)]
            pmin = max(1, int(math.ceil(any_both.pressure_events.quantile(.25))))
            bmin = max(1, int(math.ceil(any_both.baseline_events.quantile(.25))))
            eligible = df.loc[df.pressure_events.ge(pmin) & df.baseline_events.ge(bmin)
                & df.pressure_matches.ge(2) & df.baseline_matches.ge(2)].copy()
            eligible["exploratory_pressure_event_min"] = pmin
            eligible["exploratory_baseline_event_min"] = bmin
            eligible["exploratory_match_min_each_side"] = 2
            if role == "batter":
                metrics = ["delta_sr", "dot_rate_improvement", "boundary_rate_change"]
                weights = [0.6, 0.2, 0.2]
                scenarios = {"60_20_20": weights, "100_0_0": [1,0,0], "50_25_25": [.5,.25,.25], "40_30_30": [.4,.3,.3]}
            else:
                metrics = ["wicket_yield_delta"]
                weights = [1.0]
                scenarios = {"single_wicket_yield": [1.0]}
            # Standardize within format and role, without blending formats.
            means, scales = {}, {}
            for m in metrics:
                mu, sd = df[m].mean(), df[m].std(ddof=0)
                means[m], scales[m] = float(mu), float(sd) if pd.notna(sd) else 0.0
                df[f"z_{m}"] = (df[m] - mu) / sd if sd and pd.notna(sd) else 0.0
            for m in metrics:
                eligible[f"z_{m}"] = df.loc[eligible.index, f"z_{m}"]
            if role == "batter":
                for scenario, wts in scenarios.items():
                    eligible[f"score_{scenario}"] = sum(w * eligible[f"z_{m}"] for w,m in zip(wts, metrics))
                scorecol = "score_60_20_20"
                # Match-level positive rates remain evidence, not an extra double-counted weight.
                eligz = eligible[metrics].notna().all(axis=1)
                eligible = eligible.loc[eligz].copy()
            else:
                eligible["score_single_wicket_yield"] = eligible["z_wicket_yield_delta"]
                scorecol = "score_single_wicket_yield"
            # Reliability shrinkage uses event counts and explicit fixed k=20; sensitivity varies k.
            n_eff = 2 * eligible.pressure_events * eligible.baseline_events / (eligible.pressure_events + eligible.baseline_events)
            shrink = n_eff / (n_eff + 20)
            eligible["effective_events_harmonic"] = n_eff
            eligible["shrinkage_factor_k20"] = shrink
            eligible["score_unshrunk"] = eligible[scorecol]
            eligible["score"] = eligible[scorecol] * shrink
            eligible["score_uncertainty_95_low"] = np.nan
            eligible["score_uncertainty_95_high"] = np.nan
            rng = np.random.default_rng(SEED + (1 if fmt == "IPL" else 2) + (0 if role == "batter" else 10))
            for idx, r in eligible.iterrows():
                low, high = _bootstrap_score(r.to_dict(), role, rng, means, scales, weights)
                eligible.loc[idx, "score_uncertainty_95_low"] = low * r["shrinkage_factor_k20"] if pd.notna(low) else np.nan
                eligible.loc[idx, "score_uncertainty_95_high"] = high * r["shrinkage_factor_k20"] if pd.notna(high) else np.nan
            eligible["score_method"] = scorecol
            eligible["score_uncertainty_method"] = f"{BOOTSTRAPS} match-cluster bootstrap draws; percentile 95% interval; at least two match clusters per cohort required"
            eligible = eligible.sort_values(["score", "player_id"], ascending=[False, True]).reset_index(drop=True)
            eligible["rank"] = np.arange(1, len(eligible) + 1)
            eligible["metric_weights"] = "SR delta 60%, dot improvement 20%, boundary change 20%" if role == "batter" else "recognized wicket yield delta 100%"
            eligible["limitations"] = "Exploratory only: wicket/phase context is a proxy; role, phase and match-state confounding; not verified psychological pressure."
            all_rows.extend(eligible.to_dict("records"))
    ranks = pd.DataFrame(all_rows)
    if not ranks.empty:
        ranks = ranks.drop(columns=["_pressure_match", "_baseline_match"], errors="ignore")
    bats = ranks.loc[ranks.role.eq("batter")].copy() if not ranks.empty else pd.DataFrame()
    bowls = ranks.loc[ranks.role.eq("bowler")].copy() if not ranks.empty else pd.DataFrame()
    return bats, bowls, pd.DataFrame(all_rows)


def exclusion_table(features: pd.DataFrame, cohorts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows=[]
    pair=cohorts["wicket_phase_proxy"]
    for fmt in ["IPL","T20I"]:
        for role,idcol,namecol,floors in [("batter","striker_id","striker_name",BATTER_FLOORS),("bowler","bowler_id","bowler_name",BOWLER_FLOORS)]:
            full=features.loc[features.analysis_format.eq(fmt)].dropna(subset=[idcol])
            p=pair.loc[pair.analysis_format.eq(fmt)]
            vals=[]
            for pid, f in full.groupby(idcol,sort=True):
                name=f[namecol].dropna().astype(str).mode()
                pr=p.loc[p[idcol].eq(pid)&p.cohort.eq("pressure")]
                bl=p.loc[p[idcol].eq(pid)&p.cohort.eq("baseline")]
                if role=="batter": pr=pr.loc[truth(pr.ordinary_delivery)]; bl=bl.loc[truth(bl.ordinary_delivery)]
                pe,be=len(pr),len(bl); pm,bm=pr.match_id.nunique(),bl.match_id.nunique()
                why=[]
                if not pe: why.append("no paired contextual pressure events")
                if not be: why.append("no paired baseline events")
                if pe<floors['pressure_events']: why.append("pressure event floor not met")
                if pm<floors['pressure_matches']: why.append("pressure match floor not met")
                if be<floors['baseline_events']: why.append("baseline event floor not met")
                if bm<floors['baseline_matches']: why.append("baseline match floor not met")
                vals.append({"format":fmt,"role":role,"player_id":pid,"player_name":name.iloc[0] if len(name) else "Unknown",
                    "matches_played_in_scope":f.match_id.nunique(),"pressure_events":pe,"pressure_matches":pm,"baseline_events":be,"baseline_matches":bm,
                    "competition_ready":not why,"exclusion_reason":"; ".join(why)})
            rows.extend(vals)
    return pd.DataFrame(rows)


def main() -> dict:
    REPORTS.mkdir(parents=True,exist_ok=True)
    evidence=pd.read_csv(REPORTS/"phase5b_player_method_evidence.csv",low_memory=False)
    eligibility=pd.read_csv(REPORTS/"phase5b_eligibility_sensitivity.csv",low_memory=False)
    frames=[]
    for (fmt,role),g in evidence.loc[evidence.method.eq("wicket_phase_proxy")].groupby(["format","role"]):
        gate=eligibility.loc[eligibility.method.eq("wicket_phase_proxy")&eligibility.format.eq(fmt)&eligibility.role.eq(role)&eligibility.threshold_tier.eq("exploratory_empirical_Q25")]
        selected=set(str(gate.iloc[0].eligible_player_ids).split(";")) if len(gate) and pd.notna(gate.iloc[0].eligible_player_ids) else set()
        strict=set(g.loc[g.meets_existing_floors.astype(bool),"player_id"].astype(str))
        selected |= strict
        pool=g.copy()
        if role=="batter":
            pool["dot_rate_improvement"]=-pd.to_numeric(pool.delta_dot_rate,errors="coerce")
            source=["delta_sr","dot_rate_improvement","delta_boundary_rate"]
            weights=[.6,.2,.2]
        else:
            pool["wicket_yield_delta"]=pd.to_numeric(pool.pressure_wicket_yield_per_event,errors="coerce")-pd.to_numeric(pool.baseline_wicket_yield_per_event,errors="coerce")
            source=["wicket_yield_delta"]
            weights=[1.0]
        for c in source: pool[c]=pd.to_numeric(pool[c],errors="coerce")
        means={c:pool[c].mean() for c in source}; scales={c:pool[c].std(ddof=0) for c in source}
        pool=pool.loc[pool.player_id.astype(str).isin(selected)&pool[source].notna().all(axis=1)].copy()
        if pool.empty: continue
        z=[]
        for c in source: z.append((pool[c]-means[c])/scales[c] if scales[c] and pd.notna(scales[c]) else pd.Series(0.,index=pool.index))
        pool["score_unshrunk"]=sum(w*v for w,v in zip(weights,z))
        n_eff=2*pool.pressure_events*pool.baseline_events/(pool.pressure_events+pool.baseline_events)
        pool["effective_events_harmonic"]=n_eff
        pool["shrinkage_factor_k20"]=n_eff/(n_eff+20)
        pool["score"]=pool.score_unshrunk*pool.shrinkage_factor_k20
        # Event-count approximation to score uncertainty; match exposure separately shows clustering limits.
        se=pool.shrinkage_factor_k20*np.sqrt(1/pool.pressure_events+1/pool.baseline_events)
        pool["score_uncertainty_95_low"]=pool.score-1.96*se
        pool["score_uncertainty_95_high"]=pool.score+1.96*se
        pool["score_uncertainty_method"]="Approximate event-count SE on standardized score; 95% normal interval; not cluster-robust"
        pool["rank_stability_note"]="Per-match pressure outcome shares vs aggregate baseline are used as a consistency reliability shrink; score uncertainty does not propagate uncertainty in this factor"
        pool["pressure_definition"]="wicket_phase_context_Q75_vs_Q25"
        pool["ranking_status"]="exploratory_contextual_only"
        if role=="batter":
            pool.loc[pool.meets_existing_floors.astype(bool),"ranking_status"]="competition_ready_contextual_batter"
        pool["competition_ready"]=pool.ranking_status.eq("competition_ready_contextual_batter")
        pool["matches_played_in_scope"]=pool.matches_observed
        pool["match_consistency_status"]="not_estimable from cohort-aggregated Phase 5B evidence; pressure/baseline match counts reported"
        pool["score_method"]="60_20_20" if role=="batter" else "single_wicket_yield"
        pool["metric_weights"]="ordinary-subset SR delta 60%; dot-rate improvement (baseline minus pressure) 20%; boundary-event change 20%" if role=="batter" else "recognized credited wickets per observed delivery event yield delta 100%"
        pool["limitations"]="Contextual proxy only; not verified psychological pressure. Limited and potentially differential run coverage." if role=="batter" else "Contextual proxy only; credited wickets per observed delivery event. Economy and conventional bowling strike rate blocked."
        frames.append(pool)
    rankings=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    # Recover match-level consistency from supplied deliveries for listed candidates.
    if not rankings.empty:
        raw=pd.read_csv(FEATURES,low_memory=False)
        matches=pd.read_csv(RAW/"matches.csv",low_memory=False)
        competitions=pd.read_csv(RAW/"competitions.csv",low_memory=False)
        scoped=filter_confirmed_scope(raw,matches,competitions)
        paired=pressure_cohorts(scoped)["wicket_phase_proxy"]
        for role,idcol in [("batter","striker_id"),("bowler","bowler_id")]:
            target=rankings.loc[rankings.role.eq(role)]
            updates=[]
            for fmt, cand in target.groupby("format"):
                ids=set(cand.player_id.astype(str))
                x=paired.loc[paired.analysis_format.eq(fmt)&paired.cohort.eq("pressure")&paired[idcol].astype(str).isin(ids)].copy()
                if role=="batter":
                    x=x.loc[truth(x.ordinary_delivery)].copy()
                    x["_runs"]=pd.to_numeric(x.batter_runs_verified_subset,errors="coerce")
                    x["_dot"]=truth(x.dot_ball_verified_subset).astype(int)
                    x["_boundary"]=truth(x.boundary_event).astype(int)
                    gm=x.groupby(idcol,dropna=True).agg(pressure_match_count_observed=("match_id","nunique"),events=("match_id","size"),known=("_runs","count"),runs=("_runs","sum"),dots=("_dot","sum"),boundaries=("_boundary","sum"))
                    # Match-level rates are compared with the player's aggregate normal-context baseline.
                    per=x.groupby([idcol,"match_id"],dropna=True).agg(events=("match_id","size"),known=("_runs","count"),runs=("_runs","sum"),dots=("_dot","sum"),boundaries=("_boundary","sum"))
                    per["sr"]=100*per.runs/per.known.replace(0,np.nan); per["dot_rate"]=per.dots/per.known.replace(0,np.nan); per["boundary_rate"]=per.boundaries/per.events
                    bas=cand.set_index(cand.player_id.astype(str))[["baseline_sr","baseline_dot_rate","baseline_boundary_rate"]]
                    per=per.reset_index(); per["_id"]=per[idcol].astype(str); per=per.join(bas,on="_id")
                    per["sr_positive"]=per.sr.gt(per.baseline_sr); per["dot_positive"]=per.dot_rate.lt(per.baseline_dot_rate); per["boundary_positive"]=per.boundary_rate.gt(per.baseline_boundary_rate)
                    con=per.groupby(per._id).agg(sr_positive_match_share=("sr_positive","mean"),dot_improvement_match_share=("dot_positive","mean"),boundary_improvement_match_share=("boundary_positive","mean"))
                else:
                    x["_wicket"]=truth(x.bowler_wicket_event).astype(int)
                    per=x.groupby([idcol,"match_id"],dropna=True).agg(events=("match_id","size"),wickets=("_wicket","sum"))
                    per["match_yield"]=per.wickets/per.events
                    bas=cand.set_index(cand.player_id.astype(str))["baseline_wicket_yield_per_event"]
                    per=per.reset_index(); per["_id"]=per[idcol].astype(str); per=per.join(bas,on="_id")
                    per["yield_positive"]=per.match_yield.gt(per.baseline_wicket_yield_per_event)
                    con=per.groupby(per._id).agg(wicket_yield_positive_match_share=("yield_positive","mean"))
                con=con.reset_index(names="player_id"); con["format"]=fmt; con["role"]=role
                updates.append(con)
            if updates:
                u=pd.concat(updates,ignore_index=True)
                rankings["_pid_key"]=rankings.player_id.astype(str)
                u["_pid_key"]=u.player_id.astype(str)
                rankings=rankings.merge(u.drop(columns="player_id"),on=["format","role","_pid_key"],how="left").drop(columns="_pid_key")
        consistency_cols=[c for c in rankings.columns if c.endswith("_match_share")]
        rankings["match_consistency_index"]=rankings[consistency_cols].mean(axis=1) if consistency_cols else np.nan
        rankings["match_consistency_status"]="calculated from per-match pressure rates vs aggregate normal-context baseline; descriptive, small clustered samples"
        rankings["consistency_limitation"]="Positive-match shares are descriptive and are not a separate weighted score component; baseline is cohort aggregate."
        # Match-to-match consistency is included as a reliability shrink toward format mean.
        rankings["consistency_reliability_factor"]=0.5+0.5*rankings.match_consistency_index.fillna(0.5)
        rankings["score_before_consistency_adjustment"]=rankings.score
        rankings["score"]=rankings.score*rankings.consistency_reliability_factor
        rankings["score_uncertainty_95_low"]=rankings.score_uncertainty_95_low*rankings.consistency_reliability_factor
        rankings["score_uncertainty_95_high"]=rankings.score_uncertainty_95_high*rankings.consistency_reliability_factor
        rankings=rankings.sort_values(["format","role","score","player_id"],ascending=[True,True,False,True])
        rankings["rank"]=rankings.groupby(["format","role"]).cumcount()+1
    if not rankings.empty:
        rankings=rankings.sort_values(["format","role","score","player_id"],ascending=[True,True,False,True])
        rankings["rank"]=rankings.groupby(["format","role"]).cumcount()+1
    bats=rankings.loc[rankings.role.eq("batter")].copy() if not rankings.empty else pd.DataFrame()
    bowls=rankings.loc[rankings.role.eq("bowler")].copy() if not rankings.empty else pd.DataFrame()
    bats.to_csv(REPORTS/"phase5c_batter_rankings.csv",index=False)
    bowls.to_csv(REPORTS/"phase5c_bowler_rankings.csv",index=False)
    # Reuse the fully enumerated proxy evidence and inherited Phase 2D decisions.
    exclusions=evidence.loc[evidence.method.eq("wicket_phase_proxy")].copy()
    exclusions["exposure_floors_met"]=exclusions.meets_existing_floors.astype(bool)
    candidate_keys=set((bats.format.astype(str)+"|batter|"+bats.player_id.astype(str)).tolist()) | set((bowls.format.astype(str)+"|bowler|"+bowls.player_id.astype(str)).tolist())
    exclusions["exploratory_candidate"]=(exclusions.format.astype(str)+"|"+exclusions.role.astype(str)+"|"+exclusions.player_id.astype(str)).isin(candidate_keys)
    comp_keys=set((bats.loc[bats.competition_ready,"format"].astype(str)+"|batter|"+bats.loc[bats.competition_ready,"player_id"].astype(str)).tolist())
    exclusions["competition_ready"]=(exclusions.format.astype(str)+"|"+exclusions.role.astype(str)+"|"+exclusions.player_id.astype(str)).isin(comp_keys)
    exclusions["exclusion_reason"]=exclusions.exclusion_reason.fillna("")
    proxy_only=exclusions.exclusion_reason.eq("") & ~exclusions.competition_ready
    exclusions.loc[proxy_only,"exclusion_reason"]="Exposure floors met, but wicket-depletion context is not role-valid as bowler pressure; exploratory only."
    exclusions.to_csv(REPORTS/"phase5c_candidate_exclusions.csv",index=False)
    counts={"competition_ready":int(rankings.competition_ready.sum()),
        "competition_ready_batters":int(bats.competition_ready.sum()),
        "exploratory_batters":int((~bats.competition_ready).sum()),
        "exploratory_bowlers":len(bowls),
        "exploratory_batter_candidates":int((~bats.competition_ready).sum()),
        "exploratory_bowler_candidates":len(bowls)}
    (REPORTS/"phase5c_counts.json").write_text(json.dumps(counts,indent=2),encoding="utf-8")
    write_reports(evidence,eligibility,bats,bowls,counts)
    return counts


def write_reports(evidence: pd.DataFrame, eligibility: pd.DataFrame, bats: pd.DataFrame,
                  bowls: pd.DataFrame, counts: dict) -> None:
    def md_table(frame: pd.DataFrame) -> str:
        cols=list(frame.columns)
        esc=lambda v: str(v).replace("|","/").replace("\n"," ")
        return "| "+" | ".join(cols)+" |\n| "+" | ".join(["---"]*len(cols))+" |\n"+"\n".join("| "+" | ".join(esc(v) for v in row)+" |" for row in frame.itertuples(index=False,name=None))
    # Rank stability is evaluated on the exploratory proxy cohort only.
    sens=[]
    for fmt in ["IPL","T20I"]:
        g_all=evidence.loc[evidence.method.eq("wicket_phase_proxy")&evidence.format.eq(fmt)&evidence.role.eq("batter")].copy()
        ids=set(bats.loc[bats.format.eq(fmt),"player_id"].astype(str))
        g=g_all
        g["delta_sr"]=pd.to_numeric(g.delta_sr,errors="coerce")
        g["delta_boundary_rate"]=pd.to_numeric(g.delta_boundary_rate,errors="coerce")
        g["dot_improvement"]=-pd.to_numeric(g.delta_dot_rate,errors="coerce")
        cols=["delta_sr","dot_improvement","delta_boundary_rate"]
        for c in cols: g[c]=pd.to_numeric(g[c],errors="coerce")
        ranks=[]
        for weights,name in [([.6,.2,.2],"60/20/20"),([1,0,0],"100/0/0"),([.5,.25,.25],"50/25/25"),([.4,.3,.3],"40/30/30")]:
            z=[]
            for c in cols:
                sd=g[c].std(ddof=0)
                z.append((g[c]-g[c].mean())/sd if pd.notna(sd) and sd>0 else pd.Series(0.,index=g.index))
            neff=2*g.pressure_events*g.baseline_events/(g.pressure_events+g.baseline_events)
            score=sum(w*v for w,v in zip(weights,z))*neff/(neff+20)
            factor=bats.loc[bats.format.eq(fmt)].set_index(bats.loc[bats.format.eq(fmt)].player_id.astype(str)).consistency_reliability_factor
            candidate_score=score.loc[g.player_id.astype(str).isin(ids)]
            candidate_score.index=g.loc[g.player_id.astype(str).isin(ids),"player_id"].astype(str)
            candidate_score=candidate_score*factor.reindex(candidate_score.index).to_numpy()
            ranks.append((name,candidate_score.rank(ascending=False,method="average"),candidate_score))
        base=ranks[0][1]
        for name,rank,score in ranks:
            overlap=len(set(score.nlargest(min(10,len(score))).index)&set(ranks[0][2].nlargest(min(10,len(score))).index))
            sens.append({"format":fmt,"comparison":"batter weights","scenario":name,"spearman_vs_60_20_20":float(rank.corr(base,method="spearman")),"top10_overlap":overlap,"eligible_pool":len(score)})
    sensitivity=pd.DataFrame(sens)
    definition_rows=[]
    for fmt in ["IPL","T20I"]:
        for role in ["batter","bowler"]:
            method_ranks={}
            method_ids={}
            for method in ["verified_chase","wicket_phase_proxy","combined_verified_and_proxy"]:
                g=evidence.loc[evidence.method.eq(method)&evidence.format.eq(fmt)&evidence.role.eq(role)].copy()
                if role=="batter":
                    metrics=["delta_sr","dot_improvement","delta_boundary_rate"]
                    g["dot_improvement"]=-pd.to_numeric(g.delta_dot_rate,errors="coerce")
                    weights=[.6,.2,.2]
                else:
                    metrics=["wicket_yield_delta"]
                    g["wicket_yield_delta"]=pd.to_numeric(g.pressure_wicket_yield_per_event,errors="coerce")-pd.to_numeric(g.baseline_wicket_yield_per_event,errors="coerce")
                    weights=[1.0]
                for c in metrics: g[c]=pd.to_numeric(g[c],errors="coerce")
                g=g.loc[g[metrics].notna().all(axis=1)].copy()
                score=0
                for c,w in zip(metrics,weights):
                    sd=g[c].std(ddof=0)
                    score=score+w*((g[c]-g[c].mean())/sd if pd.notna(sd) and sd>0 else 0)
                neff=2*g.pressure_events*g.baseline_events/(g.pressure_events+g.baseline_events)
                score=score*neff/(neff+20)
                method_ranks[method]=pd.Series(score.to_numpy(),index=g.player_id.astype(str)).rank(ascending=False,method="average")
                method_ids[method]=set(method_ranks[method].index)
            for other in ["verified_chase","combined_verified_and_proxy"]:
                common=sorted(method_ids.get("wicket_phase_proxy",set())&method_ids.get(other,set()))
                left=method_ranks["wicket_phase_proxy"].reindex(common); right=method_ranks[other].reindex(common)
                rho=float(left.corr(right,method="spearman")) if len(common)>1 and left.nunique()>1 and right.nunique()>1 else np.nan
                definition_rows.append({"format":fmt,"role":role,"comparison":"wicket_phase_proxy vs "+other,"common_players_with_both_metric_deltas":len(common),"spearman_rank_correlation":rho,"interpretation":"raw metric score ordering before proxy match-consistency adjustment; under-floor diagnostic, not an eligibility or final-rank claim"})
    definition_sensitivity=pd.DataFrame(definition_rows)
    threshold_rows=[]
    for fmt in ["IPL","T20I"]:
        for role in ["batter","bowler"]:
            g=evidence.loc[evidence.method.eq("wicket_phase_proxy")&evidence.format.eq(fmt)&evidence.role.eq(role)].copy()
            metric_cols=["delta_sr","delta_dot_rate","delta_boundary_rate"] if role=="batter" else ["wicket_yield_delta"]
            if role=="batter":
                g["dot_rate_improvement"]=-pd.to_numeric(g.delta_dot_rate,errors="coerce")
                metric_cols=["delta_sr","dot_rate_improvement","delta_boundary_rate"]
            else:
                g["wicket_yield_delta"]=pd.to_numeric(g.pressure_wicket_yield_per_event,errors="coerce")-pd.to_numeric(g.baseline_wicket_yield_per_event,errors="coerce")
            score=0
            for metric,w in zip(metric_cols,([.6,.2,.2] if role=="batter" else [1.0])):
                g[metric]=pd.to_numeric(g[metric],errors="coerce")
                sd=g[metric].std(ddof=0)
                score=score+w*((g[metric]-g[metric].mean())/sd if pd.notna(sd) and sd>0 else 0)
            neff=2*g.pressure_events*g.baseline_events/(g.pressure_events+g.baseline_events)
            g["rating"]=score*neff/(neff+20)
            cf=(bats if role=="batter" else bowls).loc[(bats if role=="batter" else bowls).format.eq(fmt)].set_index((bats if role=="batter" else bowls).loc[(bats if role=="batter" else bowls).format.eq(fmt)].player_id.astype(str)).consistency_reliability_factor
            g["rating"]*=g.player_id.astype(str).map(cf).fillna(1.0)
            q=eligibility.loc[eligibility.method.eq("wicket_phase_proxy")&eligibility.format.eq(fmt)&eligibility.role.eq(role)&eligibility.threshold_tier.eq("exploratory_empirical_Q25")]
            qids=set(str(q.iloc[0].eligible_player_ids).split(";")) if len(q) and pd.notna(q.iloc[0].eligible_player_ids) else set()
            strict=g.loc[g.meets_existing_floors.astype(bool)].set_index(g.loc[g.meets_existing_floors.astype(bool)].player_id.astype(str)).rating
            loose=g.loc[g.player_id.astype(str).isin(qids)].set_index(g.loc[g.player_id.astype(str).isin(qids)].player_id.astype(str)).rating
            common=sorted(set(strict.index)&set(loose.index))
            sr=float(strict.loc[common].rank(ascending=False).corr(loose.loc[common].rank(ascending=False),method="spearman")) if len(common)>1 else np.nan
            topn=min(10,len(strict),len(loose))
            overlap=len(set(strict.nlargest(topn).index)&set(loose.nlargest(topn).index)) if topn else 0
            threshold_rows.append({"format":fmt,"role":role,"inherited_floor_candidates":len(strict),"exploratory_Q25_candidates":len(loose),"common_candidates":len(common),"spearman_on_common_candidates":sr,"top10_overlap":overlap,"comparison":"same proxy score, alternate eligibility gate"})
    threshold_sensitivity=pd.DataFrame(threshold_rows)
    floor=eligibility.loc[eligibility.threshold_tier.eq("existing_Phase2D")]
    q25=eligibility.loc[eligibility.threshold_tier.eq("exploratory_empirical_Q25")]
    pcomp=pd.read_csv(REPORTS/"phase5b_pressure_definition_comparison.csv")
    phase_thresholds=pd.read_csv(REPORTS/"phase5a_proxy_thresholds.csv")
    threshold_table=phase_thresholds[["format","phase","wickets_q75","wickets_q25","high_rule","low_rule"]]
    readiness=[]
    for _,r in pcomp.iterrows():
        readiness.append({"method":r.method,"format":r.format,"role":r.role,"floor_eligible":r.players_meeting_existing_floors,
            "competition_ready":0,"decision":"not competition-ready; verified definition has insufficient candidates, proxy/combined have construct or exposure limitations"})
    validation=("# Phase 5C ranking validation\n\n"
      "## Readiness decision\n\n"
      f"Competition-ready contextual batter candidates: **{counts['competition_ready_batters']}** ({int(bats.loc[bats.format.eq('IPL')].competition_ready.sum())} IPL; {int(bats.loc[bats.format.eq('T20I')].competition_ready.sum())} T20I). Competition-ready contextual bowlers: **0**. Exploratory candidates: **{counts['exploratory_batters']} batters** and **{counts['exploratory_bowlers']} bowlers**. Counts are player-format-role rows; IPL and T20I remain separate.\n\n"
      "The competition-ready label applies only to batter rankings under the explicit operational context definition and inherited Phase 2D floors. The verified RRR > CRR track has zero players meeting those floors. Q75 wicket depletion is role-asymmetric: it describes a depleted batting innings, while a bowler attacking a depleted side is not clearly operating under pressure. Therefore all bowler candidates remain exploratory. Neither contextual nor verified indicators establish psychological pressure.\n\n"
      "## Definition, metric and threshold sensitivity\n\n"
      "Phase 5B supplied definition-by-format-role floor counts are retained here; Phase 5B Q25 sensitivity counts are retained separately. RRR > CRR and its RRR <= CRR comparison remain a validation track, never pooled into the contextual score. Combined RRR-plus-wicket evidence is an intersection and remains sparse. All ranked rows use the wicket/phase Q75 pressure-context vs Q25 low-depletion reference pair; eligibility includes unchanged inherited-floor candidates plus the separately labeled Q25 sensitivity additions.\n\n"
      "### Existing floors\n\n"+md_table(floor[["method","format","role","pressure_event_min","pressure_match_min","baseline_event_min","baseline_match_min","players_eligible"]])+"\n\n"
      "### Pressure definition coverage and inherited-floor passes\n\n"+md_table(pcomp[["method","format","role","paired_pressure_events","paired_baseline_events","paired_matches","paired_match_phase_strata","players_with_both_sides","players_meeting_existing_floors"]])+"\n\n"
      "### Q25 sensitivity (not substituted for official floors)\n\n"+md_table(q25[["method","format","role","pressure_event_min","pressure_match_min","baseline_event_min","baseline_match_min","players_eligible"]])+"\n\n"
      "### Batter weight sensitivity\n\n"+md_table(sensitivity)+"\n\n"
      "### Eligibility threshold rank sensitivity\n\n"+md_table(threshold_sensitivity)+"\n\n"
      "### Pressure-definition rank sensitivity\n\n"+md_table(definition_sensitivity)+"\n\n"
      "Bowler weights are not varied: only one defensible outcome is available. Economy and conventional bowling strike rate remain blocked. Eligibility sensitivity shows that lowering thresholds changes who appears; it does not upgrade any player to competition-ready.\n\n"
      "## Uncertainty and stability limitations\n\n"
      "Scores are standardized within each format and role, reliability-shrunk using harmonic event exposure with fixed k=20, and further shrunk toward zero by the pressure-match consistency factor. Per-match pressure rates are compared with each player's aggregate normal-context baseline. CSV score intervals use an event-count standard error approximation, not cluster-robust intervals, and do not propagate uncertainty in the consistency factor. Pressure and baseline match counts and positive-match shares are reported. Adjacent ranks should not be interpreted as reliably distinct. Batter rank stability is shown across four weight scenarios; threshold stability compares inherited numeric floors with Q25 eligibility. These checks do not validate the pressure construct.\n\n"
      "## Exclusions\n\n"
      "`phase5c_candidate_exclusions.csv` includes every proxy-evidence player-format-role row, exposure, inherited floor decision, competition-ready decision and reason. Numeric floor passes are explicitly separate from competition readiness.\n")
    (REPORTS/"phase5c_ranking_validation.md").write_text(validation,encoding="utf-8")
    methodology=("# Phase 5C final ranking methodology\n\n"
      "## Scope and evidence provenance\n\n"
      "Only supplied official IPL and T20I data from 2022 onward are used. No external scorecards or derived third-party data enter scores. Confirmed competition filtering, match acceptance, delivery normalization, unknown-state safeguards and source data preservation remain in force. Format scores are never combined.\n\n"
      "## Operational pressure conditions\n\n"
      "**Operational contextual definition for batters:** within each format and innings phase, pressure-context observations have wickets lost before the delivery at or above the empirical Q75; low-depletion reference observations are at or below Q25. Super Overs are excluded. Rows are compared only inside match/phase strata containing both classes. These are the supplied data's actual thresholds:\n\n"
      +md_table(threshold_table)+"\n\n"
      "The operational inputs are `wickets_lost_before`, `innings_phase`, format and `match_id`; all are available in the supplied delivery feed. The lost-wicket resource creates a demanding batting situation: a powerplay wicket removes a top-order resource early, middle-over depletion narrows the rebuild-versus-acceleration options, and death-over depletion leaves less batting depth to finish the innings. The reference has preserved more wickets at the same phase. This is an operational context indicator, not verified scoreboard-state or psychological pressure: the feed does not establish required scoring demand, match importance, player intention or psychology.\n\n"
      "This condition is not role-symmetric for bowlers. A bowler facing a depleted batting side may have an easier task. It is therefore evaluated as exploratory evidence for bowlers and cannot alone support a competition-ready bowler ranking. A role-valid pressure definition would need reliable score/target/run-rate demand or another validated bowling-side challenge field; no such definition clears current evidence floors.\n\n"
      "**Verified validation track:** regular second-innings RRR > CRR where reconstructed score, target, runs required, legal balls remaining and completed legal balls support both rates. The reference is RRR <= CRR. This is scoreboard demand, not psychological pressure. It remains separate from the contextual ratings and has no competition-ready candidate under inherited floors.\n\n"
      "**Other comparison:** combined verified demand and high wicket-depletion versus RRR <= CRR and low depletion is retained only as a sparse intersection. No pressure class is imputed when fields are unknown.\n\n"
      "## Ratings\n\n"
      "Batters: 60% ordinary-subset strike-rate delta, 20% dot-rate improvement (baseline minus pressure), and 20% boundary-event-rate change. Ordinary deliveries only; run coverage and missing events are reported. These are limited feed metrics, not conventional full-innings rates. Alternative 100/0/0, 50/25/25 and 40/30/30 weights are tested.\n\n"
      "Bowlers: 100% recognized credited wickets per observed delivery event in pressure context minus comparable baseline yield. This is not bowling strike rate. Bowler-conceded runs, economy and conventional bowling strike rate are blocked and excluded.\n\n"
      "Within each format/role, metrics are standardized across the available evidence pool. Reliability shrinkage is score × n_eff/(n_eff+20), where n_eff is the harmonic mean of pressure and baseline event counts. k=20 is a transparent conservative fixed sensitivity choice, not an empirically optimized parameter. Match consistency is the share of pressure matches in which the player beats the aggregate baseline for each component; component shares are averaged into a consistency index. The score is then multiplied by 0.5 + 0.5 × consistency index, shrinking inconsistent evidence toward zero. All component shares and this factor appear in the CSVs.\n\n"
      "## Eligibility, consistency and uncertainty\n\n"
      "Competition readiness retains existing Phase 2D floors without alteration: batter pressure ≥2 events/2 matches and baseline ≥16 events/3 matches; bowler pressure ≥5 events/2 matches and baseline ≥37 events/2 matches. Batters meeting the existing floors are competition-ready for the context-based contest ranking because wicket depletion is a direct batting-side resource constraint and the comparison is paired within match and phase. This is an operational match-context definition, not a psychological claim. Bowlers remain exploratory because the same condition does not establish a demanding bowling task. The verified RRR > CRR track has no floor-qualified candidates.\n\n"
      "Competition-ready batter rows use unchanged inherited Phase 2D event and match floors. Supplemental exploratory rows use the pre-existing Phase 5B empirical Q25 exposure tier and at least two matches on each side; these additions are never relabeled competition-ready. Bowler rows remain exploratory because wicket depletion is not a role-valid pressure condition for bowlers. Each row reports pressure/baseline events and matches, available metrics, matches played in scope, match-consistency shares, a reliability- and consistency-adjusted score and an approximate 95% score interval. The interval uses event-count standard errors and is not cluster-robust; uncertainty in the consistency factor itself is not propagated.\n\n"
      "## Interpretation\n\n"
      "Competition-ready ranks are operational batter rankings under the competition's context-based definition; they do not establish psychological pressure. Bowler ranks and under-floor batter additions are exploratory. Verified RRR > CRR results remain a separate validation track. Candidate counts are reported as supported; no artificial Top 10 cutoff is imposed. Definitions, weights, floors, limitations, exact counts and exclusions are detailed in the validation report.\n")
    (REPORTS/"phase5c_final_ranking_methodology.md").write_text(methodology,encoding="utf-8")


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
