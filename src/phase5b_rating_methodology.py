"""Phase 5B pressure rating feasibility; no player scores or rankings emitted."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from src.confirmed_scope_coverage import RAW, PROCESSED, REPORTS, filter_confirmed_scope
from src.phase5a_analysis import build_states, build_proxy, truth, md_table
from src.player_analytics import BATTER_FLOORS, BOWLER_FLOORS

FEATURES = PROCESSED / "pressure_research_deliveries.csv.gz"
METHODS = ("verified_chase", "wicket_phase_proxy", "combined_verified_and_proxy")


def _paired(x: pd.DataFrame, high: pd.Series, low: pd.Series) -> pd.DataFrame:
    """Retain same-match, same-phase strata with both pressure and reference rows."""
    x = x.copy()
    x["_high"] = high.reindex(x.index).fillna(False).astype(bool)
    x["_low"] = low.reindex(x.index).fillna(False).astype(bool)
    x = x.loc[x._high | x._low].copy()
    groups = x.groupby(["match_id", "innings_phase"], dropna=False)
    good = groups._high.any() & groups._low.any()
    keys = good[good].index
    if not len(keys):
        return x.iloc[0:0].drop(columns=["_high", "_low"])
    idx = pd.MultiIndex.from_frame(x[["match_id", "innings_phase"]])
    x = x.loc[idx.isin(keys)].copy()
    x["cohort"] = x._high.map({True: "pressure", False: "baseline"})
    return x.drop(columns=["_high", "_low"])


def pressure_cohorts(features: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build the three pressure definitions on regular innings only.

    Proxy-only strata use high/low wicket-loss quantiles. Combined strata require
    both verified chase state and proxy class, so unknown states never qualify.
    """
    regular = features.loc[~features.innings_phase.astype("string").str.contains(
        "super over", case=False, na=False)].copy()
    proxy, _ = build_proxy(regular)
    # Wicket/phase proxy comparisons include all innings with known local wicket
    # and phase fields; super overs have already been removed by build_proxy.
    px = proxy.loc[proxy.proxy_class.isin([
        "high_wicket_loss_proxy", "low_wicket_loss_reference"]
    )].copy()
    px_pair = _paired(px,
        px.proxy_class.eq("high_wicket_loss_proxy"),
        px.proxy_class.eq("low_wicket_loss_reference"))
    px_pair["definition"] = "wicket_phase_proxy"

    states = build_states(regular)
    verified = _paired(states,
        states.pressure_class.eq("pressure"),
        states.pressure_class.eq("normal_baseline"))
    verified["definition"] = "verified_chase"

    # Join only records with state inputs and a proxy class. Use source row keys,
    # not player names, for this within-dataset intersection.
    key = ["match_id", "innings", "sequence"]
    keep = [*key, "proxy_class"]
    joined = states.merge(px[keep], on=key, how="inner", validate="one_to_one")
    high = joined.pressure_class.eq("pressure") & joined.proxy_class.eq("high_wicket_loss_proxy")
    low = joined.pressure_class.eq("normal_baseline") & joined.proxy_class.eq("low_wicket_loss_reference")
    combined = _paired(joined, high, low)
    combined["definition"] = "combined_verified_and_proxy"
    return {"verified_chase": verified,
            "wicket_phase_proxy": px_pair,
            "combined_verified_and_proxy": combined}


