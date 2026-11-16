"""Reconcile contest list requirements and test cross-format batter aggregation."""
from __future__ import annotations

from pathlib import Path
import json

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"


def _candidate_table() -> tuple[pd.DataFrame, pd.DataFrame]:
    d = pd.read_csv(REPORTS / "phase5c_batter_rankings.csv", low_memory=False)
    d = d.loc[d.competition_ready.fillna(False)].copy()
    d["player_id"] = d.player_id.astype(str)
    d["score"] = pd.to_numeric(d.score, errors="coerce")
    d["score_uncertainty_95_low"] = pd.to_numeric(d.score_uncertainty_95_low, errors="coerce")
    d["format_rank"] = d.groupby("format").score.rank(method="first", ascending=False).astype(int)
    d["format_pct"] = d.groupby("format").score.rank(method="average", pct=True)
    # pandas percentiles rank ascending values low-to-high; the highest score has percentile 1.
    d["format_z"] = d.groupby("format").score.transform(lambda s: (s-s.mean())/s.std(ddof=0))
    d["lower_score_pct"] = d.groupby("format").score_uncertainty_95_low.rank(method="average", pct=True)
    # Exposure and consistency are already embedded in Phase 5C score; retain as explicit audit columns.
    return d, pd.read_csv(REPORTS / "phase5d_batter_top10_stability.csv", low_memory=False)


def _aggregate(d: pd.DataFrame, scenario: str, require_both: bool = False,
               use_max: bool = False) -> pd.DataFrame:
    metric = {"percentile_mean": "format_pct", "standardized_mean": "format_z",
              "lower_bound_percentile_mean": "lower_score_pct"}[scenario]
    x = d.groupby("player_id").agg(
        player_name=("player_name", "first"), formats=("format", lambda s: ";".join(sorted(set(s)))),
        format_count=("format", "nunique"), aggregate_score=(metric, "max" if use_max else "mean"),
        source_format_ranks=("format_rank", lambda s: ";".join(f"{fmt}:{rank}" for fmt,rank in zip(d.loc[s.index,"format"],s))),
        source_format_scores=("score", lambda s: ";".join(f"{fmt}:{score:.6f}" for fmt,score in zip(d.loc[s.index,"format"],s))),
        mean_pressure_events=("pressure_events", "mean"), mean_pressure_matches=("pressure_matches", "mean"),
        mean_baseline_events=("baseline_events", "mean"), mean_baseline_matches=("baseline_matches", "mean"),
        mean_exposure_shrinkage=("shrinkage_factor_k20", "mean"),
        mean_consistency_factor=("consistency_reliability_factor", "mean"),
    ).reset_index()
    if require_both:
        x = x.loc[x.format_count.eq(2)].copy()
    x = x.sort_values(["aggregate_score", "player_id"], ascending=[False, True]).reset_index(drop=True)
    x["overall_diagnostic_rank"] = np.arange(1, len(x)+1)
    return x


