"""Phase 5A: official confirmed-scope player analysis, without rankings."""
from __future__ import annotations
from pathlib import Path
import json
import math
import pandas as pd

from src.confirmed_scope_coverage import RAW, PROCESSED, REPORTS, filter_confirmed_scope
from src.cricket_data_validation import normalize_delivery_events
from src.pressure_method_review import pressure_definitions, _paired_population
from src.player_analytics import BATTER_FLOORS, BOWLER_FLOORS

ROOT = Path(__file__).resolve().parents[1]
FEATURES = PROCESSED / "pressure_research_deliveries.csv.gz"


def truth(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(bool)


def wilson(k: int, n: int) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    z = 1.959963984540054
    p = k/n
    d = 1+z*z/n
    center = (p+z*z/(2*n))/d
    half = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/d
    return max(0,center-half),min(1,center+half)


def build_states(features: pd.DataFrame) -> pd.DataFrame:
    """Classify regular second-innings states only when both CRR and RRR exist."""
    f=features.copy()
    for c in ["score_before","runs_required","legal_balls_remaining"]:
        f[c]=pd.to_numeric(f[c],errors="coerce")
    balls=pd.to_numeric(f.legal_balls_bowled_before,errors="coerce")
    f["required_run_rate"]=f.runs_required*6/f.legal_balls_remaining.where(f.legal_balls_remaining>0)
    f["current_run_rate"]=f.score_before*6/balls.where(balls>0)
    regular=f.innings.eq(2)&~f.innings_phase.astype("string").str.contains("super over",case=False,na=False)
    good=regular&truth(f.match_state_pressure_eligible)&f.innings_phase.notna()
    good &= f.required_run_rate.notna()&f.current_run_rate.notna()
    s=f.loc[good].copy()
    s["rate_gap"]=s.required_run_rate-s.current_run_rate
    s["pressure_class"]=s.rate_gap.gt(0).map({True:"pressure",False:"normal_baseline"})
    s["phase_key"]=s.innings_phase.astype("string")
    s["wickets_lost_key"]=pd.to_numeric(s.wickets_lost_before,errors="coerce")
    s["wickets_remaining_key"]=pd.to_numeric(s.wickets_remaining,errors="coerce")
    return s


def build_primary_pair(features: pd.DataFrame) -> pd.DataFrame:
    """Same-match, same-phase pair; wickets-lost balance is reported separately."""
    s=build_states(features)
    if s.empty:
        return s.assign(cohort=pd.Series(dtype="string"))
    s["_high"]=s.pressure_class.eq("pressure")
    counts=s.groupby(["match_id","phase_key"],dropna=False)._high.nunique()
    keys=counts[counts.eq(2)].reset_index()[["match_id","phase_key"]]
    p=s.merge(keys,on=["match_id","phase_key"],how="inner",validate="many_to_one")
    p["cohort"]=p.pressure_class
    return p.drop(columns="_high")


def bat_metrics(rows: pd.DataFrame) -> dict:
    x=rows.loc[truth(rows.ordinary_delivery)]
    r=pd.to_numeric(x.batter_runs_verified_subset,errors="coerce")
    n=int(r.notna().sum()); events=len(x); total=float(r.sum()) if n else None
    sr=100*total/n if n else None
    dots=int(truth(x.dot_ball_verified_subset).sum())
    bounds=int(truth(x.boundary_event).sum())
    lo_dot,hi_dot=wilson(dots,n); lo_b,hi_b=wilson(bounds,events)
    lo_sr=hi_sr=None
    if n>1:
        se=float(r.dropna().std(ddof=1)/math.sqrt(n))*100
        lo_sr,hi_sr=sr-1.96*se,sr+1.96*se
    return {"ordinary_events":events,"known_runs_events":n,"missing_runs_events":events-n,
        "run_coverage_pct":round(100*n/events,2) if events else None,"ordinary_runs":total,
        "ordinary_subset_strike_rate":sr,"strike_rate_naive_ci95_low":lo_sr,"strike_rate_naive_ci95_high":hi_sr,
        "ordinary_dot_events":dots,"ordinary_dot_rate":dots/n if n else None,
        "dot_wilson_ci95_low":lo_dot,"dot_wilson_ci95_high":hi_dot,
        "ordinary_boundary_events":bounds,"ordinary_boundary_rate":bounds/events if events else None,
        "boundary_wilson_ci95_low":lo_b,"boundary_wilson_ci95_high":hi_b}


def bowl_metrics(rows: pd.DataFrame) -> dict:
    n=len(rows); w=int(truth(rows.bowler_wicket_event).sum()); lo,hi=wilson(w,n)
    return {"observed_delivery_events":n,"recognized_credit_wickets":w,
        "wickets_per_observed_delivery_event":w/n if n else None,
        "wicket_wilson_ci95_low":lo,"wicket_wilson_ci95_high":hi,
        "unknown_legality_events":int(rows.legal_delivery.isna().sum()),
        "bowler_conceded_runs":None,"economy_rate":None,"bowling_strike_rate":None}


def build_proxy(features: pd.DataFrame) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Separate Q75/Q25 phase-and-wicket depletion proxy; never labels verified pressure."""
    x=features.loc[truth(features.wicket_phase_proxy_eligible)].copy()
    regular=~x.innings_phase.astype("string").str.contains("super over",case=False,na=False)
    x=x.loc[regular&x.innings_phase.notna()&x.wickets_lost_before.notna()].copy()
    x["wickets_lost_before"]=pd.to_numeric(x.wickets_lost_before,errors="coerce")
    x["proxy_class"]="middle"
    rows=[]
    for (fmt,phase),idx in x.groupby(["analysis_format","innings_phase"],sort=True).groups.items():
        v=x.loc[idx,"wickets_lost_before"]; q25=float(v.quantile(.25)); q50=float(v.quantile(.5)); q75=float(v.quantile(.75))
        if q75>q25:
            x.loc[idx[v.ge(q75)],"proxy_class"]="high_wicket_loss_proxy"
            x.loc[idx[v.le(q25)],"proxy_class"]="low_wicket_loss_reference"
        rows.append({"format":fmt,"phase":phase,"events":len(v),"wickets_q25":q25,"wickets_q50":q50,"wickets_q75":q75,
            "high_rule":f"wickets lost >= {q75:g}" if q75>q25 else "not separable: tied quantiles",
            "low_rule":f"wickets lost <= {q25:g}" if q75>q25 else "not separable: tied quantiles",
            "interpretation":"exploratory situational proxy; not verified or psychological pressure"})
    return x,pd.DataFrame(rows)


def build_player_profiles(features:pd.DataFrame,states:pd.DataFrame,pair:pd.DataFrame,proxy:pd.DataFrame,role:str)->pd.DataFrame:
    idcol,namecol=("striker_id","striker_name") if role=="batter" else ("bowler_id","bowler_name")
    floors=BATTER_FLOORS if role=="batter" else BOWLER_FLOORS
    out=[]
    for (fmt,pid),full in features.dropna(subset=[idcol]).groupby(["analysis_format",idcol],sort=True):
        nm=full[namecol].dropna().astype(str).mode(); name=nm.iloc[0] if len(nm) else "Unknown"
        p=pair.loc[pair.analysis_format.eq(fmt)&pair[idcol].eq(pid)&pair.cohort.eq("pressure")]
        b=pair.loc[pair.analysis_format.eq(fmt)&pair[idcol].eq(pid)&pair.cohort.eq("normal_baseline")]
        pe=int(truth(p.ordinary_delivery).sum()) if role=="batter" else len(p)
        be=int(truth(b.ordinary_delivery).sum()) if role=="batter" else len(b)
        pm,bm=int(p.match_id.nunique()),int(b.match_id.nunique())
        eligible=pe>=floors["pressure_events"] and pm>=floors["pressure_matches"] and be>=floors["baseline_events"] and bm>=floors["baseline_matches"]
        statep=states.loc[states.analysis_format.eq(fmt)&states[idcol].eq(pid)&states.pressure_class.eq("pressure")]
        r={"player_id":pid,"player_name":name,"format":fmt,"role":role,"matches_observed":int(full.match_id.nunique()),
            "deliveries_observed":len(full),"known_pressure_deliveries_unpaired":len(statep),
            "paired_pressure_deliveries":len(p),"pressure_metric_events":pe,"pressure_matches":pm,
            "paired_baseline_deliveries":len(b),"baseline_metric_events":be,"baseline_matches":bm,
            "pressure_event_floor":floors["pressure_events"],"pressure_match_floor":floors["pressure_matches"],
            "baseline_event_floor":floors["baseline_events"],"baseline_match_floor":floors["baseline_matches"],
            "meets_existing_phase2d_both_floors":bool(eligible),
            "uncertainty_note":"small clustered delivery sample; descriptive intervals are naive"}
        if role=="batter":
            allm,pp,bb=bat_metrics(full),bat_metrics(p),bat_metrics(b)
            r.update({f"all_{k}":v for k,v in allm.items()}); r.update({f"pressure_{k}":v for k,v in pp.items()}); r.update({f"baseline_{k}":v for k,v in bb.items()})
            r["delta_sr_pressure_minus_baseline"]=pp["ordinary_subset_strike_rate"]-bb["ordinary_subset_strike_rate"] if pp["ordinary_subset_strike_rate"] is not None and bb["ordinary_subset_strike_rate"] is not None else None
            r["dot_rate_reduction_baseline_minus_pressure"]=bb["ordinary_dot_rate"]-pp["ordinary_dot_rate"] if pp["ordinary_dot_rate"] is not None and bb["ordinary_dot_rate"] is not None else None
            r["boundary_rate_change_pressure_minus_baseline"]=pp["ordinary_boundary_rate"]-bb["ordinary_boundary_rate"] if pp["ordinary_boundary_rate"] is not None and bb["ordinary_boundary_rate"] is not None else None
            hi=proxy.loc[proxy.analysis_format.eq(fmt)&proxy[idcol].eq(pid)&proxy.proxy_class.eq("high_wicket_loss_proxy")]
            lo=proxy.loc[proxy.analysis_format.eq(fmt)&proxy[idcol].eq(pid)&proxy.proxy_class.eq("low_wicket_loss_reference")]
            r["proxy_high_events"]=len(hi); r["proxy_high_matches"]=int(hi.match_id.nunique()); r["proxy_high_runs"]=bat_metrics(hi)["ordinary_runs"]
            r["proxy_low_reference_events"]=len(lo); r["proxy_low_reference_runs"]=bat_metrics(lo)["ordinary_runs"]
            r["pressure_missing_runs_pct"]=None if pp["run_coverage_pct"] is None else 100-pp["run_coverage_pct"]
            r["baseline_missing_runs_pct"]=None if bb["run_coverage_pct"] is None else 100-bb["run_coverage_pct"]
        else:
            allm,pp,bb=bowl_metrics(full),bowl_metrics(p),bowl_metrics(b)
            r.update({f"all_{k}":v for k,v in allm.items()}); r.update({f"pressure_{k}":v for k,v in pp.items()}); r.update({f"baseline_{k}":v for k,v in bb.items()})
            base=bb["recognized_credit_wickets"]/bb["observed_delivery_events"] if bb["observed_delivery_events"] else None
            expected=base*pe if base is not None else None
            r["expected_pressure_wickets_at_baseline_event_yield"]=expected
            r["wicket_event_yield_residual"]=pp["recognized_credit_wickets"]-expected if expected is not None else None
            hi=proxy.loc[proxy.analysis_format.eq(fmt)&proxy[idcol].eq(pid)&proxy.proxy_class.eq("high_wicket_loss_proxy")]
            lo=proxy.loc[proxy.analysis_format.eq(fmt)&proxy[idcol].eq(pid)&proxy.proxy_class.eq("low_wicket_loss_reference")]
            r["proxy_high_events"]=len(hi); r["proxy_high_matches"]=int(hi.match_id.nunique())
            r["proxy_high_wickets"]=int(truth(hi.bowler_wicket_event).sum()); r["proxy_low_reference_events"]=len(lo)
            r["proxy_low_reference_wickets"]=int(truth(lo.bowler_wicket_event).sum())
            r["bowler_conceded_runs_coverage_pct"]=0.0; r["economy_status"]="blocked"; r["bowling_strike_rate_status"]="blocked"
        out.append(r)
    return pd.DataFrame(out)


def state_summary(features:pd.DataFrame,states:pd.DataFrame,pair:pd.DataFrame)->pd.DataFrame:
    rows=[]
    for fmt,f in features.groupby("analysis_format",sort=True):
        known=f.loc[f.innings.eq(2)&truth(f.match_state_pressure_eligible)&~f.innings_phase.astype("string").str.contains("super over",case=False,na=False)]
        s=states.loc[states.analysis_format.eq(fmt)]; p=pair.loc[pair.analysis_format.eq(fmt)]
        rows.append({"format":fmt,"matches":int(f.match_id.nunique()),"deliveries":len(f),"known_regular_chase_states":len(known),
            "states_with_crr_rrr":len(s),"rrr_gt_crr":int(s.pressure_class.eq("pressure").sum()),
            "rrr_le_crr":int(s.pressure_class.eq("normal_baseline").sum()),"paired_rows":len(p),
            "paired_pressure_rows":int(p.cohort.eq("pressure").sum()),"paired_baseline_rows":int(p.cohort.eq("normal_baseline").sum()),
            "paired_matches":int(p.match_id.nunique()),"accepted_external_matches":0})
    return pd.DataFrame(rows)


def pressure_sensitivity(features:pd.DataFrame)->pd.DataFrame:
    """Test phase 3A.1 state definitions/matching plus explicit Q25 tier."""
    rows=[]
    for fmt,part in features.groupby("analysis_format",sort=True):
        s=build_states(part)
        if s.empty: continue
        s["rate_gap"]=s.required_run_rate-s.current_run_rate
        defs=pressure_definitions(s)
        for dname,(high,low,rule) in defs.items():
            for method in ["within_match_phase","exact_match_phase_wickets"]:
                pop=_paired_population(s,high,low,method)
                for role,idcol,floors in [("batter","striker_id",BATTER_FLOORS),("bowler","bowler_id",BOWLER_FLOORS)]:
                    exp=pop.loc[truth(pop.ordinary_delivery)] if role=="batter" else pop
                    groups={}
                    for flag,label in [(True,"p"),(False,"b")]:
                        x=exp.loc[exp._high.eq(flag)]
                        groups[label]=x.groupby(idcol).agg(events=("match_id","size"),matches=("match_id","nunique"))
                    ids=groups["p"].index.intersection(groups["b"].index)
                    p=groups["p"].reindex(ids,fill_value=0); b=groups["b"].reindex(ids,fill_value=0)
                    existing=int(((p.events.ge(floors["pressure_events"])&p.matches.ge(floors["pressure_matches"]))&
                                  (b.events.ge(floors["baseline_events"])&b.matches.ge(floors["baseline_matches"]))).sum())
                    qp=float(p.events.quantile(.25)) if len(p) else 0; qb=float(b.events.quantile(.25)) if len(b) else 0
                    alt=int(((p.events.ge(max(1,math.ceil(qp)))&p.matches.ge(2))&(b.events.ge(max(1,math.ceil(qb)))&b.matches.ge(2))).sum()) if len(ids) else 0
                    rows.append({"format":fmt,"pressure_definition":dname,"rule":rule,"baseline_matching":method,"role":role,
                        "pressure_events":int(exp._high.sum()),"baseline_events":int((~exp._high).sum()),
                        "pressure_matches":int(pop.loc[pop._high,"match_id"].nunique()),"baseline_matches":int(pop.loc[~pop._high,"match_id"].nunique()),
                        "players_both":len(ids),"existing_floor_eligible":existing,"q25_pressure_events":math.ceil(qp) if len(p) else 0,
                        "q25_baseline_events":math.ceil(qb) if len(b) else 0,"q25_sensitivity_min_matches_each":2,
                        "q25_sensitivity_eligible":alt,"phase2d_floors_changed":False})
    return pd.DataFrame(rows)


def weight_sensitivity(batters:pd.DataFrame)->pd.DataFrame:
    scenarios={"SR_only":(1.,0.,0.),"Phase3A_60_20_20":(.6,.2,.2),"Balanced_50_25_25":(.5,.25,.25),"Style_heavy_40_30_30":(.4,.3,.3)}
    cols=["delta_sr_pressure_minus_baseline","dot_rate_reduction_baseline_minus_pressure","boundary_rate_change_pressure_minus_baseline"]
    out=[]
    for fmt,g in batters.groupby("format",sort=True):
        x=g.dropna(subset=cols).copy(); n=len(x)
        z=[]
        for c in cols:
            sd=x[c].std(ddof=1) if n>1 else 0
            z.append((x[c]-x[c].mean())/sd if pd.notna(sd) and sd>0 else pd.Series(0.,index=x.index))
        scores={name:sum(w[i]*z[i] for i in range(3)) for name,w in scenarios.items()}
        base=scores["Phase3A_60_20_20"].rank(ascending=False,method="average")
        for name,w in scenarios.items():
            rank=scores[name].rank(ascending=False,method="average")
            out.append({"format":fmt,"weight_scenario":name,"weights_sr_dot_boundary":"/".join(f"{v:.2f}" for v in w),
                "players_with_all_deltas":n,"spearman_vs_60_20_20":float(rank.corr(base,method="spearman")) if n>1 else None,
                "top10_overlap":int(len(set(rank.nsmallest(10).index)&set(base.nsmallest(10).index))) if n>=10 else None,
                "eligible_under_existing_floors":int(x.meets_existing_phase2d_both_floors.sum()) if n else 0,
                "diagnostic_only":True})
    return pd.DataFrame(out)


def metric_coverage(features:pd.DataFrame,states:pd.DataFrame,pair:pd.DataFrame,
                    proxy:pd.DataFrame,thresholds:pd.DataFrame)->pd.DataFrame:
    """Field-level reliability and confirmed-scope coverage by format."""
    normalized=normalize_delivery_events(features)
    specs=[
      ("Batter runs, ordinary subset","limited","runs; ordinary_delivery; batter_runs_verified_subset","ordinary rows with known runs","extras events omitted"),
      ("Balls faced, ordinary subset","limited","ordinary_delivery","ordinary delivery events","not conventional full balls faced"),
      ("Strike rate, ordinary subset","limited","batter_runs_verified_subset; ordinary_delivery","100 x known ordinary runs / known ordinary events","not conventional full strike rate"),
      ("Boundary event count","reliable","is_four; is_six; striker_id","verified boundary flags","count only; complete rate denominator not available"),
      ("Dot rate, ordinary subset","limited","dot_ball_verified_subset; ordinary_delivery","known ordinary dots / known ordinary run rows","excludes extras"),
      ("Batter dismissal event","limited","batter_dismissal_event; dismissed_player_id","recognized local dismissed-player events","retirement and player-ID limitations"),
      ("Team wickets lost","limited","is_wicket; dismissal_type","wicket event flags","match/innings metric, distinct from bowler credit"),
      ("Recognized bowler-credit wickets","limited","bowler_wicket_event; bowler_id; dismissal_type","recognized credit types only","no-ball exceptions and taxonomy still limited"),
      ("Known-category legal delivery exposure","limited","legal_delivery; extras_type; ordinary_delivery","ordinary plus verified legal bye/leg-bye rows","not complete legal balls / overs"),
      ("Bowler-conceded runs","blocked","complete total_runs and typed extras absent","none","do not infer from runs or extra codes"),
      ("Economy rate","blocked","bowler-conceded runs; full legal balls absent","none","both inputs incomplete"),
      ("Conventional bowling strike rate","blocked","full legal balls; recognized wickets","none","full legal-ball denominator absent"),
      ("Verified pressure RRR > CRR","reliable","score_before; target; runs_required; legal balls","known regular chase states with required rate above current rate","only known-input rows; match acceptance remains separate"),
      ("Verified comparison RRR <= CRR","reliable","same state fields","known regular chase states at/ahead of required rate","not all-inning normal baseline"),
      ("Within-match phase-paired state","limited","state inputs; match_id; innings_phase","both classes within same match and phase","small clusters; wicket balance not exact"),
      ("Wicket/phase descriptive proxy","limited","wickets_lost_before; innings_phase; overid","regular innings with known phase and wicket state","situational context only"),
      ("High wicket-loss Q75 proxy","provisional","wickets_lost_before; innings_phase","high-depletion rows above format/phase Q75","exploratory, tie-sensitive and not verified pressure"),
      ("Full delivery team-run increment","blocked","runs; extras_type; extras1_runs; extras_2_runs","non-null conservative-normalizer team_runs_delta only","11,467 run events unresolved"),
      ("Full target / revised-limit history","blocked","revised_target; first_inn_revised_overs; second_inn_revised_overs","known-state rows only","sparse undocumented semantics outside known states"),
    ]
    out=[]
    for fmt in ["IPL","T20I","ALL"]:
        f=features if fmt=="ALL" else features.loc[features.analysis_format.eq(fmt)]
        st=states if fmt=="ALL" else states.loc[states.analysis_format.eq(fmt)]
        pp=pair if fmt=="ALL" else pair.loc[pair.analysis_format.eq(fmt)]
        px=proxy if fmt=="ALL" else proxy.loc[proxy.analysis_format.eq(fmt)]
        norm=normalized if fmt=="ALL" else normalized.loc[normalized.analysis_format.eq(fmt)]
        for metric,status,fields,meaning,limitations in specs:
            players=0; matches=0; n=0
            if metric=="Batter runs, ordinary subset":
                x=f.loc[truth(f.ordinary_delivery)&f.batter_runs_verified_subset.notna()]; n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Balls faced, ordinary subset":
                x=f.loc[truth(f.ordinary_delivery)];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Strike rate, ordinary subset":
                x=f.loc[truth(f.ordinary_delivery)&f.batter_runs_verified_subset.notna()];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Boundary event count":
                x=f.loc[truth(f.boundary_event)];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Dot rate, ordinary subset":
                x=f.loc[truth(f.ordinary_delivery)&truth(f.dot_ball_verified_subset)];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Batter dismissal event":
                x=f.loc[truth(f.batter_dismissal_event)];n=len(x);players=x.dismissed_player_id.nunique();matches=x.match_id.nunique()
            elif metric=="Team wickets lost":
                x=f.loc[truth(f.is_wicket)];n=len(x);matches=x.match_id.nunique()
            elif metric=="Recognized bowler-credit wickets":
                x=f.loc[truth(f.bowler_wicket_event)];n=len(x);players=x.bowler_id.nunique();matches=x.match_id.nunique()
            elif metric=="Known-category legal delivery exposure":
                labels=f.extras_type.astype("string").str.casefold();mask=truth(f.ordinary_delivery)|(labels.isin(["byes","legbyes"])&truth(f.legal_delivery));x=f.loc[mask];n=len(x);players=x.bowler_id.nunique();matches=x.match_id.nunique()
            elif metric=="Verified pressure RRR > CRR":
                x=st.loc[st.pressure_class.eq("pressure")];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Verified comparison RRR <= CRR":
                x=st.loc[st.pressure_class.eq("normal_baseline")];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Within-match phase-paired state":
                x=pp;n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Wicket/phase descriptive proxy":
                x=f.loc[truth(f.wicket_phase_proxy_eligible)&~f.innings_phase.astype("string").str.contains("super over",case=False,na=False)];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="High wicket-loss Q75 proxy":
                x=px.loc[px.proxy_class.eq("high_wicket_loss_proxy")];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Full delivery team-run increment":
                x=norm.loc[norm.team_runs_delta.notna()];n=len(x);players=x.striker_id.nunique();matches=x.match_id.nunique()
            elif metric=="Bowler-conceded runs":
                n=0
            elif metric=="Economy rate":
                n=0
            elif metric=="Conventional bowling strike rate":
                n=0
            elif metric=="Full target / revised-limit history":
                x=f.loc[truth(f.match_state_pressure_eligible)];n=len(x);matches=x.match_id.nunique()
            denom=len(f)
            out.append({"format":fmt,"metric":metric,"classification":status,"covered_events_or_rows":int(n),
                "scope_delivery_rows":denom,"coverage_pct_of_scope":round(100*n/denom,4) if denom else 0,
                "matches_covered":int(matches),"players_covered":int(players),"source_fields":fields,
                "calculation":meaning,"limitations":limitations})
    return pd.DataFrame(out)


def md_table(frame:pd.DataFrame)->str:
    if frame.empty:return "No rows."
    def cell(v):
        if pd.isna(v):return ""
        return f"{v:.4g}" if isinstance(v,float) else str(v).replace("|","\\|").replace("\n"," ")
    return "\n".join(["| "+" | ".join(map(str,frame.columns))+" |","| "+" | ".join(["---"]*len(frame.columns))+" |"]+
        ["| "+" | ".join(cell(v) for v in row)+" |" for row in frame.itertuples(index=False,name=None)])


def write_reports(features,states,pair,proxy,thresholds,state,coverage,sensitivity,weights,batters,bowlers):
    existing=pd.read_csv(REPORTS/"confirmed_scope_player_eligibility.csv")
    exposure=[]
    for role,frame in [("batter",batters),("bowler",bowlers)]:
        for fmt in ["IPL","T20I"]:
            g=frame.loc[frame.format.eq(fmt)]
            exposure.append({"role":role,"format":fmt,"players_observed":len(g),
                "players_with_pressure_and_baseline":int(((g.pressure_metric_events>0)&(g.baseline_metric_events>0)).sum()),
                "players_meeting_existing_floors":int(g.meets_existing_phase2d_both_floors.sum())})
    proxy_summary=proxy.groupby(["analysis_format","proxy_class"],as_index=False).agg(deliveries=("match_id","size"),matches=("match_id","nunique"))
    sensitive=sensitivity.groupby(["format","pressure_definition","baseline_matching","role"],as_index=False).agg(
        pressure_events=("pressure_events","max"),baseline_events=("baseline_events","max"),players_both=("players_both","max"),
        existing_floor_eligible=("existing_floor_eligible","max"),q25_sensitivity_eligible=("q25_sensitivity_eligible","max"))
    coverage_all=coverage.loc[coverage.format.eq("ALL"),["metric","classification","covered_events_or_rows","coverage_pct_of_scope","limitations"]]
    main=["# Phase 5A — Available-data player analysis","",
      "## Scope and guardrails","",
      "Only supplied official IPL and T20I records from 2022 onward are used, filtered by official competition metadata and match date. No provider response or external dataset is read. Raw files, Phase 2E decisions, pressure definition and Phase 2D floors are unchanged. No final player score or ranking is produced.","",
      "Verified pressure is regular-chase RRR > CRR where score, target and legal-ball state are known. The comparison is RRR <= CRR in the same match and phase. This is scoreboard demand, not psychological pressure. Wicket/phase contexts remain separate proxies.","",
      "## Metric reliability audit","",md_table(coverage_all),"",
      "Full team-run increments remain unresolved on 11,467 events. Batter rates use only the ordinary-delivery subset. Bowler-conceded runs, economy and conventional bowling strike rate remain blocked. Bowler wicket rates use observed event counts, not an invented legal-ball denominator.","",
      "## State coverage","",md_table(state),"",
      "Only states with a completed-ball CRR enter RRR>CRR classification. The matched baseline retains same-match, same-phase strata containing both classes. Unknown states are not assigned to either side.","",
      "## Player evidence","",md_table(pd.DataFrame(exposure)),"",
      "Role CSVs contain per-player match/delivery exposure, pressure and baseline observations/matches, ordinary-run missingness, rates and uncertainty bounds. Batter differences are unweighted raw deltas. Bowler residuals compare recognized credited wickets per observed delivery event to baseline event yield and are nonstandard descriptive measures. Intervals ignore match clustering.","",
      "### Existing eligibility floors","",md_table(existing),"",
      "No player-format pair meets both existing floors. Below-floor deltas are descriptive only and not selection evidence.","",
      "## Supplementary wicket/phase proxy","",
      "High wicket-depletion proxy uses the format/phase Q75 of wickets lost before the event; the low reference uses Q25. Super Overs are excluded. This exploratory proxy is not verified pressure and is not the normal baseline.","",md_table(thresholds),md_table(proxy_summary),"",
      "## Pressure, threshold and weight sensitivity","",
      "Pressure variants tested are the primary RRR>CRR rule and Phase 3A.1 alternatives: high absolute RRR, high RRR-CRR gap, behind-rate with low resources, and high runs-required-per-wicket. They are calculated separately by format. Baselines use within-match/phase and exact match/phase/wickets methods. Phase 2D floors remain unchanged; empirical Q25 floors are labelled sensitivity only.","",md_table(sensitive),"",
      "Batter weight sensitivity tests SR-only 100/0/0, proposed 60/20/20, balanced 50/25/25, and style-heavy 40/30/30 on three ordinary-subset raw deltas. Only aggregate rank-correlation diagnostics are reported; player order and weighted scores are not exported. Bowler weights are not meaningful with only one eligible outcome.","",md_table(weights),"",
      "## Top 10 support","",
      "Neither a batter nor bowler Top 10 is supportable from these data under the existing floors. Proxy contexts cannot replace verified match states, and lowering thresholds to obtain ten names would weaken evidence standards."]
    (REPORTS/"phase5a_available_data_analysis.md").write_text("\n".join(main)+"\n",encoding="utf-8")
    ranking=["# Phase 5A — Ranking sensitivity and support audit","",
      "No player scores, ordered player rows or Top 10 lists are published.","",
      "## Pressure and matching sensitivity","",md_table(sensitive),"",
      "The primary definition remains RRR>CRR. Alternative definitions and exact wicket matching are sensitivity checks only.","",
      "## Threshold sensitivity","",md_table(sensitivity.groupby(["format","role","baseline_matching"],as_index=False).agg(
        existing_floors=("existing_floor_eligible","max"),q25_sensitivity=("q25_sensitivity_eligible","max"),
        pressure_events=("pressure_events","max"),baseline_events=("baseline_events","max"))),"",
      "Q25 cutoffs come from observed player event distributions within each format, pressure definition, matching rule and role. The exploratory tier requires two matches per side; for batter baseline that is less strict than the inherited three-match floor and does not replace it.","",
      "## Batter scoring-weight sensitivity","",md_table(weights),"",
      "Small samples make ordering diagnostics unstable; top-10 overlap is undefined below ten candidates. No under-floor score is eligible for selection.","",
      "## Bowler and Top 10 conclusion","",
      "Only recognized credited wickets are usable. The event-yield residual is not conventional strike rate. Neither required Top 10 is defensible with the current exposure and baseline evidence."]
    (REPORTS/"phase5a_ranking_sensitivity.md").write_text("\n".join(ranking)+"\n",encoding="utf-8")


def run()->dict[str,int]:
    raw=pd.read_csv(FEATURES,low_memory=False)
    matches=pd.read_csv(RAW/"matches.csv",low_memory=False)
    comps=pd.read_csv(RAW/"competitions.csv",low_memory=False)
    f=filter_confirmed_scope(raw,matches,comps)
    states=build_states(f); pair=build_primary_pair(f); proxy,thresholds=build_proxy(f)
    bat=build_player_profiles(f,states,pair,proxy,"batter")
    bowl=build_player_profiles(f,states,pair,proxy,"bowler")
    state=state_summary(f,states,pair); sensitivity=pressure_sensitivity(f)
    weights=weight_sensitivity(bat); coverage=metric_coverage(f,states,pair,proxy,thresholds)
    REPORTS.mkdir(parents=True,exist_ok=True)
    bat.to_csv(REPORTS/"phase5a_batter_analysis.csv",index=False)
    bowl.to_csv(REPORTS/"phase5a_bowler_analysis.csv",index=False)
    coverage.to_csv(REPORTS/"phase5a_metric_coverage.csv",index=False)
    sensitivity.to_csv(REPORTS/"phase5a_pressure_threshold_sensitivity.csv",index=False)
    thresholds.to_csv(REPORTS/"phase5a_proxy_thresholds.csv",index=False)
    write_reports(f,states,pair,proxy,thresholds,state,coverage,sensitivity,weights,bat,bowl)
    return {"scope_deliveries":len(f),"paired_state_rows":len(pair),"batter_player_formats":len(bat),
        "bowler_player_formats":len(bowl),"batter_floor_qualified":int(bat.meets_existing_phase2d_both_floors.sum()),
        "bowler_floor_qualified":int(bowl.meets_existing_phase2d_both_floors.sum()),"pressure_sensitivity_rows":len(sensitivity)}


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
