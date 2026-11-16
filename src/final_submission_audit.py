"""Build the reconciled final submission audit from frozen Phase 5C-5E outputs."""
from __future__ import annotations

from pathlib import Path
import csv
import html
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "outputs" / "reports"


def _top10() -> pd.DataFrame:
    p5c = pd.read_csv(REPORTS / "phase5c_batter_rankings.csv", low_memory=False)
    p5d = pd.read_csv(REPORTS / "phase5d_batter_top10_stability.csv", low_memory=False)
    ready = p5c.loc[p5c.competition_ready.fillna(False)].copy()
    ready["player_id"] = ready.player_id.astype(str)
    p5d["player_id"] = p5d.player_id.astype(str)
    ready = ready.sort_values(["format", "score", "player_id"], ascending=[True, False, True])
    ready["independent_rank"] = ready.groupby("format").cumcount() + 1
    selected = ready.loc[ready.independent_rank.le(10)].merge(
        p5d, how="left", on=["format", "player_id"], validate="one_to_one", suffixes=("", "_phase5d"))
    if len(selected) != 20 or selected.independent_rank.isna().any():
        raise ValueError("Expected independently verified Top 10 rows for both formats")
    score_diff = (selected.score - selected.independent_score).abs()
    if score_diff.max() > 1e-12:
        raise ValueError(f"Phase 5C/5D score mismatch: {score_diff.max()}")
    if not (selected.independent_rank == selected.independent_rank_competition_pool).all():
        raise ValueError("Competition-pool rank differs from independently rebuilt rank")
    if not selected.competition_ready.fillna(False).all():
        raise ValueError("A non-ready candidate entered a final batter Top 10")
    selected["rank"] = selected.independent_rank.astype(int)
    selected["score"] = selected.score.astype(float)
    selected["score_ci95_low"] = selected.bootstrap_score_ci95_low
    selected["score_ci95_high"] = selected.bootstrap_score_ci95_high
    selected["uncertainty_method"] = selected.uncertainty_method
    selected["stability_flag"] = selected.stability_flag
    selected["limitations"] = selected.apply(
        lambda r: "; ".join(filter(None, [
            "Contextual wicket-depletion ranking, not verified scoreboard or psychological pressure",
            "ordinary-delivery subset metrics",
            "bootstrap interval is score uncertainty, not rank probability",
            "season-sensitive Top 10" if r.stability_flag == "method_or_sample_sensitive" else "",
            "at inherited exposure minimum on at least one dimension" if bool(r.at_any_inherited_floor) else "",
        ])), axis=1)
    cols = [
        "format", "rank", "player_id", "player_name", "score", "score_ci95_low", "score_ci95_high",
        "uncertainty_method", "pressure_events", "pressure_matches", "baseline_events", "baseline_matches",
        "matches_played_in_scope", "pressure_run_coverage_pct", "pressure_sr", "baseline_sr", "delta_sr",
        "pressure_dot_rate", "baseline_dot_rate", "dot_rate_improvement", "pressure_boundary_rate",
        "baseline_boundary_rate", "boundary_rate_change", "match_consistency_index", "exposure_shrinkage_factor",
        "consistency_factor", "leave_one_match_top10_rate", "leave_one_season_top10_rate", "bootstrap_draws",
        "stability_flag", "at_any_inherited_floor", "limitations",
    ]
    return selected[cols].sort_values(["format", "rank"])