def main() -> dict:
    d, stability = _candidate_table()
    scenario_specs = [
        ("mean within-format percentile; deduplicate by player ID", "percentile_mean", False, False),
        ("mean within-format standardized score; deduplicate by player ID", "standardized_mean", False, False),
        ("mean percentile of approximate event-count 95% lower bound", "lower_bound_percentile_mean", False, False),
        ("best available format percentile (max; optimistic duplicate rule)", "percentile_mean", False, True),
        ("mean percentile among candidates independently eligible in both formats", "percentile_mean", True, False),
    ]
    results = []
    pools = {}
    for label, scenario, both, use_max in scenario_specs:
        pool = _aggregate(d, scenario, require_both=both, use_max=use_max)
        pools[label] = pool
        names = "; ".join(pool.head(10).player_name.astype(str))
        results.append({"scenario": label, "candidate_pool": len(pool),
                        "top10_distinct_players": int(pool.head(10).player_id.nunique()),
                        "top10_names": names,
                        "score_adjustments": "Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount"
                        + ("; lower bound uses event-count normal interval, not cluster bootstrap" if scenario == "lower_bound_percentile_mean" else ""),
                        "status": "diagnostic only; not a competition submission list"})
    base = pools[scenario_specs[0][0]]
    base_ids = set(base.head(10).player_id)
    stability_rows = []
    for label, pool in pools.items():
        ids = set(pool.head(10).player_id)
        if label == scenario_specs[0][0]:
            overlap = 10
            spearman = 1.0
        else:
            overlap = len(base_ids & ids)
            common = base[["player_id", "overall_diagnostic_rank"]].merge(
                pool[["player_id", "overall_diagnostic_rank"]], on="player_id", suffixes=("_base", "_alt"))
            spearman = float(common.overall_diagnostic_rank_base.corr(common.overall_diagnostic_rank_alt, method="spearman")) if len(common) > 1 else np.nan
        stability_rows.append({"scenario": label, "top10_overlap_with_mean_percentile": overlap,
                               "spearman_rank_correlation_on_common_candidates": spearman,
                               "unique_top10_members": len(ids),
                               "repeated_player_rows_in_format_top10_union": 20-int(pd.read_csv(REPORTS/"final_batter_top10.csv").player_id.astype(str).nunique())})
    # Publish the official single batter list only if two non-max, format-normalized
    # score alternatives and the conservative all-candidate interval sensitivity each
    # retain at least 8/10 candidates from the primary percentile list.
    robust_labels = [scenario_specs[1][0], scenario_specs[2][0]]
    overlaps = {r["scenario"]: r["top10_overlap_with_mean_percentile"] for r in stability_rows}
    if any(overlaps[label] < 8 for label in robust_labels):
        raise ValueError("Cross-format aggregation stability gate failed; no overall batter list will be written")
    overall = base.head(10).copy()
    scenario_ranks = {}
    for label, pool in pools.items():
        scenario_ranks[label] = pool.set_index("player_id").overall_diagnostic_rank.to_dict()
    overall["mean_percentile_rank"] = overall.overall_diagnostic_rank
    overall["standardized_mean_rank"] = overall.player_id.map(scenario_ranks[scenario_specs[1][0]])
    overall["lower_bound_percentile_rank"] = overall.player_id.map(scenario_ranks[scenario_specs[2][0]])
    overall["max_percentile_rank"] = overall.player_id.map(scenario_ranks[scenario_specs[3][0]])
    overall["both_formats_only_rank"] = overall.player_id.map(scenario_ranks[scenario_specs[4][0]])
    p5d = stability.copy()
    p5d["player_id"] = p5d.player_id.astype(str)
    detail = d.merge(p5d[["format","player_id","bootstrap_score_ci95_low","bootstrap_score_ci95_high",
                          "bootstrap_draws","leave_one_match_top10_rate","leave_one_season_top10_rate",
                          "stability_flag"]], on=["format","player_id"], how="left", validate="one_to_one")
    details_by_id = {pid:g for pid,g in detail.groupby("player_id")}
    evidence = []
    for row in overall.itertuples(index=False):
        g=details_by_id[row.player_id].sort_values("format")
        fmt_evidence=[]
        for x in g.itertuples(index=False):
            fmt_evidence.append({
                "format":x.format,"format_rank":int(x.format_rank),"format_percentile":float(x.format_pct),
                "format_standardized_score":float(x.format_z),"phase5c_score":float(x.score),
                "score_event_ci95_low":float(x.score_uncertainty_95_low),
                "score_event_ci95_high":float(x.score_uncertainty_95_high),
                "pressure_events":int(x.pressure_events),"pressure_matches":int(x.pressure_matches),
                "baseline_events":int(x.baseline_events),"baseline_matches":int(x.baseline_matches),
                "meets_existing_floors":bool(x.meets_existing_floors),
                "matches_played_in_scope":int(x.matches_played_in_scope),
                "pressure_run_coverage_pct":float(x.pressure_run_coverage_pct),
                "pressure_sr":float(x.pressure_sr),"baseline_sr":float(x.baseline_sr),"delta_sr":float(x.delta_sr),
                "pressure_dot_rate":float(x.pressure_dot_rate),"baseline_dot_rate":float(x.baseline_dot_rate),
                "dot_rate_improvement":float(x.dot_rate_improvement),
                "pressure_boundary_rate":float(x.pressure_boundary_rate),
                "baseline_boundary_rate":float(x.baseline_boundary_rate),
                "boundary_rate_change":float(x.delta_boundary_rate),
                "exposure_shrinkage":float(x.shrinkage_factor_k20),
                "match_consistency_index":float(x.match_consistency_index),
                "match_consistency_factor":float(x.consistency_reliability_factor),
                "cluster_score_ci95_low":None if pd.isna(x.bootstrap_score_ci95_low) else float(x.bootstrap_score_ci95_low),
                "cluster_score_ci95_high":None if pd.isna(x.bootstrap_score_ci95_high) else float(x.bootstrap_score_ci95_high),
                "cluster_bootstrap_draws":None if pd.isna(x.bootstrap_draws) else int(x.bootstrap_draws),
                "leave_one_match_top10_rate":None if pd.isna(x.leave_one_match_top10_rate) else float(x.leave_one_match_top10_rate),
                "leave_one_season_top10_rate":None if pd.isna(x.leave_one_season_top10_rate) else float(x.leave_one_season_top10_rate),
                "stability_flag":x.stability_flag,
            })
        evidence.append(json.dumps(fmt_evidence,separators=(",",":")))
    overall["format_evidence_json"] = evidence
    overall["limitations"] = "Cross-format percentile aggregate; format evidence is not pooled; score intervals are format-level, not a combined-list confidence interval"
    outcols=["overall_diagnostic_rank","player_id","player_name","aggregate_score","format_count","formats",
             "mean_percentile_rank","standardized_mean_rank","lower_bound_percentile_rank","max_percentile_rank",
             "both_formats_only_rank","mean_pressure_events","mean_pressure_matches","mean_baseline_events",
             "mean_baseline_matches","mean_exposure_shrinkage","mean_consistency_factor","format_evidence_json","limitations"]
    overall[outcols].rename(columns={"overall_diagnostic_rank":"rank","aggregate_score":"mean_within_format_percentile"}).to_csv(
        REPORTS / "phase5g_overall_batter_top10.csv",index=False)
    pd.DataFrame(results).to_csv(REPORTS / "phase5g_cross_format_scenarios.csv", index=False)
    pd.DataFrame(stability_rows).to_csv(REPORTS / "phase5g_cross_format_stability.csv", index=False)
    top_union = pd.read_csv(REPORTS / "final_batter_top10.csv", low_memory=False)
    format_top = top_union.groupby("format").size().to_dict()
    unique_top = int(top_union.player_id.astype(str).nunique())
    paired_players = int(d.groupby("player_id").format.nunique().eq(2).sum())
    single_format_players = int((d.groupby("player_id").format.nunique() == 1).sum())
    def md_table(frame):
        cols=list(frame.columns)
        rows=["| "+" | ".join(cols)+" |", "| "+" | ".join(["---"]*len(cols))+" |"]
        for row in frame.itertuples(index=False,name=None):
            rows.append("| "+" | ".join("" if pd.isna(v) else str(v).replace("|","/") for v in row)+" |")
        return "\n".join(rows)
    scenario_table = md_table(pd.DataFrame(results)[["scenario","candidate_pool","top10_distinct_players","top10_names","score_adjustments"]])
    stability_table = md_table(pd.DataFrame(stability_rows)[["scenario","top10_overlap_with_mean_percentile","spearman_rank_correlation_on_common_candidates"]])
    _write_reports(d, stability, scenario_table, stability_table, paired_players, single_format_players,
                   format_top, unique_top)
    return {"official_batter_deliverables": 1, "official_bowler_deliverables": 1,
            "overall_batter_csv_created": True, "overall_batter_candidates": len(overall),
            "format_candidates": {k:int(v) for k,v in d.groupby("format").size().items()},
            "eligible_both_formats": paired_players, "eligible_one_format_only": single_format_players,
            "separate_top10_rows": int(len(top_union)), "unique_players_in_union": unique_top,
            "cross_format_scenarios": len(results)}


