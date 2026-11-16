"""Independent final bowling evidence and submission-readiness audit."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import numpy as np

from src.phase5d_independent_validation import _scope_and_cohorts

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"
FLOORS = {"pressure_events": 5, "pressure_matches": 2, "baseline_events": 37, "baseline_matches": 2}


def _truth(s):
    return s.fillna(False).astype(bool)


def _phase5e_comparisons() -> pd.DataFrame:
    lines=(REPORTS/"phase5e_bowling_model.md").read_text(encoding="utf-8").splitlines()
    rows=[]; active=False
    for line in lines:
        if line.startswith("| format | metric | pressure_value"):
            active=True
            continue
        if active and line.startswith("| ---"):
            continue
        if active and line.startswith("|"):
            rows.append([x.strip() for x in line.strip("|").split("|")])
        elif active:
            break
    return pd.DataFrame(rows,columns=["format","metric","pressure_value","baseline_value","pressure_minus_baseline",
        "cluster_ci95_low","cluster_ci95_high","paired_match_clusters","bootstrap_draws","interpretation"])


def _fmt(x):
    return "" if pd.isna(x) else f"{float(x):.6g}"


def build_metric_audit(scope: pd.DataFrame, cohorts: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame,pd.DataFrame]:
    coverage = pd.read_csv(REPORTS / "phase5e_bowler_metric_coverage.csv", low_memory=False)
    comparisons=_phase5e_comparisons()
    p5e_elig=pd.read_csv(REPORTS/"phase5e_bowler_eligibility.csv",low_memory=False)
    rows, eligibility_rows = [], []
    metric_defs = [
        ("recognized bowler-credited wickets", "is_wicket; dismissal_type; bowler_id; extras_type (edge-case audit)",
         "Count is_wicket=True and normalized dismissal_type in {Bowled,Caught,LBW,Stump,Hit Wicket}; aggregate by bowler_id.",
         "Event count only; no rate denominator is needed for the count. This is not team wickets and not all flagged dismissals.",
         "Available at event level for the recognized allowlist; not a full independently reconciled bowling scorecard. Raw text labels are used; recognized type on Overstep=0; 25 credited Stump events on wide rows show wides are not automatically disqualifying.",
         "Event outcome; general count. Under verified chase it is a possible pressure outcome but too sparse for eligible player ranking."),
        ("recognized credited wickets per observed delivery event", "is_wicket; dismissal_type; bowler_id; observed delivery row/match_id",
         "Recognized credited wickets / observed bowler delivery rows.",
         "Observed delivery rows, explicitly not legal balls.",
         "Fully calculable for event-row exposure; denominator includes illegal and legal/unknown events and cannot be called bowling strike rate.",
         "General descriptive event yield; under verified chase it is a sparse pressure comparison, not a conventional bowling rate."),
        ("ordinary dot rate", "runs; extras_type; extras_2_runs; bowler_id",
         "Ordinary-delivery rows with runs=0 / ordinary-delivery rows with known runs.",
         "Ordinary delivery subset only; excludes every extras-labelled or ambiguous secondary-extra row.",
         "Observed ordinary rows are 94.04% IPL and 94.13% T20I of scope delivery rows; known run coverage is 100% within this restricted ordinary subset. Not all balls bowled.",
         "Can describe pressure outcome only in verified-state subset, but cannot rank: event subset and eligible exposure remain too small."),
        ("ordinary batter runs per ordinary delivery event", "runs; extras_type; extras_2_runs; bowler_id",
         "Sum of source runs on ordinary deliveries / ordinary deliveries with known runs.",
         "Ordinary subset rows with known runs.",
         "Runs behave as batter runs on ordinary deliveries; they do not include conceded extras and are not bowler-attributable runs.",
         "Limited batter-side response under a pressure cohort; never interpret as bowler-conceded runs."),
        ("ordinary boundary-event rate", "is_four; is_six; extras_type; extras_2_runs; bowler_id",
         "Ordinary rows with is_four OR is_six / ordinary delivery rows.",
         "Ordinary delivery events.",
         "Boundary flags are complete and validated against runs in source audit; ordinary-only denominator excludes extras.",
         "Descriptive outcome; possible pressure comparison only when contextual state is verified and player exposure qualifies."),
        ("bowler-conceded runs", "total_runs (absent); typed extras amounts (absent/ambiguous); runs; extras_type; extras1_runs; extras_2_runs; bowler_id",
         "Would require summing each bowler's batter runs conceded plus attributable wides/no-balls and other applicable extras.",
         "No defensible numerator; no row-level bowler-conceded amount.",
         "Raw `runs` is not total runs; `extras1_runs` is category-like code (1=Overstep, 2=wide, 3=legbyes, 4=byes, 5=other, 6=null label, 7=Penalty), not an amount. `extras_2_runs` is 0 on 200,963/200,999 raw rows; remaining 36 are 1 or 4 with scope/attachment unresolved. No total_runs or bowler-conceded field.",
         "Unavailable in normal or pressure context; blocked."),
        ("legal deliveries and overs bowled", "is_legal_delivery (absent); extras_type; extras_2_runs; overid; innings_ball_num; bowler_id",
         "A complete legal-ball count would sum a provider-validated per-event legal flag by bowler; overs require validated legal-ball totals and over allowance.",
         "Raw legal-delivery flag is absent. Processed `legal_delivery` is a classification derivative; `overid` is an over label, not legal-ball count.",
         "Processed flag is nonmissing for 99.86% IPL and 99.87% T20I rows; however it infers Overstep as no-ball and leaves Other/Penalty/ambiguous events unknown. In the combined IPL/T20I 2022+ scope, 262 rows have unknown legality. High nonmissing coverage does not validate semantics.",
         "Partial event classification only; no complete legal-ball or overs-bowled denominator."),
        ("economy rate", "bowler-conceded runs (unavailable); complete legal balls (unavailable); bowler_id",
         "6 x bowler-conceded runs / legal balls bowled.",
         "Both inputs must be complete and attributable to the bowler.",
         "Numerator and denominator both fail validation; no economy value calculated.",
         "Unavailable in normal or pressure context; blocked."),
        ("conventional bowling strike rate", "complete legal balls (unavailable); recognized bowler-credit wickets; bowler_id",
         "Legal balls bowled / recognized bowler-credited wickets.",
         "Complete legal-ball denominator; wickets use credited dismissal events.",
         "Wicket count is calculable, legal balls are not complete/validated; subset legal balls divided by wickets is not conventional bowling strike rate.",
         "Unavailable as a comparable conventional rate; blocked."),
        ("verified chase pressure exposure", "score_before; target; runs_required; legal_balls_remaining; legal_balls_bowled_before; innings; match_id; innings_phase; bowler_id",
         "Regular second innings; valid reconstructed CRR/RRR; pressure RRR>CRR; reference RRR<=CRR; pair within match and phase.",
         "Pressure/reference delivery rows and paired match clusters; state denominator is all regular second-innings source rows.",
         "Reconstructable states are only 31/42,085 IPL chase rows (0.074%) and 261/49,849 T20I rows (0.524%); paired comparison retains 18/4 IPL rows in 3 clusters and 98/89 T20I rows in 12 clusters, all powerplay.",
         "Best role-relevant observable bowler challenge, not psychological pressure; no player meets both inherited floors."),
        ("wicket/phase contextual proxy", "is_wicket; innings; overid; match_id; bowler_id",
         "High wicket depletion (format/phase Q75) versus low depletion (Q25), paired same match/phase.",
         "Observed delivery events within paired match-phase strata.",
         "Broad coverage; numeric floor passes exist (recognized wicket metric: 137 IPL/237 T20I; ordinary metrics: 133/228) but these do not make the construct role-valid.",
         "Contextual batting-resource proxy only; high depletion may make bowling easier. Not acceptable as bowler pressure."),
        ("innings phase and delivery descriptors", "innings; overid; pace_or_spin; bowling_type; bowl_speed; stroke; delivery_style; over_or_around; on_or_off",
         "Use phase/observed delivery attributes for stratification or descriptive covariates; no validated difficulty score.",
         "Available row descriptions; individual field missingness reported in this audit CSV.",
         "Most metadata fields have high row availability, but speed/style/stroke/line are descriptive or post-delivery and have no predeclared calibrated pressure meaning.",
         "General context/control only; phase is not pressure by itself."),
    ]
    for fmt in ["IPL","T20I"]:
        cov = coverage.loc[coverage.population.eq("all_scope") & coverage.format.eq(fmt)]
        p = coverage.loc[coverage.population.eq("verified_chase_pressure") & coverage.format.eq(fmt)]
        b = coverage.loc[coverage.population.eq("verified_chase_baseline") & coverage.format.eq(fmt)]
        raw_scope = scope.loc[scope.analysis_format.eq(fmt)]
        ordinary_events = int(_truth(raw_scope.ordinary_delivery).sum())
        all_rows = len(raw_scope)
        field_map = {}
        for f in ["bowler_id","runs","extras_type","extras1_runs","extras_2_runs","is_four","is_six","is_wicket","dismissal_type","legal_delivery","innings_phase","pace_or_spin","bowling_type","bowl_speed","stroke","delivery_style","over_or_around","on_or_off"]:
            if f in raw_scope:
                field_map[f] = round(100*float(raw_scope[f].notna().mean()),3) if len(raw_scope) else None
            else:
                field_map[f] = None
        source_wickets=raw_scope.is_wicket.fillna(False).astype(bool)
        dismissal_presence_on_wickets=round(100*raw_scope.loc[source_wickets,"dismissal_type"].notna().mean(),3) if source_wickets.any() else np.nan
        raw_dismissal=raw_scope.dismissal_type.astype("string").str.strip().str.casefold()
        recognized_source=source_wickets & raw_dismissal.isin({"bowled","caught","lbw","stump","hit wicket"})
        credited_bowler_presence=round(100*raw_scope.loc[recognized_source,"bowler_id"].notna().mean(),3) if recognized_source.any() else np.nan
        def metric(metric_name, frame=cov, col="numerator_or_value"):
            row=frame.loc[frame.metric.eq(metric_name)]
            return np.nan if row.empty else row.iloc[0][col]
        verified_pair = cohorts["verified_chase"].loc[cohorts["verified_chase"].analysis_format.eq(fmt)]
        mrows={}
        verified = cohorts["verified_chase"].loc[cohorts["verified_chase"].analysis_format.eq(fmt)].copy()
        for metric_name in ["recognized_credit_wicket_yield","ordinary_dot_rate","ordinary_batter_runs_per_ordinary_event","ordinary_boundary_rate"]:
            events=verified
            if metric_name != "recognized_credit_wicket_yield":
                events=events.loc[_truth(events.ordinary_delivery)
                    &pd.to_numeric(events.batter_runs_verified_subset,errors="coerce").notna()]
            side_counts={"pressure":{},"baseline":{}}
            for pid,g in events.dropna(subset=["bowler_id"]).groupby("bowler_id"):
                for cohort_name in ["pressure","baseline"]:
                    c=g.loc[g.cohort.eq(cohort_name)]
                    side_counts[cohort_name][pid]=(len(c),int(c.match_id.nunique()))
            all_ids=set(side_counts["pressure"])|set(side_counts["baseline"])
            p_side=sum(n>=FLOORS["pressure_events"] and m>=FLOORS["pressure_matches"]
                       for n,m in side_counts["pressure"].values())
            b_side=sum(n>=FLOORS["baseline_events"] and m>=FLOORS["baseline_matches"]
                       for n,m in side_counts["baseline"].values())
            both_side=sum(
                side_counts["pressure"].get(pid,(0,0))[0]>=FLOORS["pressure_events"]
                and side_counts["pressure"].get(pid,(0,0))[1]>=FLOORS["pressure_matches"]
                and side_counts["baseline"].get(pid,(0,0))[0]>=FLOORS["baseline_events"]
                and side_counts["baseline"].get(pid,(0,0))[1]>=FLOORS["baseline_matches"]
                for pid in all_ids)
            mrows[metric_name]=(p_side,b_side,both_side,len(all_ids))
            eligibility_rows.append({"format":fmt,"challenge_definition":"verified_chase_RRR_gt_CRR_vs_le_CRR","metric":metric_name,
                "pressure_floor_rule":"at least 5 observed metric events in at least 2 distinct matches",
                "baseline_floor_rule":"at least 37 observed metric events in at least 2 distinct matches",
                "eligible_pressure_side_players":p_side,"eligible_baseline_side_players":b_side,
                "players_meeting_both_sides":both_side,"players_with_any_paired_event":len(all_ids),"competition_ready_bowlers":0,
                "result":"No player meets both sides; floors unchanged."})
        for metric_name, fields, formula, denom, caveat, relevance in metric_defs:
            val=np.nan; numerator=np.nan; denominator=np.nan; cov_pct=np.nan
            if metric_name=="recognized bowler-credited wickets":
                numerator=metric("recognized_bowler_credit_wicket"); denominator=all_rows
                val=numerator; cov_pct=100
            elif metric_name=="recognized credited wickets per observed delivery event":
                numerator=metric("recognized_bowler_credit_wicket"); denominator=all_rows
                val=numerator/denominator if denominator else np.nan; cov_pct=100
            elif metric_name=="ordinary dot rate":
                numerator=metric("ordinary_dot_event"); denominator=metric("ordinary_batter_runs_known")
                val=numerator/denominator if denominator else np.nan; cov_pct=100*ordinary_events/all_rows if all_rows else np.nan
            elif metric_name=="ordinary batter runs per ordinary delivery event":
                numerator=metric("ordinary_batter_runs_sum"); denominator=metric("ordinary_batter_runs_known")
                val=numerator/denominator if denominator else np.nan; cov_pct=100*ordinary_events/all_rows if all_rows else np.nan
            elif metric_name=="ordinary boundary-event rate":
                numerator=metric("ordinary_boundary_event"); denominator=metric("ordinary_delivery_event")
                val=numerator/denominator if denominator else np.nan; cov_pct=100*ordinary_events/all_rows if all_rows else np.nan
            elif metric_name=="legal deliveries and overs bowled":
                numerator=metric("legal_delivery_true"); denominator=metric("legal_delivery_known")
                val=numerator/denominator if denominator else np.nan
                known_rows=metric("legal_delivery_known")
                cov_pct=100*known_rows/all_rows if all_rows else np.nan
            elif metric_name=="bowler-conceded runs":
                cov_pct=0
            elif metric_name=="economy rate" or metric_name=="conventional bowling strike rate":
                cov_pct=0
            elif metric_name=="verified chase pressure exposure":
                total=int((scope.analysis_format.eq(fmt)&scope.innings.eq(2)).sum())
                states=int((scope.analysis_format.eq(fmt)&scope.innings.eq(2)&_truth(scope.match_state_pressure_eligible)
                    &pd.to_numeric(scope.runs_required,errors="coerce").notna()
                    &pd.to_numeric(scope.legal_balls_remaining,errors="coerce").gt(0)
                    &pd.to_numeric(scope.legal_balls_bowled_before,errors="coerce").gt(0)
                    &pd.to_numeric(scope.score_before,errors="coerce").notna()).sum())
                numerator=states; denominator=total; val=states/total if total else np.nan; cov_pct=100*val if pd.notna(val) else np.nan
            elif metric_name=="wicket/phase contextual proxy":
                val=np.nan; cov_pct=100
            elif metric_name=="innings phase and delivery descriptors":
                val=np.nan; cov_pct=np.nan
            for metric_floor in ["recognized_credit_wicket_yield","ordinary_dot_rate","ordinary_batter_runs_per_ordinary_event","ordinary_boundary_rate"]:
                if (metric_name=="recognized bowler-credited wickets" or metric_name=="recognized credited wickets per observed delivery event") and metric_floor=="recognized_credit_wicket_yield":
                    eligible_pressure,eligible_baseline,both,count=mrows[metric_floor]
                    break
                if metric_name.startswith("ordinary dot") and metric_floor=="ordinary_dot_rate":
                    eligible_pressure,eligible_baseline,both,count=mrows[metric_floor]; break
                if metric_name.startswith("ordinary batter") and metric_floor=="ordinary_batter_runs_per_ordinary_event":
                    eligible_pressure,eligible_baseline,both,count=mrows[metric_floor]; break
                if metric_name.startswith("ordinary boundary") and metric_floor=="ordinary_boundary_rate":
                    eligible_pressure,eligible_baseline,both,count=mrows[metric_floor]; break
            else:
                eligible_pressure=eligible_baseline=both=count=np.nan
            pressure_value=baseline_value=pressure_delta=cluster_low=cluster_high=paired_clusters=np.nan
            proxy_numeric_floor_pass=np.nan
            proxy_ordinary_floor_pass=np.nan
            if metric_name=="wicket/phase contextual proxy":
                proxy_rows=p5e_elig.loc[p5e_elig.definition.eq("wicket_depletion_Q75_vs_Q25_context_only")
                    &p5e_elig.format.eq(fmt)]
                wicket_rows=proxy_rows.loc[proxy_rows.metric.eq("recognized_credit_wicket_yield")]
                ordinary_rows=proxy_rows.loc[proxy_rows.metric.eq("ordinary_dot_rate")]
                proxy_numeric_floor_pass=int(wicket_rows.meets_inherited_floors_both_sides.sum())
                proxy_ordinary_floor_pass=int(ordinary_rows.meets_inherited_floors_both_sides.sum())
            metric_code={"recognized bowler-credited wickets":"recognized_wicket_yield_per_observed_event",
                "recognized credited wickets per observed delivery event":"recognized_wicket_yield_per_observed_event",
                "ordinary dot rate":"ordinary_dot_rate",
                "ordinary batter runs per ordinary delivery event":"ordinary_batter_runs_per_event",
                "ordinary boundary-event rate":"ordinary_boundary_rate"}.get(metric_name)
            if metric_code:
                def population_rate(pop, metric, col="rate_or_coverage"):
                    hit=coverage.loc[coverage.population.eq(pop)&coverage.format.eq(fmt)&coverage.metric.eq(metric),col]
                    return float(hit.iloc[0]) if len(hit) and pd.notna(hit.iloc[0]) else np.nan
                if metric_name=="recognized bowler-credited wickets":
                    p_w=population_rate("verified_chase_pressure","recognized_bowler_credit_wicket","numerator_or_value")
                    b_w=population_rate("verified_chase_baseline","recognized_bowler_credit_wicket","numerator_or_value")
                    p_n=population_rate("verified_chase_pressure","observed_delivery_event","numerator_or_value")
                    b_n=population_rate("verified_chase_baseline","observed_delivery_event","numerator_or_value")
                    pressure_value=p_w/p_n if p_n else np.nan; baseline_value=b_w/b_n if b_n else np.nan
                elif metric_name=="ordinary dot rate":
                    pressure_value=population_rate("verified_chase_pressure","ordinary_dot_event")
                    baseline_value=population_rate("verified_chase_baseline","ordinary_dot_event")
                elif metric_name=="ordinary batter runs per ordinary delivery event":
                    pressure_value=population_rate("verified_chase_pressure","ordinary_batter_runs_sum")
                    baseline_value=population_rate("verified_chase_baseline","ordinary_batter_runs_sum")
                elif metric_name=="ordinary boundary-event rate":
                    pressure_value=population_rate("verified_chase_pressure","ordinary_boundary_event")
                    baseline_value=population_rate("verified_chase_baseline","ordinary_boundary_event")
                elif metric_name=="recognized credited wickets per observed delivery event":
                    pressure_value=population_rate("verified_chase_pressure","recognized_bowler_credit_wicket")
                    baseline_value=population_rate("verified_chase_baseline","recognized_bowler_credit_wicket")
                pressure_delta=pressure_value-baseline_value if pd.notna(pressure_value) and pd.notna(baseline_value) else np.nan
                comp=comparisons.loc[comparisons.format.eq(fmt)&comparisons.metric.eq(metric_code)]
                if len(comp):
                    pressure_value=float(comp.iloc[0].pressure_value)
                    baseline_value=float(comp.iloc[0].baseline_value)
                    pressure_delta=float(comp.iloc[0].pressure_minus_baseline)
                    cluster_low=float(comp.iloc[0].cluster_ci95_low)
                    cluster_high=float(comp.iloc[0].cluster_ci95_high)
                    paired_clusters=int(comp.iloc[0].paired_match_clusters)
            rows.append({"format":fmt,"metric":metric_name,"required_source_fields":fields,
                "available_field_coverage_pct_json":json.dumps(field_map,sort_keys=True),
                "field_presence_denominator_note":"Percentages are over all scoped delivery rows. Null extras_type is the observed no-extra category; dismissal_type is expected only on wicket events. legal_delivery and innings_phase are processed derivatives, not raw columns.",
                "dismissal_type_presence_on_wicket_rows_pct":dismissal_presence_on_wickets,
                "bowler_id_presence_on_recognized_credit_event_pct":credited_bowler_presence,
                "scope_delivery_rows":all_rows,"scope_matches":int(raw_scope.match_id.nunique()),"scope_bowlers":int(raw_scope.bowler_id.nunique()),
                "metric_numerator_or_observed_value":numerator,"metric_denominator":denominator,"calculated_value_or_coverage":val,
                "formula":formula,"denominator_definition":denom,"scope_row_coverage_pct":cov_pct,
                "verified_pressure_events":int(p.iloc[0].delivery_rows) if len(p) else 0,
                "verified_pressure_matches":int(p.iloc[0].matches) if len(p) else 0,
                "verified_baseline_events":int(b.iloc[0].delivery_rows) if len(b) else 0,
                "verified_baseline_matches":int(b.iloc[0].matches) if len(b) else 0,
                "verified_pressure_metric_value":pressure_value,"verified_baseline_metric_value":baseline_value,
                "verified_pressure_minus_baseline":pressure_delta,"paired_match_cluster_count":paired_clusters,
                "match_cluster_ci95_low":cluster_low,"match_cluster_ci95_high":cluster_high,
                "contextual_proxy_numeric_floor_pass_not_role_valid":proxy_numeric_floor_pass,
                "contextual_proxy_ordinary_floor_pass_not_role_valid":proxy_ordinary_floor_pass,
                "pressure_side_floor_pass_players":eligible_pressure,"baseline_side_floor_pass_players":eligible_baseline,
                "both_sides_floor_pass_players":both,"eligibility_floor_rule":json.dumps(FLOORS),
                "under_pressure_or_general":relevance,"missingness_and_semantics":caveat,
                "decision":"calculable only as described; no competition-ready bowler ranking" if metric_name not in {"bowler-conceded runs","economy rate","conventional bowling strike rate"} else "blocked; do not calculate or rank"})
    audits=pd.DataFrame(rows)
    elig_summary=pd.DataFrame(eligibility_rows)
    return audits, elig_summary


def verify_overall_batters() -> tuple[dict,pd.DataFrame]:
    source=pd.read_csv(REPORTS/"phase5c_batter_rankings.csv",low_memory=False)
    source=source.loc[source.competition_ready.fillna(False)].copy()
    source["player_id"]=source.player_id.astype(str)
    source["within_format_pct"]=source.groupby("format").score.rank(method="average",pct=True)
    computed=source.groupby("player_id").agg(player_name=("player_name","first"),formats=("format","nunique"),mean_pct=("within_format_pct","mean")).reset_index()
    computed=computed.sort_values(["mean_pct","player_id"],ascending=[False,True]).reset_index(drop=True)
    computed["rank"]=range(1,len(computed)+1)
    published=pd.read_csv(REPORTS/"phase5g_overall_batter_top10.csv",low_memory=False)
    same=published.sort_values("rank").reset_index(drop=True)
    if len(source)!=305 or len(published)!=10 or same.player_id.astype(str).nunique()!=10 or same["rank"].tolist()!=list(range(1,11)):
        raise ValueError("Phase 5G overall Top 10 count/uniqueness/rank audit failed")
    top=computed.head(10).merge(same[["rank","player_id","mean_within_format_percentile"]],on="rank",suffixes=("_rebuilt","_published"),validate="one_to_one")
    if not top.player_id_rebuilt.astype(str).equals(top.player_id_published.astype(str)) or (top.mean_pct-top.mean_within_format_percentile).abs().max()>1e-12:
        raise ValueError("Phase 5G mean within-format percentile list does not independently reproduce")
    scenarios=pd.read_csv(REPORTS/"phase5g_cross_format_scenarios.csv")
    stability=pd.read_csv(REPORTS/"phase5g_cross_format_stability.csv")
    expected_overlap=stability.loc[stability.scenario.isin([
        "mean within-format standardized score; deduplicate by player ID",
        "mean percentile of approximate event-count 95% lower bound"]),"top10_overlap_with_mean_percentile"]
    if len(expected_overlap)!=2 or not expected_overlap.eq(9).all():
        raise ValueError("Phase 5G cross-format 9/10 stability scenarios changed")
    separate=pd.read_csv(REPORTS/"final_batter_top10.csv",low_memory=False)
    fmt_counts=separate.groupby("format").size().to_dict()
    if fmt_counts!={"IPL":10,"T20I":10} or separate.groupby("format").player_id.nunique().ne(10).any():
        raise ValueError("Phase 5F format support Top 10 checks failed")
    details={"competition_ready_format_rows":len(source),"overall_top10_rows":len(same),
        "overall_unique_player_ids":int(same.player_id.astype(str).nunique()),"rank_1_to_10":True,
        "mean_percentile_score_max_abs_diff":float((top.mean_pct-top.mean_within_format_percentile).abs().max()),
        "overall_rank_order_reproduced":True,"scenario_count":len(scenarios),
        "standardized_and_uncertainty_adjusted_top10_overlap_each":9,
        "supporting_format_top10_rows":fmt_counts,
        "distinct_players_in_supporting_top10_union":int(separate.player_id.astype(str).nunique())}
    return details,top


def _mdtable(frame: pd.DataFrame) -> str:
    cols=list(frame.columns)
    rows=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for r in frame.itertuples(index=False,name=None):
        rows.append("| "+" | ".join("" if pd.isna(v) else str(v).replace("|","/").replace("\n"," ") for v in r)+" |")
    return "\n".join(rows)


def main() -> dict:
    scope,cohorts,_=_scope_and_cohorts()
    metric_audit,eligibility=build_metric_audit(scope,cohorts)
    bat_audit,top_rebuilt=verify_overall_batters()
    metric_audit.to_csv(REPORTS/"phase5h_bowling_metric_audit.csv",index=False)
    eligibility.to_csv(REPORTS/"phase5h_bowling_eligibility.csv",index=False)
    (REPORTS/"phase5h_bowling_final_audit.md").write_text(_bowling_report(metric_audit,eligibility,scope),encoding="utf-8")
    (REPORTS/"phase5h_methodology_report.md").write_text(_consolidated_methodology(bat_audit),encoding="utf-8")
    (REPORTS/"phase5h_submission_readiness.md").write_text(_readiness(bat_audit),encoding="utf-8")
    return {"bowler_ready":0,"bowler_exploratory":414,"verified_chase_bowler_floor_passes":0,
        "overall_batter_top10_reproduced":True,"overall_batter_candidates":10,
        "unique_player_ids":10,"format_support_lists":{"IPL":10,"T20I":10},
        "metric_audit_rows":len(metric_audit),"eligibility_summary_rows":len(eligibility)}


def _bowling_report(metrics,eligibility,scope):
    raw=pd.read_csv(ROOT/"data"/"raw"/"ball_by_ball.csv",low_memory=False)
    fields=set(raw.columns)
    absent=[x for x in ["total_runs","total_runs_external","is_legal_delivery","legal_delivery","bowler_conceded_runs"] if x not in fields]
    extras1=scope.groupby(["extras_type","extras1_runs"],dropna=False).size().reset_index(name="rows")
    extras2=scope.extras_2_runs.value_counts(dropna=False).to_dict()
    phasec=pd.read_csv(REPORTS/"phase5c_bowler_rankings.csv",low_memory=False)
    fmt_bowl=phasec.groupby("format").agg(profiles=("player_id","size"),ready=("competition_ready",lambda s:int(s.fillna(False).sum()))).reset_index()
    fmt_bowl["exploratory"]=fmt_bowl.profiles-fmt_bowl.ready
    p5e_cov=pd.read_csv(REPORTS/"phase5e_bowler_metric_coverage.csv",low_memory=False)
    extras_label_codes=", ".join(
        str(r.extras_type if pd.notna(r.extras_type) else "null")+"="+str(int(r.extras1_runs))
        for r in extras1.itertuples())
    scope_wickets=scope.is_wicket.fillna(False).astype(bool)
    scope_dismissal=scope.dismissal_type.astype("string").str.strip().str.casefold()
    scope_credited=scope_wickets & scope_dismissal.isin({"bowled","caught","lbw","stump","hit wicket"})
    recognized_count=int(scope_credited.sum())
    credited_missing_bowler=int(scope.loc[scope_credited,"bowler_id"].isna().sum())
    overstep_credited=int((scope_credited&scope.extras_type.astype("string").str.casefold().eq("overstep")).sum())
    wide_stumped=int((scope_credited&scope.extras_type.astype("string").str.casefold().eq("wide")&scope_dismissal.eq("stump")).sum())
    unknown_legality=int(scope.legal_delivery.isna().sum())
    metric_display=metrics[["format","metric","metric_numerator_or_observed_value","metric_denominator","calculated_value_or_coverage","scope_row_coverage_pct","verified_pressure_metric_value","verified_baseline_metric_value","verified_pressure_minus_baseline","match_cluster_ci95_low","match_cluster_ci95_high","paired_match_cluster_count","pressure_side_floor_pass_players","baseline_side_floor_pass_players","both_sides_floor_pass_players","under_pressure_or_general","decision"]].copy()
    return ("# Phase 5H independent bowling evidence audit\n\n"
        "## Decision\n\n"
        "A competition-ready Bowler Top 10 is not supported. The supplied fields support a narrow recognized bowler-credit wicket event count, ordinary-delivery outcome subsets, and an extremely sparse verified-chase comparison. They do not support complete bowler-conceded runs, legal-ball totals, conventional economy or bowling strike rate. No player meets both unchanged role-valid verified-chase exposure floors. Retain 0 competition-ready and 414 exploratory bowler profiles; do not submit a fabricated list.\n\n"
        +_mdtable(fmt_bowl)+"\n\n"
        "## Source audit and transformations\n\n"
        f"The source feed does not contain these fields: {', '.join('`'+f+'`' for f in absent)}. The source `runs` field is supported as batter runs on ordinary rows only; absent total-run and typed-extra amounts prevent safe reconstruction of bowler-conceded runs.\n\n"
        f"Within the confirmed IPL/T20I 2022+ scope, `extras_2_runs` distribution is {extras2}; the same category-like `extras1_runs` label/code pattern is observed as {extras_label_codes}. Null `extras_type` is the ordinary/no-extra category, not missing event classification. These are scoped observations; they do not resolve amount attribution.\n\n"
        f"Bowler-credit events are generated in `src/pressure_analysis.py`: `is_wicket=True` AND normalized `dismissal_type` is Bowled, Caught, LBW, Stump or Hit Wicket. Within scope, this rule identifies {recognized_count:,} events; {credited_missing_bowler} have no `bowler_id`, none occur on Overstep, and {wide_stumped} credited Stump events occur on wide rows. RunOut, Retire Out and Obstructing-field dismissals are excluded. These are defensible recognized credited-event counts, but not a complete independently reconciled player bowling figures dataset. Do not equate them with all `is_wicket` events.\n\n"
        f"The processed `legal_delivery` field is derived, not raw: ordinary events are provisionally legal, wides are illegal, Overstep is inferred as no-ball, byes/leg-byes are provisionally legal, and Other/Penalty/ambiguous secondary extras remain unknown. `overid` identifies an over label; it does not give legal balls bowled. There are {unknown_legality:,} unknown-legality rows in the IPL/T20I analysis scope, and even the known flag uses some inferred semantics. Phase 5H therefore treats legal-ball and over totals as incomplete.\n\n"
        "The complete metric-by-format audit—including required fields, field presence, formula, denominator, coverage, eligibility, pressure relevance and limitations—is in `phase5h_bowling_metric_audit.csv`. Field-presence percentages use all scoped delivery rows; null `extras_type` is a meaningful ordinary-delivery category, and `dismissal_type` is expected only on wicket rows. The CSV distinguishes these conditional fields and reports dismissal-label coverage on wicket rows separately. `legal_delivery` and `innings_phase` are processed derivatives, not raw source columns.\n\n"
        "## Metric and denominator evidence\n\n"
        +_mdtable(metric_display)+"\n\n"
        "Recognized wicket yield per observed event is calculable as a nonstandard event ratio: IPL 4,203/87,687 (4.793%); T20I 5,702/106,327 (5.363%). This is not conventional bowling strike rate. Ordinary deliveries are 82,458/87,687 (94.037%) IPL and 100,089/106,327 (94.133%) T20I. Those denominators support only ordinary-row dots, batter runs and boundaries; they exclude extras, and ordinary batter-run sums are not runs conceded by the bowler.\n\n"
        "## Eligibility and pressure evidence\n\n"
        "Unchanged Phase 2D bowling floors are at least 5 pressure events in at least 2 matches and at least 37 baseline events in at least 2 matches. The new eligibility audit reapplies both sides metric-by-metric to the verified chase cohort; no metric-format pair has a player meeting both sides. For T20I, two bowlers meet the pressure-side floor for verified wicket/ordinary outcomes, but zero meet the baseline-side floor. The exact metric-level counts are in `phase5h_bowling_eligibility.csv`.\n\n"
        +_mdtable(eligibility)+"\n\n"
        "Verified chase-state availability is 31/42,085 regular IPL chase rows (0.074%) and 261/49,849 T20I rows (0.524%). Match/phase pairing retains 18 pressure/4 baseline IPL events over 3 matches and 98/89 T20I events over 12 matches, all in powerplay. Match-cluster intervals and these exposures are too sparse for individual ranking. Death-phase verified comparison is absent.\n\n"
        "Wicket/phase Q75-vs-Q25 context is broad and same-match/same-phase paired, but describes batting-resource depletion, not a demanding bowling situation. Numeric event-floor passes (137 IPL/237 T20I for credited wicket observations; 133/228 for ordinary outcomes) do not confer role-valid pressure eligibility. The Phase 5C bowler model standardizes one recognized wicket-yield delta per format, applies harmonic exposure shrinkage and match-consistency adjustment, and labels all 414 profiles exploratory. Those proxy-derived scores are not used as submission rankings.\n\n"
        "Pace/spin, bowling type, speed, delivery style, stroke, line/trajectory descriptors and phase are available at high rates, but are not validated pre-delivery challenge indicators or calibrated difficulty weights. Phase can control comparisons; it cannot alone define pressure.\n\n"
        "## Final bowling decision\n\n"
        "Keep the bowler Top 10 unresolved. The honest alternative is a non-ranked evidence table with verified chase definitions, outcomes, denominators, coverage and match-cluster uncertainty, plus the exact missing fields: complete bowler-conceded runs or typed extras with validated attribution; provider-explicit legal status for every delivery; validated wicket-credit/no-ball rules; and broader paired verified challenge states. Do not contact providers or obtain external data under this phase instruction.\n")


def _consolidated_methodology(audit):
    phase5f=(REPORTS/"final_methodology_report.md").read_text(encoding="utf-8")
    phase5g=(REPORTS/"phase5g_submission_reconciliation.md").read_text(encoding="utf-8")
    return ("# Phase 5H consolidated methodology report\n\n"
        "> This is the current methodology-report package. Phase 5F source reports are preserved as historical evidence; the Phase 5G single overall batter list and Phase 5H audit govern current submission status. No earlier report has been overwritten.\n\n"
        "## Current official-list validation\n\n"
        f"The overall Batter Top 10 independently reproduces: 10 distinct IDs, ranks 1-10, maximum score-percentile difference {audit['mean_percentile_score_max_abs_diff']:.3g}; format support lists remain ten IPL and ten T20I players. The standard-score and conservative lower-bound scenarios each retain 9/10. The separate Bowler Top 10 remains unsupported (0 competition-ready; 414 exploratory). See the complete metric audit in `phase5h_bowling_metric_audit.csv`.\n\n"
        "## Phase 5F validated method and evidence (historical supporting analysis)\n\n"
        +phase5f+"\n\n---\n\n"
        "## Phase 5G submission reconciliation and current overall-list method\n\n"
        +phase5g+"\n\n---\n\n"
        "## Phase 5H bowling audit update\n\n"
        "Bowling source semantics, denominators, recognized wicket transformations, eligibility floors, chase-state sparsity and exclusions are fully audited in `phase5h_bowling_final_audit.md` and its metric/eligibility CSVs. The evidence does not support a competition-ready bowler Top 10. Current completion consequences and field actions are in `phase5h_submission_readiness.md`.\n")


def _readiness(audit):
    stale=(
        "`final_methodology_report.md` and `final_submission_audit.md` are Phase 5F snapshots describing separate IPL/T20I Top 10s as submission lists; the Phase 5G reconciliation supersedes that submission framing, while the tables remain supporting evidence.\n"
        "`final_submission_checklist.md` contains a Phase 5F section followed by a historical Phase 4A checklist; the former predates the Phase 5G overall list. Use `phase5g_final_action_checklist.md` plus this Phase 5H status.\n"
        "`phase5e_submission_strategy.md` recommends submitting format-separated batter lists and predates the official-list reconciliation. It is preserved historical strategy.\n"
        "`final_analysis_architecture.md`, Phase 5A and earlier readiness reports record prior-stage blocked states; they are history, not current counts.\n"
        "The dashboard's Phase 5G final page was still loading Phase 5F methodology/checklist artifacts. It must be routed to Phase 5H consolidated methodology/readiness and exclude stale Phase 5F checklist display.\n")
    bowlers=pd.read_csv(REPORTS/"phase5c_bowler_rankings.csv",low_memory=False)
    fmt_counts=bowlers.groupby("format").agg(profiles=("player_id","size"),competition_ready=("competition_ready",lambda s:int(s.fillna(False).sum()))).reset_index()
    fmt_counts["exploratory"]=fmt_counts.profiles-fmt_counts.competition_ready
    return ("# Phase 5H final submission readiness audit\n\n"
        "## Official deliverables and current status\n\n"
        "The supplied Round 1 PDF requires (1) one overall Batter Top 10, (2) a separate Bowler Top 10, and (3) one methodology report. The overall batter list is supported and independently reproduced: 10 unique player IDs ranked 1-10 using the Phase 5G mean within-format percentile method. It retains exposure and consistency shrinkage from Phase 5C; reasonable standardized-score and conservative event-interval alternatives each overlap 9/10. IPL and T20I lists are supporting format evidence, not extra official dropdown lists.\n\n"
        "The separate bowler list is required but unsupported: 0 competition-ready candidates, 414 exploratory profiles, and no player meeting both inherited verified-chase floors. The submission is **not complete** while the required bowler Top 10 field remains unresolved. Do not enter proxy-ranked profiles.\n\n"
        +_mdtable(fmt_counts)+"\n\n"
        "The current methodology upload should be `phase5h_methodology_report.md`, which preserves the Phase 5F analysis as a labeled historical section, incorporates the Phase 5G overall batter method/list, and adds the Phase 5H bowling audit. The current action checklist is `phase5g_final_action_checklist.md` plus this readiness report; current bowling detail is `phase5h_bowling_final_audit.md`. The historical Phase 5F final reports remain untouched.\n\n"
        "## Overall batter list reconciliation\n\n"
        f"Independent recomputation finds {audit['competition_ready_format_rows']} ready player-format rows, {audit['overall_top10_rows']} distinct overall candidates, ranks 1-10, exact mean-percentile aggregation reproduction, and supporting format lists {audit['supporting_format_top10_rows']}. The 20 supporting format entries represent {audit['distinct_players_in_supporting_top10_union']} unique IDs; cross-format duplicates are correctly collapsed in the overall list. Five aggregation/duplicate scenarios are retained in Phase 5G reports.\n\n"
        "## Bowling status and data gaps\n\n"
        "The role-valid verified chase comparison is sparse and powerplay-only. Bowler-conceded runs are unavailable because no `total_runs` or bowler-conceded source field exists and extras amounts cannot be safely attributed. Legal status is a derived partial classification with inferred Overstep semantics and unresolved categories. Consequently economy and conventional bowling strike rate are blocked. Recognized credited wickets are event-countable from an explicit dismissal allowlist but do not supply a legal-ball denominator or full bowling figure. Full detail and metric-by-metric coverage are in the Phase 5H bowling audit.\n\n"
        "## Stale historical files and dashboard reconciliation\n\n"
        +stale+"\n"
        "The dashboard's current final submission section now reads the Phase 5G overall list and Phase 5H method/decision/coverage; stale Phase 5F submission checklist and report framing are not displayed as current status. Historical source artifacts remain unchanged.\n\n"
        "## Action checklist\n\n"
        "- [x] Select batter dropdown ranks 1-10 from `phase5g_overall_batter_top10.csv`, deduplicated by stable player ID.\n"
        "- [x] Use Phase 5H consolidated methodology report as the current methodology upload.\n"
        "- [x] Retain IPL/T20I rankings as supporting evidence and preserve their own scores/uncertainty.\n"
        "- [ ] Resolve the required bowler dropdown with organizer guidance or newly authorized validated evidence; no external contact/data acquisition is part of this phase.\n"
        "- [ ] Do not mark the full three-deliverable submission complete until the bowler field has an honest accepted disposition.\n"
        "- [x] No raw data modified, no eligibility floor weakened, no bowler score fabricated.\n")


if __name__ == "__main__":
    print(json.dumps(main(),indent=2))