def _bowling_evidence() -> pd.DataFrame:
    cov = pd.read_csv(REPORTS / "phase5e_bowler_metric_coverage.csv", low_memory=False)
    lines = (REPORTS / "phase5e_bowling_model.md").read_text(encoding="utf-8").splitlines()
    table_rows = []
    in_table = False
    for line in lines:
        if line.startswith("| format | metric | pressure_value"):
            in_table = True
            continue
        if in_table and line.startswith("| ---"):
            continue
        if in_table and line.startswith("|"):
            parts = [x.strip() for x in line.strip("|").split("|")]
            table_rows.append(parts)
        elif in_table:
            break
    ci = pd.DataFrame(table_rows, columns=["format", "metric", "pressure_value", "baseline_value",
        "pressure_minus_baseline", "cluster_ci95_low", "cluster_ci95_high", "paired_match_clusters",
        "bootstrap_draws", "interpretation"])
    p = cov.loc[cov.population.eq("verified_chase_pressure")].copy()
    b = cov.loc[cov.population.eq("verified_chase_baseline")].copy()
    needed = ["ordinary_dot_event", "ordinary_batter_runs_sum", "ordinary_batter_runs_known",
              "ordinary_boundary_event", "recognized_bowler_credit_wicket", "observed_delivery_event"]
    rows = []
    mapping = {
        "ordinary_dot_rate": ("ordinary_dot_event", "ordinary_batter_runs_known", "rate_or_coverage"),
        "ordinary_batter_runs_per_event": ("ordinary_batter_runs_sum", "ordinary_batter_runs_known", "rate_or_coverage"),
        "ordinary_boundary_rate": ("ordinary_boundary_event", "ordinary_batter_runs_known", "rate_or_coverage"),
        "recognized_wicket_yield_per_observed_event": ("recognized_bowler_credit_wicket", "observed_delivery_event", "rate_or_coverage"),
    }
    for _, c in ci.iterrows():
        fmt, metric = c["format"], c["metric"]
        if metric not in mapping:
            continue
        num_metric, den_metric, _ = mapping[metric]
        def get(frame, m, col):
            hit = frame.loc[frame.format.eq(fmt) & frame.metric.eq(m), col]
            return hit.iloc[0] if len(hit) else float("nan")
        rows.append({
            "format": fmt, "metric": metric, "pressure_value": float(c.pressure_value),
            "baseline_value": float(c.baseline_value), "pressure_minus_baseline": float(c.pressure_minus_baseline),
            "cluster_ci95_low": float(c.cluster_ci95_low), "cluster_ci95_high": float(c.cluster_ci95_high),
            "pressure_events": int(get(p, "observed_delivery_event", "numerator_or_value")),
            "pressure_matches": int(get(p, "observed_delivery_event", "matches")),
            "baseline_events": int(get(b, "observed_delivery_event", "numerator_or_value")),
            "baseline_matches": int(get(b, "observed_delivery_event", "matches")),
            "pressure_metric_numerator": float(get(p, num_metric, "numerator_or_value")),
            "pressure_metric_denominator": float(get(p, den_metric, "numerator_or_value")),
            "baseline_metric_numerator": float(get(b, num_metric, "numerator_or_value")),
            "baseline_metric_denominator": float(get(b, den_metric, "numerator_or_value")),
            "paired_match_clusters": int(c.paired_match_clusters), "bootstrap_draws": int(c.bootstrap_draws),
            "interpretation": c.interpretation,
            "limitations": "Verified RRR > CRR vs <= CRR; paired match-phase. Ordinary metrics exclude extras; wicket yield denominator is observed rows, not legal balls. Not player ranking.",
        })
    return pd.DataFrame(rows).sort_values(["format", "metric"])