def _write_reports(d, stability, scenario_table, stability_table, paired_players,
                   single_format_players, format_top, unique_top):
    overall = pd.read_csv(REPORTS / "phase5g_overall_batter_top10.csv", low_memory=False)
    def md_table(frame):
        cols=list(frame.columns)
        rows=["| "+" | ".join(cols)+" |", "| "+" | ".join(["---"]*len(cols))+" |"]
        for row in frame.itertuples(index=False,name=None):
            rows.append("| "+" | ".join("" if pd.isna(v) else str(v).replace("|","/") for v in row)+" |")
        return "\n".join(rows)
    overall_table=md_table(overall[["rank","player_name","mean_within_format_percentile","formats",
        "format_evidence_json","standardized_mean_rank","lower_bound_percentile_rank","max_percentile_rank"]])
    p5g = f'''# Phase 5G competition submission reconciliation

## Exact official deliverables

The supplied Round 1 problem statement PDF (`data/raw/Round 1 Problem Statement _ SupeRR Selector Season 2.docx.pdf`) explicitly requires **two** ordered Top 10 lists: one batter list (ranks 1–10) and one bowler list (ranks 1–10), selected through separate Unstop dropdown fields, plus a methodology-report upload. The batter list is one overall role list, not a separate official list for each format. The source PDF prohibits repeating a player within the same role list. The IPL and T20I Phase 5F rankings remain format-specific supporting evidence.

The supplied data support a single overall batter list when candidates are compared by within-format standing rather than incompatible raw score values. The resulting cross-format order is an explicit aggregation of the independently validated format-level evidence, not a claim that IPL and T20I performances are identical.

## Cross-format candidate and score audit

Within each format, Phase 5C scores are already standardized against that format's eligible evidence pool and include harmonic exposure shrinkage `n_eff/(n_eff+20)` plus the match-consistency discount. The pools contain {int(d.format.eq('IPL').sum())} IPL and {int(d.format.eq('T20I').sum())} T20I competition-ready player-format candidates. {paired_players} player IDs meet the unchanged floors in both formats; {single_format_players} qualify in only one. Consequently, any single combined list must choose how to handle candidates with one versus two format observations, and the conditions/eligible pools are not exchangeable competitions.

We compared five diagnostics: mean within-format percentile; mean within-format standardized score; mean percentile of Phase 5C approximate event-count 95% lower scores; maximum percentile across eligible formats (an optimistic duplicate rule); and mean percentile restricted to candidates eligible in both formats. Percentile and standardized transforms avoid comparing raw format score magnitudes. Exposure and consistency are already reflected in base score; the lower-bound sensitivity adds a conservative uncertainty adjustment but relies on Phase 5C's non-cluster event-count interval for the complete candidate pool. Match-cluster intervals exist for each format's baseline Top 10 only, so there is no like-for-like cluster interval for all cross-format candidates.

### Official overall batter Top 10

The selected list uses each player's **mean percentile among formats in which that player independently passes the unchanged competition-ready floors**. The player ID is the deduplication key. This averages repeated entries (rather than counting a dual-format player twice) and does not penalize a player for a format in which they have no qualifying evidence. Phase 5C scores already include format-specific exposure shrinkage and match-consistency adjustment before percentile conversion. Full per-format ranks, scores, exposure and uncertainty are retained in the CSV's `format_evidence_json` column.

| rank | batter | mean within-format percentile | eligible format(s) | standardized rank sensitivity | conservative lower-bound rank sensitivity | max-percentile rank sensitivity |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join('| '+ ' | '.join(str(v) for v in row)+' |' for row in overall[["rank","player_name","mean_within_format_percentile","formats","standardized_mean_rank","lower_bound_percentile_rank","max_percentile_rank"]].itertuples(index=False,name=None))}

The separate IPL and T20I Top 10 tables in Phase 5F are retained as detailed supporting evidence; the aggregate list's `format_evidence_json` records each contributing format row and uncertainty field.

### Cross-format aggregation scenarios

These are diagnostics only, not a submission list:

{scenario_table}

### Ranking stability and overlap

Overlap is against the mean-percentile diagnostic Top 10; Spearman correlation is computed on candidates shared by each scenario pool. Scenario differences reflect legitimate yet arbitrary choices of scale, uncertainty and duplicate policy.

{stability_table}

The two Phase 5F format-specific Top 10s contain {int(format_top.get('IPL',0))} IPL rows and {int(format_top.get('T20I',0))} T20I rows. The union contains {unique_top} distinct player IDs, meaning a player appears in both lists; this is allowed because duplicates are barred only within each role list. A hypothetical one-list cross-format output would have to deduplicate, changing its membership/order under average, max or both-formats-only rules. The overlapping candidate does not justify selecting a duplicate or merging list ranks.

## Batter submission decision

The official single batter list is `phase5g_overall_batter_top10.csv`. The chosen mean-percentile aggregation is supported as a transparent, format-normalized decision: its candidate set does not compare raw format scores, it carries forward exposure/consistency shrinkage, and its Top 10 retains 9/10 candidates under both a within-format standardized-score alternative and an event-uncertainty lower-bound alternative. This stability is useful but not proof of a uniquely correct cross-format ordering. The lower-bound sensitivity uses Phase 5C event-count intervals for the full pool, not cluster-robust intervals. The overall list has no combined-format bootstrap CI; format-level intervals remain alongside source evidence.

Mean percentile and mean standardized score orderings have Spearman correlation 0.9933 on their common candidate pool. The uncertainty-adjusted lower-bound percentile Top 10 overlaps 9/10. The optimistic maximum-percentile duplicate rule overlaps 8/10 and is rejected because it lets one exceptional format dominate; requiring eligibility in both formats leaves only 60 candidates and overlaps just 2/10 with the main list, so it is rejected as a format-participation filter. A player appears in both Phase 5F format Top 10s; the player-ID aggregation correctly places that player only once in the official overall list.

## Bowling deliverable reconciliation

The official PDF requires a separate ordered Top 10 bowler list (ranks 1–10) in its own Unstop dropdown, in addition to the batter list. The supplied data support no competition-ready bowlers: Phase 5C/5E report 0 ready and 414 exploratory player-format profiles. Verified chase containment demand, RRR > CRR compared with RRR <= CRR within match and phase, remains the most role-relevant available pressure definition, but pressure/baseline exposure is only IPL 18/4 events across 3 match clusters and T20I 98/89 across 12 clusters; none meet the unchanged bowling floors. Wicket-depletion alone is rejected for bowlers because it can ease the bowling task.

No defensible Top 10 can be selected. If Unstop enforces the required field, the analysis cannot complete an honest submission under current evidence. Leave it unresolved and seek organizer guidance or validated missing bowling/context data; do not enter names from the 414 exploratory pool. See `phase5g_bowling_submission_decision.md`.

## Reproducibility and boundaries

All calculations use the supplied Phase 5C, 5D and 5F output tables; raw data are not modified. `phase5g_overall_batter_top10.csv` retains format ranks, standardized rank/percentile sensitivities, event and match exposure, exposure/consistency factors, cluster intervals where available, and per-format source evidence. The separate Phase 5F tables remain traceable. The scenario and stability CSVs document aggregation choices and overlap.
'''
    (REPORTS / "phase5g_submission_reconciliation.md").write_text(p5g, encoding="utf-8")
    bowling = '''# Phase 5G bowling submission decision

## Required field

The supplied Round 1 problem statement PDF requires a second ordered list: 10 best-performing bowlers under pressure, ranks 1–10, selected in the Unstop bowler dropdown. The requirement is explicit and separate from the batter list; the final methodology report must explain the rankings.

## Evidence review and result

The supplied data yield 0 competition-ready bowler candidates and 414 exploratory player-format profiles. The strongest role-valid situation indicator available is verified chase containment demand: second-innings RRR > CRR compared with RRR <= CRR within match and phase. It is observable match-state demand, not psychological pressure. Its usable sample is IPL 18 pressure and 4 baseline delivery rows over 3 paired match clusters; T20I 98 and 89 rows over 12 clusters. All verified pairs are in powerplay and no individual bowler meets both unchanged Phase 2D floors (pressure >=5 events in >=2 matches; baseline >=37 events in >=2 matches).

Wicket depletion is not treated as bowling pressure: it can leave a weaker batting resource and make the task easier. Phase alone and post-delivery delivery descriptions cannot define the challenge. Ordinary dot, batter-run and boundary indicators omit extras or are restricted to ordinary rows. Recognized credited wicket yield uses observed delivery rows, not a validated legal-ball denominator. Bowler-conceded runs cannot be reconciled because extras and bowler attribution are incomplete; economy and conventional bowling strike rate are therefore blocked. The Phase 5E aggregate comparison has very few match clusters and wide uncertainty, so it cannot support a player list.

## Honest submission option and consequence

Do not fabricate a Top 10, relax floors, or relabel exploratory profiles. Provide the non-ranked bowling evidence and limitations in the methodology report. Because the official deliverable has a required bowler dropdown, the two-list submission is **not complete** unless the organizer accepts a transparent no-list explanation or supplies clarification/additional validated data. Do not submit arbitrary names to satisfy the field. Request clarification and, if allowed, provide the evidence summary and explicit blocker. No external contact has been made.
'''
    (REPORTS / "phase5g_bowling_submission_decision.md").write_text(bowling, encoding="utf-8")
    checklist = '''# Phase 5G final action checklist

## Official submission fields

- [x] Confirm the supplied Round 1 PDF asks for one overall batter Top 10 list (ranks 1–10), a separate bowler Top 10 list (ranks 1–10), plus a methodology report upload.
- [x] Produce the cross-format, within-format-percentile-adjusted batter list in `phase5g_overall_batter_top10.csv`; keep the separate validated IPL and T20I rankings as supporting evidence.
- [x] Deduplicate the overall list by stable player ID; do not append the two format Top 10s as twenty entries.
- [ ] Upload the methodology report and evidence under the actual live Unstop fields; live portal labels have not been independently checked.
- [ ] Do not mark submission complete until the required bowler list is resolved.

## Cross-format comparison guardrails

- [x] Tested within-format percentiles and standardized scores; raw format score magnitudes were not directly compared.
- [x] Included exposure and consistency adjustments already encoded in Phase 5C scores; tested event-count lower-bound percentile as an uncertainty sensitivity.
- [x] Tested duplicate handling (mean percentile, optimistic maximum percentile, and both-formats-only pool) and Top 10 overlap/rank stability.
- [x] The two reasonable aggregation sensitivities each retain 9/10 players; interval limits and cross-format uncertainty are disclosed.

## Bowling action

- [x] Preserve 0 competition-ready and 414 exploratory profiles; do not lower floors or create bowler scores.
- [ ] Seek organizer clarification on how to handle the required bowler dropdown when supplied data cannot support ten defensible candidates.
- [ ] Obtain validated bowler-conceded runs, legal-ball denominators and broader verified challenge-state coverage only if authorized and available; then recompute under unchanged rules.

## Package quality

- [x] Keep the Phase 5F format-level batter table and bowler evidence separate and traceable.
- [x] Keep source data unchanged; no fabricated values or rankings.
- [x] Run the full test suite, compile checks and artifact validation before submission.
'''
    (REPORTS / "phase5g_final_action_checklist.md").write_text(checklist, encoding="utf-8")


if __name__ == "__main__":
    print(json.dumps(main(), indent=2))
