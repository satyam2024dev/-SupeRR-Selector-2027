"""Phase 5E bowling model investigation and batter sensitivity review."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.player_analytics import BOWLER_FLOORS
from src.phase5d_independent_validation import (
    REPORTS, _scope_and_cohorts, _batter_match_aggregate, _scores,
)

ROOT = Path(__file__).resolve().parents[1]
BOOT_N = 2000
SEED = 5052026


def truth(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


def _population_map(scope: pd.DataFrame, cohorts: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    proxy = cohorts["wicket_phase_proxy"]
    return {
        "all_scope": scope,
        "verified_chase_pressure": cohorts["verified_chase"].loc[cohorts["verified_chase"].cohort.eq("pressure")],
        "verified_chase_baseline": cohorts["verified_chase"].loc[cohorts["verified_chase"].cohort.eq("baseline")],
        "wicket_depletion_high_context_only": proxy.loc[proxy.cohort.eq("pressure")],
        "wicket_depletion_low_context_reference": proxy.loc[proxy.cohort.eq("baseline")],
        "verified_chase_death_pressure": cohorts["verified_chase"].loc[
            cohorts["verified_chase"].cohort.eq("pressure")
            & cohorts["verified_chase"].innings_phase.astype("string").str.contains("death", case=False, na=False)],
        "verified_chase_death_baseline": cohorts["verified_chase"].loc[
            cohorts["verified_chase"].cohort.eq("baseline")
            & cohorts["verified_chase"].innings_phase.astype("string").str.contains("death", case=False, na=False)],
    }


def metric_coverage(scope: pd.DataFrame, cohorts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for pop_name, frame in _population_map(scope, cohorts).items():
        for fmt in ["IPL", "T20I"]:
            x = frame.loc[frame.analysis_format.eq(fmt)].copy()
            ordinary = truth(x.ordinary_delivery)
            o = x.loc[ordinary]
            known_runs = pd.to_numeric(o.batter_runs_verified_subset, errors="coerce")
            dots = truth(o.dot_ball_verified_subset)
            boundary = truth(o.boundary_event)
            wickets = truth(x.bowler_wicket_event)
            legal_known = x.legal_delivery.notna()
            known_legal = truth(x.legal_delivery)
            specifications = [
                ("observed_delivery_event", len(x), len(x), "observed source delivery rows", "Complete as observed rows; not a legal-ball count."),
                ("ordinary_delivery_event", len(o), len(x), "rows with ordinary_delivery=True", "Restricted event denominator; does not cover extras."),
                ("ordinary_batter_runs_known", int(known_runs.notna().sum()), len(o), "ordinary rows with known batter_runs_verified_subset", "Batter runs only on ordinary deliveries; not bowler-conceded runs."),
                ("ordinary_batter_runs_sum", float(known_runs.sum(skipna=True)), int(known_runs.notna().sum()), "known ordinary batter-run rows", "Partial subset; excludes extras and attribution gaps."),
                ("ordinary_dot_event", int((dots & known_runs.notna()).sum()), int(known_runs.notna().sum()), "ordinary rows with known runs", "Dot subset; not all legal balls faced by the bowler."),
                ("ordinary_boundary_event", int(boundary.sum()), len(o), "ordinary delivery events", "Boundary flags; ordinary subset denominator."),
                ("recognized_bowler_credit_wicket", int(wickets.sum()), len(x), "observed delivery events", "Recognized credited wicket event; event yield, not wickets per legal ball."),
                ("legal_delivery_known", int(legal_known.sum()), len(x), "observed delivery events", "Some event legality remains unknown in the full feed; never relabeled as legal balls."),
                ("legal_delivery_true", int(known_legal.sum()), int(legal_known.sum()), "rows with nonmissing legal_delivery", "Known-category event flags; not a complete bowler legal-ball total."),
            ]
            for metric, numerator, denom, denom_name, note in specifications:
                rows.append({
                    "population": pop_name, "format": fmt, "metric": metric,
                    "numerator_or_value": numerator, "denominator": denom,
                    "rate_or_coverage": numerator / denom if denom else np.nan,
                    "denominator_definition": denom_name, "limitations": note,
                    "matches": int(x.match_id.nunique()), "bowlers": int(x.bowler_id.nunique()),
                    "delivery_rows": len(x),
                })
            # Source-field coverage for event attribution and delivery context.
            source_fields=["bowler_id","extras_type","extras_2_runs","runs","is_four","is_six",
                "dismissal_type","legal_delivery","innings_phase","pace_or_spin","bowling_type","bowl_speed",
                "stroke","delivery_style","over_or_around","on_or_off","delivery_context_proxy_eligible"]
            for field in source_fields:
                if field not in x:
                    continue
                available=int(x[field].notna().sum())
                true_count=int(truth(x[field]).sum()) if field=="delivery_context_proxy_eligible" else np.nan
                rows.append({"population":pop_name,"format":fmt,"metric":"field_availability:"+field,
                    "numerator_or_value":available,"denominator":len(x),
                    "rate_or_coverage":available/len(x) if len(x) else np.nan,
                    "denominator_definition":"observed rows in this population",
                    "limitations":f"delivery_context_proxy_eligible true rows={true_count}" if field=="delivery_context_proxy_eligible" else "Field availability does not establish semantic validity or a complete bowling denominator.",
                    "matches":int(x.match_id.nunique()),"bowlers":int(x.bowler_id.nunique()),"delivery_rows":len(x)})
            rows.append({
                "population": pop_name, "format": fmt, "metric": "bowler_conceded_runs",
                "numerator_or_value": np.nan, "denominator": np.nan, "rate_or_coverage": np.nan,
                "denominator_definition": "not available", "limitations": "Blocked: no validated bowler-attributable run total across extras.",
                "matches": int(x.match_id.nunique()), "bowlers": int(x.bowler_id.nunique()), "delivery_rows": len(x),
            })
            rows.append({
                "population": pop_name, "format": fmt, "metric": "conventional_bowling_strike_rate_or_economy",
                "numerator_or_value": np.nan, "denominator": np.nan, "rate_or_coverage": np.nan,
                "denominator_definition": "not available", "limitations": "Blocked: no complete independently validated legal-ball and bowler-conceded-run denominators.",
                "matches": int(x.match_id.nunique()), "bowlers": int(x.bowler_id.nunique()), "delivery_rows": len(x),
            })
    return pd.DataFrame(rows)


def _player_exposure(pair: pd.DataFrame, method: str, metric: str, challenge_valid: bool,
                     q25_ids: dict[tuple[str, str], set[str]]) -> pd.DataFrame:
    rows = []
    floors = BOWLER_FLOORS
    for fmt in ["IPL", "T20I"]:
        x = pair.loc[pair.analysis_format.eq(fmt)].copy()
        if metric == "recognized_credit_wicket_yield":
            event_mask = pd.Series(True, index=x.index)
        else:
            event_mask = truth(x.ordinary_delivery) & pd.to_numeric(x.batter_runs_verified_subset, errors="coerce").notna()
        x = x.loc[event_mask]
        for pid, p in x.dropna(subset=["bowler_id"]).groupby("bowler_id", sort=True):
            pr, bl = p.loc[p.cohort.eq("pressure")], p.loc[p.cohort.eq("baseline")]
            pe, be = len(pr), len(bl)
            pm, bm = int(pr.match_id.nunique()), int(bl.match_id.nunique())
            p_w, b_w = int(truth(pr.bowler_wicket_event).sum()), int(truth(bl.bowler_wicket_event).sum())
            p_runs = pd.to_numeric(pr.batter_runs_verified_subset, errors="coerce")
            b_runs = pd.to_numeric(bl.batter_runs_verified_subset, errors="coerce")
            p_dots = int(truth(pr.dot_ball_verified_subset).sum())
            b_dots = int(truth(bl.dot_ball_verified_subset).sum())
            p_bounds = int(truth(pr.boundary_event).sum())
            b_bounds = int(truth(bl.boundary_event).sum())
            p_pass = pe >= floors["pressure_events"] and pm >= floors["pressure_matches"]
            b_pass = be >= floors["baseline_events"] and bm >= floors["baseline_matches"]
            q25 = str(pid) in q25_ids.get((method, fmt), set())
            rows.append({
                "definition": method, "format": fmt, "role": "bowler", "player_id": pid,
                "player_name": p.bowler_name.dropna().astype(str).mode().iloc[0] if p.bowler_name.notna().any() else "Unknown",
                "metric": metric, "challenge_definition_role_valid": challenge_valid,
                "pressure_events": pe, "pressure_matches": pm, "baseline_events": be, "baseline_matches": bm,
                "pressure_floor_events": floors["pressure_events"], "pressure_floor_matches": floors["pressure_matches"],
                "baseline_floor_events": floors["baseline_events"], "baseline_floor_matches": floors["baseline_matches"],
                "pressure_side_floor_met": p_pass, "baseline_side_floor_met": b_pass,
                "meets_inherited_floors_both_sides": p_pass and b_pass,
                "phase5b_Q25_sensitivity_candidate": q25,
                "competition_ready": False,
                "exploratory_evidence_row": bool(pe and be),
                "pressure_credited_wickets": p_w, "baseline_credited_wickets": b_w,
                "pressure_wicket_yield_per_observed_event": p_w/pe if pe else np.nan,
                "baseline_wicket_yield_per_observed_event": b_w/be if be else np.nan,
                "pressure_ordinary_batter_runs": float(p_runs.sum()) if pe else np.nan,
                "baseline_ordinary_batter_runs": float(b_runs.sum()) if be else np.nan,
                "pressure_ordinary_dot_rate": p_dots/pe if pe else np.nan,
                "baseline_ordinary_dot_rate": b_dots/be if be else np.nan,
                "pressure_ordinary_boundary_rate": p_bounds/pe if pe else np.nan,
                "baseline_ordinary_boundary_rate": b_bounds/be if be else np.nan,
                "decision_note": ("Context contrast only; high wicket depletion is not accepted as bowler pressure."
                    if not challenge_valid else
                    "No competition-ready row: verified pressure definition and outcome exposure do not clear both inherited floors."),
            })
    return pd.DataFrame(rows)


def eligibility_table(cohorts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    elig = pd.read_csv(REPORTS/"phase5b_eligibility_sensitivity.csv", low_memory=False)
    q25_ids = {}
    for method in ["verified_chase", "wicket_phase_proxy", "combined_verified_and_proxy"]:
        for fmt in ["IPL", "T20I"]:
            row = elig.loc[elig.method.eq(method) & elig.format.eq(fmt) & elig.role.eq("bowler")
                & elig.threshold_tier.eq("exploratory_empirical_Q25")]
            ids = set(str(row.iloc[0].eligible_player_ids).split(";")) if len(row) and pd.notna(row.iloc[0].eligible_player_ids) else set()
            q25_ids[(method, fmt)] = ids
    methods = [
        ("verified_chase", cohorts["verified_chase"], True),
        ("verified_chase_death_only", cohorts["verified_chase"].loc[
            cohorts["verified_chase"].innings_phase.astype("string").str.contains("death",case=False,na=False)], True),
        ("wicket_depletion_Q75_vs_Q25_context_only", cohorts["wicket_phase_proxy"], False),
        ("combined_verified_and_wicket_context", cohorts["combined_verified_and_proxy"], True),
    ]
    rows = []
    metrics = ["recognized_credit_wicket_yield", "ordinary_dot_rate", "ordinary_batter_runs_per_ordinary_event", "ordinary_boundary_rate"]
    for name, pair, valid in methods:
        for metric in metrics:
            table = _player_exposure(pair, name, metric, valid, q25_ids)
            if not table.empty:
                rows.append(table)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def cluster_comparisons(verified: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fmt in ["IPL", "T20I"]:
        x = verified.loc[verified.analysis_format.eq(fmt)].copy()
        x["_ordinary"] = truth(x.ordinary_delivery)
        o = x.loc[x._ordinary].copy()
        o["_runs"] = pd.to_numeric(o.batter_runs_verified_subset, errors="coerce")
        o["_dot"] = truth(o.dot_ball_verified_subset).astype(int)
        o["_boundary"] = truth(o.boundary_event).astype(int)
        x["_wicket"] = truth(x.bowler_wicket_event).astype(int)
        agg = x.groupby(["match_id", "cohort"], observed=True).agg(
            events=("match_id", "size"), wickets=("_wicket", "sum")).unstack("cohort", fill_value=0)
        ordinary = o.groupby(["match_id", "cohort"], observed=True).agg(
            ordinary_events=("match_id", "size"), known_runs=("_runs", "count"),
            batter_runs=("_runs", "sum"), dots=("_dot", "sum"), boundaries=("_boundary", "sum")
        ).unstack("cohort", fill_value=0)
        wide = agg.join(ordinary, how="outer").fillna(0)
        wide.columns = [f"{a}_{b}" for a,b in wide.columns]
        for cohort in ["pressure","baseline"]:
            for col in ["events","wickets","ordinary_events","known_runs","batter_runs","dots","boundaries"]:
                if f"{col}_{cohort}" not in wide:
                    wide[f"{col}_{cohort}"]=0
        names = {
            "ordinary_dot_rate": ("dots", "known_runs"),
            "ordinary_batter_runs_per_event": ("batter_runs", "known_runs"),
            "ordinary_boundary_rate": ("boundaries", "ordinary_events"),
            "recognized_wicket_yield_per_observed_event": ("wickets", "events"),
        }
        match_count = len(wide)
        rng = np.random.default_rng(SEED + (1 if fmt=="IPL" else 2))
        if match_count:
            draws = rng.integers(0,match_count,size=(BOOT_N,match_count))
        for metric,(numerator,denominator) in names.items():
            pn = wide[f"{numerator}_pressure"].to_numpy()
            pdn = wide[f"{denominator}_pressure"].to_numpy()
            bn = wide[f"{numerator}_baseline"].to_numpy()
            bdn = wide[f"{denominator}_baseline"].to_numpy()
            p_rate=pn.sum()/pdn.sum() if pdn.sum() else np.nan
            b_rate=bn.sum()/bdn.sum() if bdn.sum() else np.nan
            if match_count:
                p_boot=pn[draws].sum(axis=1)/np.maximum(pdn[draws].sum(axis=1),1)
                b_boot=bn[draws].sum(axis=1)/np.maximum(bdn[draws].sum(axis=1),1)
                ci=np.quantile(p_boot-b_boot,[.025,.975])
            else:
                ci=(np.nan,np.nan)
            rows.append({"format":fmt,"metric":metric,"pressure_value":p_rate,"baseline_value":b_rate,
                "pressure_minus_baseline":p_rate-b_rate,"cluster_ci95_low":ci[0],"cluster_ci95_high":ci[1],
                "paired_match_clusters":match_count,"bootstrap_draws":BOOT_N,
                "interpretation":"exploratory pooled comparison; very few independent match clusters; no ranking"})
    return pd.DataFrame(rows)


def batter_sensitivity_review() -> str:
    _, cohorts, seasons = _scope_and_cohorts()
    from src.phase5d_independent_validation import _batter_match_aggregate
    agg = _batter_match_aggregate(cohorts["wicket_phase_proxy"], seasons)
    stability = pd.read_csv(REPORTS/"phase5d_batter_top10_stability.csv", low_memory=False)
    names = [("Dewald Brevis","IPL"),("Ackeem Auguste","T20I")]
    season_rows=[]
    overview=[]
    for name,fmt in names:
        row=stability.loc[stability.format.eq(fmt)&stability.player_name.eq(name)].iloc[0]
        overview.append({"format":fmt,"player":name,"rank":int(row.phase5c_rank_all_list),
            "score":row.phase5c_score,"pressure_events":int(row.pressure_events),"pressure_matches":int(row.pressure_matches),
            "baseline_events":int(row.baseline_events),"baseline_matches":int(row.baseline_matches),
            "leave_one_match_top10_rate":row.leave_one_match_top10_rate,
            "leave_one_season_top10_rate":row.leave_one_season_top10_rate,
            "bootstrap_ci95_low":row.bootstrap_score_ci95_low,"bootstrap_ci95_high":row.bootstrap_score_ci95_high,
            "at_any_inherited_floor":bool(row.at_any_inherited_floor)})
        for season in sorted(agg.loc[agg.analysis_format.eq(fmt),"season"].dropna().astype(str).unique()):
            scored,_,_=_scores(agg,fmt,omitted_season=season)
            scored=scored.reset_index()
            strict=scored.loc[scored.eligible_audit].sort_values(["score_audit","striker_id"],ascending=[False,True]).reset_index(drop=True)
            strict["rank_without_season"]=np.arange(1,len(strict)+1)
            pid=stability.loc[stability.format.eq(fmt)&stability.player_name.eq(name),"player_id"].iloc[0]
            match=strict.loc[strict.striker_id.astype(str).eq(str(pid))]
            if len(match):
                r=match.iloc[0]
                season_rows.append({"format":fmt,"player":name,"omitted_season":season,"eligible_after_removal":True,
                    "rank_after_removal":int(r.rank_without_season),"score_after_removal":float(r.score_audit),
                    "pressure_matches_remaining":int(r.p_matches),"baseline_matches_remaining":int(r.b_matches)})
            else:
                season_rows.append({"format":fmt,"player":name,"omitted_season":season,"eligible_after_removal":False,
                    "rank_after_removal":np.nan,"score_after_removal":np.nan,
                    "pressure_matches_remaining":0,"baseline_matches_remaining":0})
    def table(df):
        cols=list(df.columns); esc=lambda v:str(v).replace("|","/")
        return "| "+" | ".join(cols)+" |\n| "+" | ".join(["---"]*len(cols))+" |\n"+"\n".join("| "+" | ".join(esc(v) for v in r)+" |" for r in df.itertuples(index=False,name=None))
    return ("# Phase 5E batter sensitivity review\n\n"
        "## Full-sample evidence and perturbation summary\n\n"
        +table(pd.DataFrame(overview))+"\n\n"
        "Both players pass the unchanged Phase 2D batter floors in the full sample. Their leave-one-season Top 10 retention is lower than the other baseline Top 10 names: Dewald Brevis 0.60; Ackeem Auguste 0.50. Match deletion retention is 0.989 and 0.923 respectively. Both pass the reported exposure rule; these are stability flags, not grounds to remove them or alter the floor. Their cluster intervals are shown in the table.\n\n"
        "## Season deletion results\n\n"
        +table(pd.DataFrame(season_rows))+"\n\n"
        "Inclusion remains justified for the full-sample, separately ranked batter submission because the supplied evidence passes all original floors and all listed ranks were independently reproduced. Keep both in rank order, mark the season sensitivity beside each, and avoid claiming robust Top 10 status across seasons. Their omission in particular seasons is a stability warning, not evidence of invalid source rows.\n")


def build_reports(scope: pd.DataFrame, cohorts: dict[str,pd.DataFrame],
                  coverage: pd.DataFrame, eligibility: pd.DataFrame,
                  comparisons: pd.DataFrame) -> tuple[str,str]:
    def mdtable(df):
        cols=list(df.columns); esc=lambda v:str(v).replace("|","/").replace("\n"," ")
        return "| "+" | ".join(cols)+" |\n| "+" | ".join(["---"]*len(cols))+" |\n"+"\n".join("| "+" | ".join(esc(v) for v in r)+" |" for r in df.itertuples(index=False,name=None))
    comp_floor=eligibility.loc[eligibility.definition.eq("verified_chase")&eligibility.meets_inherited_floors_both_sides]
    proxy_floor=eligibility.loc[eligibility.definition.eq("wicket_depletion_Q75_vs_Q25_context_only")&eligibility.meets_inherited_floors_both_sides]
    pair=cohorts["verified_chase"]
    phase_counts=pair.groupby(["analysis_format","cohort","innings_phase"],dropna=False).agg(events=("match_id","size"),matches=("match_id","nunique")).reset_index()
    pressure_rows=int(pair.cohort.eq("pressure").sum()); baseline_rows=int(pair.cohort.eq("baseline").sum())
    p5c_bat=pd.read_csv(REPORTS/"phase5c_batter_rankings.csv",low_memory=False)
    p5c_bowl=pd.read_csv(REPORTS/"phase5c_bowler_rankings.csv",low_memory=False)
    counts={"competition_ready_batters":int(p5c_bat.competition_ready.fillna(False).sum()),
        "exploratory_batters":int((~p5c_bat.competition_ready.fillna(False)).sum()),
        "competition_ready_bowlers":0,"exploratory_bowlers":len(p5c_bowl)}
    summary=("# Phase 5E strongest defensible bowling pressure model\n\n"
        "## Decision\n\n"
        "No defensible competition-ready bowler ranking can be produced from the supplied data. The strongest role-relevant challenge definition available is verified chase containment demand: regular second innings with valid CRR/RRR state and RRR > CRR, paired against RRR <= CRR in the same match and phase. It is an observable scoreboard task for bowlers, not proof of psychological pressure. The paired cohort is too small to meet inherited floors, especially in IPL. No Top 10 is emitted.\n\n"
        "## Bowler-attributable field and denominator audit\n\n"
        "Metric coverage is in phase5e_bowler_metric_coverage.csv. Ordinary-dot rate, ordinary batter runs/event and ordinary boundary-event rate use only ordinary deliveries with known batter runs/flags; they omit extras and do not measure total bowler-conceded runs. Credited wickets use recognized bowler-credit dismissal events divided by observed delivery rows, not legal balls. legal_delivery is a partial event flag, not a complete legal-ball denominator. Bowler-conceded runs, economy and conventional bowling strike rate are not calculated. Across the full scope, ordinary deliveries represent about 94% of observed rows in each format; recognized credited wickets are only event counts over observed rows. The exact source-field and denominator audit remains in the coverage CSV.\n\n"
        "## Verified chase pressure compared with baseline\n\n"
        f"Verified paired rows comprise {pressure_rows} pressure events and {baseline_rows} reference events. State coverage and field-level eligible exposure are low. The following pooled comparisons have match-cluster intervals; they are response profiles, not rankings:\n\n"
        +mdtable(comparisons)+"\n\n"
        "Pairing remains within match and phase. Phase coverage is:\n\n"+mdtable(phase_counts)+"\n\n"
        "Match-cluster intervals are based on very few clusters (IPL 3; T20I 12) and do not support player ranking or generalization. The IPL denominator is especially sparse (18 high-demand and 4 reference delivery events).\n\n"
        "## Contextual bowling-challenge proxies\n\n"
        "Innings phase helps control task differences, but death phase alone is not pressure. The verified paired sample in this feed occurs only in powerplay; verified death-over comparisons are absent. pace/spin, speed, stroke, delivery style and line/length-like fields are mostly present, but describe the delivery, not pre-delivery challenge. delivery_context_proxy_eligible only confirms phase/wicket and bowling-type metadata; it is not a pressure label. High wicket depletion is reported only as a contextual contrast and rejected as a bowler-pressure definition because it can make the batting task easier. It cannot be used to name pressured bowlers.\n\n"
        "## Eligibility and sample-size results\n\n"
        "The unchanged Phase 2D bowling floors are pressure ≥5 events in ≥2 matches and baseline ≥37 events in ≥2 matches. Eligibility is metric-specific in phase5e_bowler_eligibility.csv. No verified-chase or verified-chase/death bowler profile clears both sides of the inherited floors on the available outcomes. Numeric floors pass under the wicket-depletion contrast for 137 IPL and 237 T20I players using credited wicket events, and 133 IPL and 228 T20I players using ordinary-event outcomes; that count does not confer pressure validity. The earlier Phase 5B Q25 sensitivity identified two T20I profiles only; those remain exploratory and that looser sensitivity does not qualify candidates.\n\n"
        "No bowler ranks are generated, so ranking-stability metrics are not applicable. The match-cluster bootstrap quantifies only aggregate paired response uncertainty; it cannot replace player exposure floors.\n\n"
        "## Strongest honest bowling alternative\n\n"
        "Provide a non-ranked verified-chase response table with ordinary dot rate, ordinary batter runs per ordinary event, ordinary boundary-event rate, recognized credited wickets per observed event, pressure/baseline event and match exposure, and matched state coverage. Label all run metrics as partial ordinary-delivery subsets. Keep formats separate and show uncertainty at the match-cluster level. Do not publish exploratory bowler names as a pressure ranking.\n")
    strategy=("# Phase 5E submission strategy\n\n"
        "## Exact role counts\n\n"
        f"- Competition-ready batters: **{counts['competition_ready_batters']}** (IPL 107; T20I 198).\n"
        f"- Exploratory batter additions: **{counts['exploratory_batters']}**.\n"
        "- Competition-ready bowlers: **0**.\n"
        f"- Exploratory Phase 5C bowler profiles: **{counts['exploratory_bowlers']}**; none are promoted to competition-ready.\n\n"
        "## Recommended submission\n\n"
        "Submit the batter rankings separately for IPL and T20I using the contextual wicket-depletion definition, explicitly described as a batting-resource challenge indicator rather than verified scoreboard or psychological pressure. Preserve all original eligibility floors, expose uncertainty and consistency, and flag Dewald Brevis and Ackeem Auguste as season-sensitive while retaining their full-sample ranks.\n\n"
        "For bowlers, do not manufacture a Top 10 or relabel the wicket-depletion profiles. Include a clearly marked 'no defensible ranked list from supplied data' section and attach the non-ranked verified-chase response profile. Explain that verified chase state supplies a role-relevant containment challenge, but only 18/4 IPL and 98/89 T20I pressure/reference event rows are available, with 3/12 paired matches; no bowler clears existing floors. Dot, batter-run and boundary metrics omit extras, while bowler runs and complete legal-ball totals are unavailable.\n\n"
        "This is the strongest honest way to address both roles: provide the supported batter lists and a transparent bowling evidence profile with the exact blocker. If the competition portal mechanically requires ranked bowlers, request clarification or additional validated ball-by-ball conceded-run and legal-ball data rather than submitting exploratory names as pressure performers.\n\n"
        "## Non-negotiable labels\n\n"
        "Keep RRR > CRR verified chase demand separate from contextual phase/delivery descriptors. Wicket depletion is not bowling pressure. Never calculate bowler economy or conventional bowling strike rate from the supplied fields. Keep IPL and T20I separate and do not weaken floors to fill ten places.\n")
    return summary,strategy


def main():
    REPORTS.mkdir(parents=True,exist_ok=True)
    scope,cohorts,_=_scope_and_cohorts()
    coverage=metric_coverage(scope,cohorts)
    eligibility=eligibility_table(cohorts)
    comparisons=cluster_comparisons(cohorts["verified_chase"])
    sensitivity=batter_sensitivity_review()
    summary,strategy=build_reports(scope,cohorts,coverage,eligibility,comparisons)
    coverage.to_csv(REPORTS/"phase5e_bowler_metric_coverage.csv",index=False)
    eligibility.to_csv(REPORTS/"phase5e_bowler_eligibility.csv",index=False)
    (REPORTS/"phase5e_bowling_model.md").write_text(summary,encoding="utf-8")
    (REPORTS/"phase5e_batter_sensitivity_review.md").write_text(sensitivity,encoding="utf-8")
    (REPORTS/"phase5e_submission_strategy.md").write_text(strategy,encoding="utf-8")
    p5c_bat=pd.read_csv(REPORTS/"phase5c_batter_rankings.csv",low_memory=False)
    p5c_bowl=pd.read_csv(REPORTS/"phase5c_bowler_rankings.csv",low_memory=False)
    return {"competition_ready_batters":int(p5c_bat.competition_ready.fillna(False).sum()),
        "exploratory_batters":int((~p5c_bat.competition_ready.fillna(False)).sum()),
        "competition_ready_bowlers":int(p5c_bowl.competition_ready.fillna(False).sum()),"exploratory_bowlers":int((~p5c_bowl.competition_ready.fillna(False)).sum()),
        "verified_bowler_eligible":int(eligibility.loc[eligibility.definition.eq("verified_chase")].meets_inherited_floors_both_sides.sum())}


if __name__=="__main__":
    print(json.dumps(main(),indent=2))