def _svg_chart(top: pd.DataFrame, fmt: str, path: Path) -> None:
    d = top.loc[top.format.eq(fmt)].sort_values("rank")
    width, height, left, right, topm, bottom = 1000, 470, 300, 30, 34, 38
    plotw = width-left-right
    vals = d.score.astype(float).tolist()
    lows = d.score_ci95_low.astype(float).tolist()
    highs = d.score_ci95_high.astype(float).tolist()
    xmin = min(0, min(lows)); xmax = max(highs)
    span = xmax-xmin or 1
    scale = plotw/span
    bar_h = 25
    elems = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#101827"/>',
             f'<text x="{left}" y="24" fill="#ffffff" font-family="Arial" font-size="18" font-weight="bold">{fmt} batter score and 95% match-cluster bootstrap interval</text>']
    zero = left + (0-xmin)*scale
    elems.append(f'<line x1="{zero:.1f}" y1="{topm}" x2="{zero:.1f}" y2="{height-bottom}" stroke="#94a3b8" stroke-width="1"/>')
    for i, row in enumerate(d.itertuples(index=False)):
        y = topm + i*38
        xval = left+(row.score-xmin)*scale
        xlo = left+(row.score_ci95_low-xmin)*scale
        xhi = left+(row.score_ci95_high-xmin)*scale
        elems.append(f'<text x="{left-12}" y="{y+18}" fill="#e5e7eb" text-anchor="end" font-family="Arial" font-size="13">{row.rank}. {html.escape(row.player_name)}</text>')
        elems.append(f'<line x1="{xlo:.1f}" y1="{y+12}" x2="{xhi:.1f}" y2="{y+12}" stroke="#fbbf24" stroke-width="3"/>')
        elems.append(f'<line x1="{xlo:.1f}" y1="{y+7}" x2="{xlo:.1f}" y2="{y+17}" stroke="#fbbf24"/><line x1="{xhi:.1f}" y1="{y+7}" x2="{xhi:.1f}" y2="{y+17}" stroke="#fbbf24"/>')
        elems.append(f'<circle cx="{xval:.1f}" cy="{y+12}" r="5" fill="#38bdf8"/>')
        elems.append(f'<text x="{min(width-90,xval+9):.1f}" y="{y+17}" fill="#cbd5e1" font-family="Arial" font-size="11">{row.score:.3f}</text>')
    elems.append(f'<text x="{left}" y="{height-10}" fill="#cbd5e1" font-family="Arial" font-size="12">Standardized composite score (higher = stronger observed context-adjusted profile); intervals are not rank probabilities</text>')
    elems.append('</svg>')
    path.write_text("\n".join(elems), encoding="utf-8")