def _metric_rows(rows: pd.DataFrame, role: str) -> dict[str, object]:
    if role == "batter":
        x = rows.loc[truth(rows.ordinary_delivery)].copy()
        runs = pd.to_numeric(x.batter_runs_verified_subset, errors="coerce")
        known = int(runs.notna().sum())
        return {"metric_events": len(x), "known_run_events": known,
                "missing_run_events": len(x)-known,
                "run_coverage_pct": 100*known/len(x) if len(x) else None,
                "batter_runs": float(runs.sum()) if known else None,
                "ordinary_subset_sr": 100*float(runs.sum())/known if known else None,
                "dot_rate": float(truth(x.dot_ball_verified_subset).sum())/known if known else None,
                "boundary_event_rate": float(truth(x.boundary_event).sum())/len(x) if len(x) else None,
                "recognized_wickets": None}
    wickets = int(truth(rows.bowler_wicket_event).sum())
    n = len(rows)
    return {"metric_events": n, "known_run_events": None, "missing_run_events": None,
            "run_coverage_pct": None, "batter_runs": None, "ordinary_subset_sr": None,
            "dot_rate": None, "boundary_event_rate": None,
            "recognized_wickets": wickets,
            "recognized_wickets_per_observed_event": wickets/n if n else None,
            "bowler_conceded_runs": None, "economy_rate": None,
            "bowling_strike_rate": None}