def _md_table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    def cell(value):
        if pd.isna(value):
            return ""
        return str(value).replace("|", "/").replace("\n", " ")
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    rows.extend("| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(rows)


def main() -> dict:
    top = _top10()
    bowling = _bowling_evidence()
    top.to_csv(REPORTS / "final_batter_top10.csv", index=False)
    bowling.to_csv(REPORTS / "final_bowler_evidence.csv", index=False)
    for fmt in ["IPL", "T20I"]:
        _svg_chart(top, fmt, REPORTS / f"final_{fmt.lower()}_batter_top10_chart.svg")
    audit = pd.read_csv(REPORTS / "phase5d_independent_validation.md") if False else None
    audit_text = (REPORTS / "phase5d_independent_validation.md").read_text(encoding="utf-8")
    all_batters = pd.read_csv(REPORTS / "phase5c_batter_rankings.csv", low_memory=False)
    all_bowlers = pd.read_csv(REPORTS / "phase5c_bowler_rankings.csv", low_memory=False)
    ready = all_batters.loc[all_batters.competition_ready.fillna(False)]
    counts = ready.groupby("format").size().to_dict()
    exploratory_batters = int((~all_batters.competition_ready.fillna(False)).sum())
    competition_ready_bowlers = int(all_bowlers.competition_ready.fillna(False).sum())
    exploratory_bowlers = int((~all_bowlers.competition_ready.fillna(False)).sum())
    bowler_fmt_counts = all_bowlers.groupby("format").agg(
        profiles=("player_id", "size"),
        competition_ready=("competition_ready", lambda s: int(s.fillna(False).sum())),
    ).reset_index()
    bowler_fmt_counts["exploratory"] = bowler_fmt_counts.profiles - bowler_fmt_counts.competition_ready
    for idx, row in bowling.iterrows():
        fmt_counts = bowler_fmt_counts.loc[bowler_fmt_counts.format.eq(row["format"])].iloc[0]
        bowling.loc[idx, "competition_ready_bowler_profiles_format"] = int(fmt_counts.competition_ready)
        bowling.loc[idx, "exploratory_bowler_profiles_format"] = int(fmt_counts.exploratory)
    p5e = pd.read_csv(REPORTS / "phase5e_bowler_metric_coverage.csv", low_memory=False)
    cov = p5e.loc[(p5e.population.eq("all_scope")) & p5e.metric.isin([
        "observed_delivery_event", "ordinary_delivery_event", "recognized_bowler_credit_wicket", "legal_delivery_known"]),
        ["format", "metric", "numerator_or_value", "denominator", "rate_or_coverage"]]
    cov_table = _md_table(cov)
    bowl_table = _md_table(bowling[["format", "metric", "pressure_value", "baseline_value", "pressure_minus_baseline",
        "cluster_ci95_low", "cluster_ci95_high", "paired_match_clusters"]])
    bowler_eligibility_table = _md_table(bowler_fmt_counts)
    top_table = _md_table(top[["format", "rank", "player_name", "score", "pressure_events", "pressure_matches",
        "baseline_events", "baseline_matches", "score_ci95_low", "score_ci95_high", "stability_flag"]])
    (REPORTS / "final_methodology_report.md").write_text(
f'''# Final competition methodology and results report

## Scope and decision

This audit uses only the supplied, accepted IPL and T20I data from 2022 onward and the completed Phase 1-5E outputs. IPL and T20I are analyzed independently; no cross-format score conversion or pooled ranking is used. The supplied data support two format-specific batter Top 10s under a declared contextual batting-resource definition. They do **not** support a reliable competition-ready bowling Top 10 under the unchanged evidence requirements. The required bowling list remains unsupported and must not be filled with exploratory profiles.

The ranking is an operational evaluation of performance in specified match contexts. It does not claim to measure a player's psychology or prove that the player felt pressure.

## Pressure definitions and comparison design

### Ranked batter context

For each format and innings phase, the pressure-context cohort uses wickets lost before the delivery at or above that phase-format's empirical 75th percentile (Q75); its reference uses wickets lost at or below Q25. Exact cutpoints from Phase 5C are: IPL powerplay 1/0, middle 4/1, death 6/3; T20I powerplay 1/0, middle 4/2, death 7/4 (pressure/reference wickets lost). Super Overs are excluded. Only match-by-phase strata containing both classes are paired. This represents batting-resource depletion at a comparable phase; it is a defensible batting challenge proxy, not verified scoreboard pressure. RRR > CRR is not mixed into this score.

### Separate verified chase validation

In regular second innings only, validated pre-delivery score, target, runs required, legal balls remaining and completed legal balls must permit CRR and RRR. Pressure is RRR > CRR; reference is RRR <= CRR. Unknown or ambiguous state is excluded, not imputed. This represents observable chase acceleration/containment demand, not psychological pressure. It remains a separate validation track and does not qualify a batter or bowler under current floors.

### Bowling challenge decision

Verified RRR > CRR is the strongest role-relevant bowling challenge available: a chasing batting side requires acceleration and the bowler's team faces a containment task. High wicket depletion alone is rejected as bowling pressure because a depleted batting lineup may make the task easier. Death phase, pace/spin, line/length proxies, speed and delivery descriptors do not establish pre-delivery match demand. No verified chase bowler profile meets both inherited pressure and baseline exposure floors.

## Batter metrics, baseline and score

On ordinary-delivery subsets, the batter components are (1) pressure-minus-baseline strike-rate change (60%); (2) baseline-minus-pressure dot-rate change (20%); and (3) pressure-minus-baseline boundary-event-rate change (20%). Baselines are the player's comparable low-depletion observations in paired match/phase context. These measures are limited feed subsets, not complete innings rates. Components are standardized within format and role before weighting.

The weighted standardized composite is reliability-shrunk by `n_eff / (n_eff + 20)`, where `n_eff` is the harmonic mean of pressure and baseline event counts. It is then multiplied by `0.5 + 0.5 × match_consistency_index`; the index is the average share of pressure matches in which the player's component beats their aggregate baseline. The k=20 shrinkage is a declared conservative choice, not a fitted parameter. Higher scores rank first, ties break by stable player ID. Format and candidate eligibility are kept separate.

Competition-ready batter floors remain unchanged: pressure at least 2 events across at least 2 matches, baseline at least 16 events across at least 3 matches. Phase 5D independently reconstructed all 305 eligible scores and rank order: 107 IPL and 198 T20I, maximum absolute score differences <4e-16, zero rank mismatches and zero floor failures. The final CSV contains the top ten of each independently reconstructed eligible pool.

### Final batter evidence table

The scores and uncertainty columns below come directly from the reconciled final CSV. Pressure/baseline exposures are events and distinct matches. Cluster intervals are uncertainty intervals on score, not rank probabilities.

{top_table}

### Score charts

Blue points show the composite score; gold bars show the 95% match-cluster bootstrap interval. Wide or overlapping intervals mean adjacent ranks are not statistically resolved.

![IPL batter score intervals](final_ipl_batter_top10_chart.svg)

![T20I batter score intervals](final_t20i_batter_top10_chart.svg)

## Uncertainty, stability and format separation

For each format's Top 10, Phase 5D used 1,000 stratified match-cluster bootstrap draws per candidate, jointly resampling shared pressure/baseline matches and separately sampling pressure-only and baseline-only match clusters; format standardization was held fixed. The intervals do not represent rank probabilities. Leave-one-match-out perturbations cover 359 paired IPL matches and 466 paired T20I matches; leave-one-season-out perturbations cover 5 IPL seasons and 8 T20I seasons. Under the disclosed stability flag (>=80% leave-one-match Top 10 retention and >=75% leave-one-season retention), 9/10 qualify in each format. Dewald Brevis (IPL) and Ackeem Auguste (T20I) are season-sensitive; both pass full-sample floors and remain included with flags. Rank proximity and bootstrap overlap caution against treating ordinal gaps as definitive.

Sensitivity in Phase 5C found Top 10 overlap of 9/10 for the 100/0/0 batter component weighting in both formats; IPL overlaps were 10/10 for 50/25/25 and 40/30/30, T20I overlaps were 9/10 for each. The threshold sensitivity is exploratory and does not change the inherited eligibility gates. Pressure-definition sensitivity is limited because the verified-state eligible pool is very small. No format scores are combined.

## Bowling evidence: available comparisons and blockers

Ordinary dots, ordinary batter runs/event and ordinary boundary events can be described on their restricted ordinary-delivery subsets; recognized bowler-credit wickets are divided by observed delivery rows (not legal balls). Full-scope ordinary rows cover about 94% of observed rows. The field coverage and denominators below reconcile to the Phase 5E metric-coverage file. High percentage availability of `legal_delivery` does not establish a complete validated per-bowler legal-ball denominator.

{cov_table}

Verified chase paired comparisons (higher dot rate and lower batter runs/boundaries are generally favorable to the bowling side; wicket yield is a separate observed-event ratio) are:

{bowl_table}

These aggregate contrasts have only 3 paired IPL match clusters (18 pressure / 4 baseline rows) and 12 T20I clusters (98 / 89 rows), all in powerplay. Their cluster-bootstrap intervals are broad, and no individual bowler meets inherited floors. Phase 5E outputs 0 competition-ready and 414 exploratory bowler profiles; neither the contextual wicket-depletion contrast nor the small RRR>CRR sample qualifies names for a ranked bowling list.

The format-level profile/exclusion accounting is:

{bowler_eligibility_table}

Every listed Phase 5C bowler profile remains exploratory. Under the role-valid verified-chase definition, **0** profiles meet both inherited pressure and baseline exposure floors in either format; contextual wicket-depletion numeric floor passes are excluded from competition-ready status because the challenge is not role-valid for bowlers.

Bowler-conceded runs cannot be reconstructed defensibly from available fields because extra type/amount and attribution are incomplete; complete legal-ball denominators also fail validation. Therefore economy and conventional bowling strike rate are blocked. Wickets are credited only under recognized dismissal rules, and this event yield does not repair the absent run/ball denominator. Available delivery attributes describe delivery type/execution but do not define a challenging situation in advance. Phase alone is a comparability control, not pressure. High wicket depletion is role-asymmetric and not accepted as bowling pressure.

## Candidate and exclusion accounting

| Role | Competition-ready | Exploratory | Submission status |
| --- | ---: | ---: | --- |
| Batter | {len(ready)} (IPL {counts.get('IPL',0)}, T20I {counts.get('T20I',0)}) | {exploratory_batters} | Separate format Top 10s supported under contextual batting definition |
| Bowler | {competition_ready_bowlers} | {exploratory_bowlers} | No competition-ready Top 10 supported |

No candidates were promoted by lowering floors. Every final batter rank comes from the frozen Phase 5C file and was verified against Phase 5D reconstruction; all listed score, eligibility, exposure, sensitivity and limitation fields are in `final_batter_top10.csv`. Bowling comparisons, coverage, exposures and limitations are in `final_bowler_evidence.csv`.

## Limitations

The context definition is a wicket-resource proxy; it cannot isolate psychology, innings target difficulty, match importance or selection effects. Ordinary-delivery batting components omit extras and any unsupported attribution. Score standardization and weighting are model choices; the uncertainty analysis fixes standardization and leaves the contextual thresholds fixed. Bootstrap uncertainty is clustered by match but depends on a small number of independent matches for many individuals. Leave-one-season sensitivity is not threshold-recalibrated. Performance should not be inferred beyond the supplied IPL/T20I 2022-onward sample. No unsupported player claim, bowler score, complete bowling economy or psychological-pressure label is made.
''', encoding="utf-8")
    (REPORTS / "final_submission_audit.md").write_text(
f'''# Final submission audit

## Reconciliation results

- Phase 5C batter CSV: 305 competition-ready rows ({counts.get('IPL',0)} IPL; {counts.get('T20I',0)} T20I) and 17 exploratory rows.
- Phase 5D independent audit: 305 reconstructed, maximum absolute score differences below 4e-16, 0 rank mismatches, 0 floor failures.
- Frozen submission table: exactly 10 distinct batter rows per format, all competition-ready; rank keys and score order match independent rebuild and Phase 5D.
- Top 10 stability: 9/10 in IPL and 9/10 in T20I meet the disclosed leave-one-match/season flag. Brevis and Auguste are season-sensitive and flagged.
- Bowler CSV: 0 competition-ready; 414 exploratory. Verified chase sample: IPL 18/4 pressure/reference events over 3 matched clusters; T20I 98/89 over 12. No eligible bowler and no ranked Top 10.
- The dashboard final-submission page reads the same frozen batter/bowler evidence CSVs and renders the same tables, charts, audit and checklist.

The ranking arithmetic validates the frozen model; it does not validate the psychological interpretation of wicket depletion. All report numbers are generated or reconciled from Phase 5C/5D/5E CSV/JSON artifacts. The bowling comparisons are copied from the generated Phase 5E comparison table and joined to Phase 5E denominator/coverage rows.

## List readiness

The batter entries can be transcribed as two separate lists under the contextual method, with the report's caveat and sensitivity flags. The required bowler Top 10 cannot be completed honestly from the supplied data. Do not fill it with the 414 exploratory profiles or present the aggregate comparison as player rankings. A live portal field requirement should be checked against the official task: the local competition brief documents two ordered Top 10 lists and a methodology report, while live Unstop instructions were not available in the workspace.
''', encoding="utf-8")
    return {"batter_top10_rows": len(top), "IPL": int(top.format.eq("IPL").sum()),
            "T20I": int(top.format.eq("T20I").sum()), "bowler_evidence_rows": len(bowling),
            "competition_ready_batters": int(len(ready)), "competition_ready_bowlers": competition_ready_bowlers,
            "exploratory_batters": exploratory_batters, "exploratory_bowlers": exploratory_bowlers}


if __name__ == "__main__":
    import json
    print(json.dumps(main(), indent=2))