def player_method_results(features: pd.DataFrame,
                          cohorts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    out = []
    for method, pair in cohorts.items():
        for role, idcol, namecol, floors in [
            ("batter", "striker_id", "striker_name", BATTER_FLOORS),
            ("bowler", "bowler_id", "bowler_name", BOWLER_FLOORS),
        ]:
            for fmt in ["IPL", "T20I"]:
                subset = pair.loc[pair.analysis_format.eq(fmt)]
                allfmt = features.loc[features.analysis_format.eq(fmt)]
                full_groups = {pid: full for pid, full in
                               allfmt.dropna(subset=[idcol]).groupby(idcol, sort=True)}
                cohort_groups = {(pid, cohort): part for (pid, cohort), part in
                    subset.dropna(subset=[idcol]).groupby([idcol, "cohort"], sort=False)}
                for pid, full in full_groups.items():
                    nm = full[namecol].dropna().astype(str).mode()
                    name = nm.iloc[0] if len(nm) else "Unknown"
                    pr = cohort_groups.get((pid, "pressure"), subset.iloc[0:0])
                    bl = cohort_groups.get((pid, "baseline"), subset.iloc[0:0])
                    pm, bm = int(pr.match_id.nunique()), int(bl.match_id.nunique())
                    pmet, bmet = _metric_rows(pr, role), _metric_rows(bl, role)
                    pe, be = int(pmet["metric_events"]), int(bmet["metric_events"])
                    floor_ok = (pe >= floors["pressure_events"] and pm >= floors["pressure_matches"]
                                and be >= floors["baseline_events"] and bm >= floors["baseline_matches"])
                    # Empirical Q25 cutoffs are reported as an alternative tier,
                    # never substituted for inherited Phase 2D floors.
                    common = subset.loc[subset[idcol].eq(pid)]
                    high_events = int(common.loc[common.cohort.eq("pressure")].shape[0])
                    low_events = int(common.loc[common.cohort.eq("baseline")].shape[0])
                    reason = []
                    if pe == 0: reason.append("no paired pressure observations")
                    elif pm < floors["pressure_matches"]: reason.append("pressure match floor not met")
                    if be == 0: reason.append("no paired baseline observations")
                    elif bm < floors["baseline_matches"]: reason.append("baseline match floor not met")
                    if pe < floors["pressure_events"]: reason.append("pressure event floor not met")
                    if be < floors["baseline_events"]: reason.append("baseline event floor not met")
                    row = {"method": method, "format": fmt, "role": role,
                        "player_id": pid, "player_name": name,
                        "matches_observed": int(full.match_id.nunique()),
                        "deliveries_observed": len(full),
                        "pressure_events": pe, "pressure_matches": pm,
                        "baseline_events": be, "baseline_matches": bm,
                        "pressure_event_floor": floors["pressure_events"],
                        "pressure_match_floor": floors["pressure_matches"],
                        "baseline_event_floor": floors["baseline_events"],
                        "baseline_match_floor": floors["baseline_matches"],
                        "meets_existing_floors": bool(floor_ok),
                        "existing_floor_decision": "eligible" if floor_ok else "ineligible",
                        "exclusion_reason": "; ".join(reason),
                        "pressure_metric_events": pe, "pressure_metric_missing_run_events": pmet["missing_run_events"],
                        "pressure_run_coverage_pct": pmet["run_coverage_pct"],
                        "pressure_batter_runs": pmet["batter_runs"],
                        "pressure_sr": pmet["ordinary_subset_sr"],
                        "pressure_dot_rate": pmet["dot_rate"],
                        "pressure_boundary_rate": pmet["boundary_event_rate"],
                        "pressure_recognized_wickets": pmet["recognized_wickets"],
                        "pressure_wicket_yield_per_event": pmet.get("recognized_wickets_per_observed_event"),
                        "baseline_metric_events": be, "baseline_metric_missing_run_events": bmet["missing_run_events"],
                        "baseline_run_coverage_pct": bmet["run_coverage_pct"],
                        "baseline_batter_runs": bmet["batter_runs"],
                        "baseline_sr": bmet["ordinary_subset_sr"],
                        "baseline_dot_rate": bmet["dot_rate"],
                        "baseline_boundary_rate": bmet["boundary_event_rate"],
                        "baseline_recognized_wickets": bmet["recognized_wickets"],
                        "baseline_wicket_yield_per_event": bmet.get("recognized_wickets_per_observed_event"),
                        "bowler_conceded_runs": None if role == "bowler" else "not_applicable",
                        "economy_rate": None if role == "bowler" else "not_applicable",
                        "bowling_strike_rate": None if role == "bowler" else "not_applicable"}
                    if role == "batter":
                        for metric in ["sr", "dot_rate", "boundary_rate"]:
                            a, b = row[f"pressure_{metric}"], row[f"baseline_{metric}"]
                            row[f"delta_{metric}"] = a-b if a is not None and b is not None else None
                    else:
                        a, b = row["pressure_wicket_yield_per_event"], row["baseline_wicket_yield_per_event"]
                        row["wicket_yield_residual"] = a-b if a is not None and b is not None else None
                    out.append(row)
    return pd.DataFrame(out)


def eligibility_sensitivity(players: pd.DataFrame) -> pd.DataFrame:
    """Compare inherited floors to a separately labelled data-derived tier."""
    out=[]
    for (method, fmt, role), g in players.groupby(["method", "format", "role"], sort=True):
        both = g.loc[g.pressure_events.gt(0) & g.baseline_events.gt(0)]
        pq = int(both.pressure_events.quantile(.25)) if len(both) else 0
        bq = int(both.baseline_events.quantile(.25)) if len(both) else 0
        # Exploratory threshold: observed Q25 exposure counts, with at least two
        # matches on each side. This is explicitly not a recommended final floor.
        alt = both.loc[both.pressure_events.ge(max(1,pq)) & both.baseline_events.ge(max(1,bq))
                       & both.pressure_matches.ge(2) & both.baseline_matches.ge(2)]
        strict = g.loc[g.meets_existing_floors]
        for tier, selected, pe, be, pm, bm, justification in [
            ("existing_Phase2D", strict, int(g.pressure_event_floor.iloc[0]), int(g.baseline_event_floor.iloc[0]),
             int(g.pressure_match_floor.iloc[0]), int(g.baseline_match_floor.iloc[0]),
             "inherited evidence floors; unchanged"),
            ("exploratory_empirical_Q25", alt, max(1,pq), max(1,bq), 2, 2,
             "per-method player exposure Q25 and two matches per side; exploratory only"),
        ]:
            out.append({"method":method,"format":fmt,"role":role,"threshold_tier":tier,
                "pressure_event_min":pe,"pressure_match_min":pm,"baseline_event_min":be,"baseline_match_min":bm,
                "players_with_both_sides":len(both),"players_eligible":len(selected),
                "eligible_player_ids":";".join(map(str,selected.player_id.tolist())),
                "eligible_player_names":";".join(selected.player_name.tolist()),
                "eligible_players_evidence":"; ".join(
                    f"{r.player_name} (P {r.pressure_events}/{r.pressure_matches} matches; B {r.baseline_events}/{r.baseline_matches})"
                    for r in selected.itertuples()),
                "noneligible_reason_summary": "; ".join(g.exclusion_reason.value_counts().head(5).index.tolist()),
                "justification":justification,"changes_existing_floor":False if tier=="existing_Phase2D" else True,
                "score_or_rank_generated":False})
    return pd.DataFrame(out)


def pressure_definition_comparison(cohorts: dict[str,pd.DataFrame], players:pd.DataFrame)->pd.DataFrame:
    rows=[]
    descriptions={
      "verified_chase":("Regular second innings with known state; pressure=RRR>CRR; reference=RRR<=CRR.","Best construct validity; strict scope and dependent on known score, target, legal-ball state.","score_before,target,runs_required,legal_balls_remaining,legal_balls_bowled_before"),
      "wicket_phase_proxy":("Format/phase Q75 wickets lost vs Q25; same match and phase strata only.","Broad context coverage; selection and role confounding; not verified psychological pressure.","wickets_lost_before,innings_phase,match_id"),
      "combined_verified_and_proxy":("RRR>CRR AND high wicket-loss Q75 vs RRR<=CRR AND low wicket-loss Q25; paired by match/phase.","Higher situational specificity, but intersection sharply reduces exposure and inherits proxy tie/selection issues.","verified chase fields plus wickets_lost_before,innings_phase"),}
    for method, cohort in cohorts.items():
        d=descriptions[method]
        for fmt in ["IPL","T20I"]:
            x=cohort.loc[cohort.analysis_format.eq(fmt)]
            for role in ["batter","bowler"]:
                p=players.loc[players.method.eq(method)&players.format.eq(fmt)&players.role.eq(role)]
                summary=p.groupby("existing_floor_decision").size()
                elig=p.loc[p.meets_existing_floors]
                rows.append({"method":method,"format":fmt,"role":role,"pressure_definition":d[0],
                  "advantages_and_biases":d[1],"required_fields":d[2],"paired_pressure_events":int(x.cohort.eq("pressure").sum()),
                  "paired_baseline_events":int(x.cohort.eq("baseline").sum()),
                  "paired_matches":int(x.match_id.nunique()),"paired_match_phase_strata":int(x[["match_id","innings_phase"]].drop_duplicates().shape[0]) if not x.empty else 0,
                  "players_with_both_sides":int((p.pressure_events.gt(0)&p.baseline_events.gt(0)).sum()),
                  "players_meeting_existing_floors":len(elig),"eligible_player_ids":";".join(map(str,elig.player_id.tolist())),
                  "eligible_player_names":";".join(elig.player_name.tolist()),"ineligible_player_pairs":int(summary.get("ineligible",0)),
                  "accepted_external_matches_included":0})
    return pd.DataFrame(rows)


def scoring_design(role:str)->pd.DataFrame:
    if role=="batter":
        rows=[
          ("ordinary-subset strike-rate delta", "pressure SR - baseline SR", "limited", "100 x known ordinary batter runs / ordinary deliveries with known runs", "Never conventional full innings SR; missing-run subset reported"),
          ("ordinary-subset dot-rate improvement", "baseline dot rate - pressure dot rate", "limited", "dots / known ordinary runs", "Extras excluded; missingness may differ by context"),
          ("boundary-event-rate change", "pressure boundary events / ordinary events - baseline rate", "limited", "verified is_four/is_six event flags", "Delivery coverage and denominator limitations remain"),
          ("sample shrinkage", "n_eff/(n_eff+k) multiplied by standardized component delta", "proposed adjustment", "effective events and between-player dispersion", "k calibrated from observed format-specific distribution; report raw and shrunk effects"),
          ("match consistency", "mean match-level delta and fraction of matches with positive effect", "proposed descriptive component", "match IDs and per-match metric", "Requires multiple paired matches; cluster bootstrap preferred"),
          ("uncertainty", "match-cluster bootstrap interval for composite; no iid delivery CI", "required", "paired match clusters", "Current clusters too few for stable intervals"),
        ]
    else:
        rows=[
          ("recognized credited-wicket yield delta", "pressure wickets/observed event - baseline wickets/observed event", "limited", "bowler_wicket_event and observed delivery rows", "Not conventional bowling strike rate; event count is not legal balls"),
          ("sample shrinkage", "n_eff/(n_eff+k) multiplied by standardized yield delta", "proposed adjustment", "effective events and between-player dispersion", "Use only if both cohorts meet evidence floors"),
          ("match consistency", "match-level wicket yield change and fraction of positive matches", "proposed descriptive component", "paired match-level recognized credited wickets and events", "Sparse wickets and few match clusters"),
          ("uncertainty", "match-cluster bootstrap interval", "required", "paired match clusters", "Bowler-conceded runs/economy and conventional bowling SR blocked"),
        ]
    return pd.DataFrame([{"role":role,"component":a,"proposed_calculation":b,"status":c,
      "source_or_weight":d,"limitations":e,"final_weight":"not set; sensitivity only"} for a,b,c,d,e in rows])


def run()->dict[str,int]:
    raw=pd.read_csv(FEATURES,low_memory=False)
    matches=pd.read_csv(RAW/"matches.csv",low_memory=False)
    comps=pd.read_csv(RAW/"competitions.csv",low_memory=False)
    features=filter_confirmed_scope(raw,matches,comps)
    cohorts=pressure_cohorts(features)
    players=player_method_results(features,cohorts)
    sens=eligibility_sensitivity(players)
    comparison=pressure_definition_comparison(cohorts,players)
    comparison.to_csv(REPORTS/"phase5b_pressure_definition_comparison.csv",index=False)
    scoring_design("batter").to_csv(REPORTS/"phase5b_batter_scoring_design.csv",index=False)
    scoring_design("bowler").to_csv(REPORTS/"phase5b_bowler_scoring_design.csv",index=False)
    sens.to_csv(REPORTS/"phase5b_eligibility_sensitivity.csv",index=False)
    (REPORTS/"phase5b_player_method_evidence.csv").write_text(players.to_csv(index=False),encoding="utf-8")
    existing=sens.loc[sens.threshold_tier.eq("existing_Phase2D")]
    broad=sens.loc[sens.threshold_tier.eq("exploratory_empirical_Q25")]
    summary_cols=["method","format","role","players_with_both_sides","players_eligible",
                  "pressure_event_min","pressure_match_min","baseline_event_min","baseline_match_min"]
    existing_summary=existing[summary_cols]
    broad_summary=broad[summary_cols]
    mcounts=comparison[["method","format","role","paired_pressure_events","paired_baseline_events","paired_matches","players_with_both_sides","players_meeting_existing_floors"]]
    lines=["# Phase 5B — Pressure rating methodology and feasibility","",
      "## Scope and evidence guardrails","",
      "Uses supplied official IPL and T20I data from 2022 onward only. Formats are analyzed separately. No external or provider data are included. No player scores, ordered lists, or final rankings are produced. Existing Phase 2D floors and all validation rules remain unchanged.","",
      "## Pressure definitions","",
      "**Verified chase pressure:** RRR > CRR in a regular second innings only when score, target, runs required, balls remaining, and completed legal balls support both rates. RRR <= CRR is the within-match/phase reference. This indicates scoreboard demand, not psychology.","",
      "**Wicket/phase contextual proxy:** within format and innings phase, high wicket depletion at/above Q75 compared with low depletion at/below Q25. Uses known wickets lost and phase; Super Overs excluded. It is broad but confounded by role and match situation, and is never called verified pressure.","",
      "**Combined definition:** intersection of verified RRR > CRR with high wicket depletion; reference is RRR <= CRR with low depletion. Unknown match states cannot enter. This is the most specific definition and the sparsest.","",
      "Each comparison requires both classes within the same match and innings phase. Baseline observations can differ in wickets lost; that imbalance is disclosed rather than hidden. The combined method requires reliable fields already populated on the same delivery, but the wicket/phase input remains limited and its added restriction is exploratory.","",
      "## Coverage and existing-floor eligibility","",md_table(comparison),"",
      "## Player qualification and exclusions","",
      "`phase5b_eligibility_sensitivity.csv` reports eligible player IDs/names by method, format, role, and threshold, plus exposure and exclusion reasons. The companion `phase5b_player_method_evidence.csv` contains each player-format-method decision, including ineligible rows. Eligibility is evidence eligibility, not ranking.","",
      "Existing floor results:","",md_table(existing_summary),"",
      "The data-derived Q25 tier is a sensitivity proposal only. It uses observed per-player pressure/baseline event Q25 and at least two matches on each side. It is explicitly looser than the inherited batter baseline match/event requirement in some strata and must not replace the official floor without review:","",md_table(broad_summary),"",
      "## Role-specific rating model design","",
      "Batter components: ordinary-subset strike-rate delta (60%), dot-rate improvement (20%), and boundary-event-rate change (20%) as a Phase 3A starting scenario. Also test 100/0/0, 50/25/25, and 40/30/30. Components would be standardized within format; weights remain provisional and no composite is computed here. Missing ordinary-run rows are excluded from run-rate denominators and coverage is reported per cohort.","",
      "Bowler component: recognized bowler-credit wickets per observed delivery event, pressure minus baseline. Do not call this bowling strike rate. Economy and conventional bowling strike rate remain blocked because conceded runs and legal-ball denominators are incomplete. With only one outcome, bowler component weights are not meaningful.","",
      "For both roles, any future rating should shrink noisy player effects toward the format mean using an empirically calibrated effective-sample factor; report raw and shrunk estimates. Estimate consistency from paired match-level effects, not delivery independence. Use match-cluster bootstrap uncertainty only when enough distinct clusters exist; current samples are too sparse for stable intervals.","",
      "## Weight and threshold sensitivity","",
      "Phase 5A sensitivity tested SR-only, 60/20/20, 50/25/25, and 40/30/30. Among only 18 T20I batter pairs with all three deltas, Spearman agreement with 60/20/20 ranged 0.962–0.988; this tiny, under-floor subset cannot validate weights. IPL had two such pairs and no eligible players. No bowler score-weight sensitivity is defensible with one eligible outcome and no reliable economy denominator.","",
      "Existing floors remain the decision standard. Q25 thresholds are shown only as exploratory alternatives; they may create names but do not establish defensibility. Match consistency and clustered uncertainty cannot be adequately estimated from the current handful of paired matches.","",
      "## Top 10 feasibility","",
      "No pressure definition supports defensible Top 10 batter or bowler lists. The verified method has 0 eligible player-format pairs under existing floors. Proxy-based names are context-dependent, with incomplete batter metric coverage and wicket/phase confounding; using that proxy as a substitute would change the construct. Combined evidence is a smaller intersection, not a remedy. The exact blockers are too few matched pressure/baseline matches per player, unresolved scoring events and state coverage, and for bowlers missing conceded runs and complete legal-ball denominators.","",
      "## Output interpretation","",
      "The CSVs are methodology/feasibility artifacts, not player rankings. Candidate names are shown only to explain whether and why exposure criteria pass. No ordering or final rating is released."]
    (REPORTS/"phase5b_rating_methodology.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    return {"scope_deliveries":len(features),"player_method_rows":len(players),
      "verified_floor_eligible":int(existing.loc[existing.method.eq("verified_chase"),"players_eligible"].sum()),
      "proxy_floor_eligible":int(existing.loc[existing.method.eq("wicket_phase_proxy"),"players_eligible"].sum()),
      "combined_floor_eligible":int(existing.loc[existing.method.eq("combined_verified_and_proxy"),"players_eligible"].sum())}


if __name__=="__main__":
    print(json.dumps(run(),indent=2))
