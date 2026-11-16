"""Player coverage and scoring feasibility; deliberately does not rank players."""
from __future__ import annotations

from pathlib import Path
import math
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "outputs" / "reports"


def _sum(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def _rate(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def build_player_eligibility(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, dict[str, int]]]:
    """Build batter/bowler exposure tables and role-specific scoring feasibility."""
    pressure = features["match_state_pressure_eligible"].fillna(False).astype(bool)
    proxy = features["wicket_phase_proxy_eligible"].fillna(False).astype(bool)
    ordinary = features["ordinary_delivery"].fillna(False).astype(bool)
    wicket = features["bowler_wicket_event"].fillna(False).astype(bool)

    batters = _aggregate_role(features, "striker_id", "striker_name", pressure, proxy, ordinary, wicket, "batter")
    bowlers = _aggregate_role(features, "bowler_id", "bowler_name", pressure, proxy, ordinary, wicket, "bowler")

    # Batting dismissals are keyed by dismissed batter, independently of striker role.
    dismissed = features[features["batter_dismissal_event"].fillna(False)].copy()
    if not dismissed.empty:
        dismissed_counts = dismissed.groupby("dismissed_player_id").agg(
            batter_dismissals=("batter_dismissal_event", "sum"),
            dismissal_matches=("match_id", "nunique"),
        )
        batters = batters.set_index("player_id")
        for player_id, row in dismissed_counts.iterrows():
            if player_id in batters.index:
                batters.loc[player_id, "batter_dismissals"] = int(row["batter_dismissals"])
                batters.loc[player_id, "dismissal_matches"] = int(row["dismissal_matches"])
            else:
                batters.loc[player_id, "batter_dismissals"] = int(row["batter_dismissals"])
                batters.loc[player_id, "dismissal_matches"] = int(row["dismissal_matches"])
                batters.loc[player_id, "player_name"] = "Unknown name in striker rows"
        batters["batter_dismissals"] = batters["batter_dismissals"].fillna(0).astype(int)
        batters["dismissal_matches"] = batters["dismissal_matches"].fillna(0).astype(int)
        zero_fields = ["matches_observed", "deliveries_observed", "verified_pressure_deliveries", "verified_pressure_matches",
            "wicket_phase_proxy_deliveries", "wicket_phase_proxy_matches", "ordinary_deliveries", "ordinary_run_sum_partial",
            "ordinary_boundary_events", "ordinary_dot_events", "ordinary_run_coverage_pct", "verified_pressure_ordinary_deliveries",
            "pressure_ordinary_run_sum_partial", "batter_dismissals", "dismissal_matches"]
        for field in zero_fields:
            batters[field] = batters[field].fillna(0)
        for field in ["matches_observed", "deliveries_observed", "verified_pressure_deliveries", "verified_pressure_matches",
                      "wicket_phase_proxy_deliveries", "wicket_phase_proxy_matches", "ordinary_deliveries"]:
            batters[field] = batters[field].astype(int)
        batters = batters.reset_index()

    # Role-specific baseline thresholds are empirical first quartiles of observed exposure.
    thresholds: dict[str, dict[str, int]] = {}
    for role, frame in [("batter", batters), ("bowler", bowlers)]:
        exposed = frame.loc[frame["deliveries_observed"].gt(0)]
        pressure_exposed = frame.loc[frame["verified_pressure_deliveries"].gt(0)]
        thresholds[role] = {
            "baseline_deliveries_q1": max(1, math.ceil(exposed["deliveries_observed"].quantile(.25))),
            "baseline_matches_q1": max(1, math.ceil(exposed["matches_observed"].quantile(.25))),
            "pressure_deliveries_q1": max(1, math.ceil(pressure_exposed["verified_pressure_deliveries"].quantile(.25))),
            "pressure_matches_min": 2,
        }
        t = thresholds[role]
        frame["baseline_evidence_eligible"] = frame["deliveries_observed"].ge(t["baseline_deliveries_q1"]) & frame["matches_observed"].ge(t["baseline_matches_q1"])
        frame["verified_pressure_evidence_eligible"] = (
            frame["verified_pressure_matches"].ge(t["pressure_matches_min"])
            & frame["verified_pressure_deliveries"].ge(t["pressure_deliveries_q1"])
        )
        frame["proxy_exploration_eligible"] = frame["baseline_evidence_eligible"] & frame["wicket_phase_proxy_matches"].ge(t["baseline_matches_q1"])
        frame["exclusion_reasons"] = frame.apply(lambda r: _exclusion_reasons(r, t), axis=1)
        frame["baseline_evidence_status"] = frame["baseline_evidence_eligible"].map({True: "eligible for descriptive exposure", False: "below empirical Q1 exposure"})
        frame["verified_pressure_status"] = frame["verified_pressure_evidence_eligible"].map({True: "at least pressure Q1 deliveries across 2+ matches; exploratory only", False: "below pressure Q1 deliveries or fewer than 2 verified-pressure matches"})
        if role == "batter":
            frame["normal_baseline_status"] = frame["normal_baseline_status"].fillna("not identifiable: most rows have unknown pressure state")
            frame["pressure_retention_status"] = frame["pressure_retention_status"].fillna("not calculated; baseline cannot be classified as normal")
            frame["reliable_metrics_available"] = frame["reliable_metrics_available"].fillna("dismissed-player event only; no striker delivery records")
            frame["uncertain_or_missing_metrics"] = frame["uncertain_or_missing_metrics"].fillna("no striker delivery evidence; full scoring metrics unavailable")

    scoring = _scoring_feasibility(features, batters, bowlers)
    batters = batters.sort_values("player_id").reset_index(drop=True)
    bowlers = bowlers.sort_values("player_id").reset_index(drop=True)
    return batters, bowlers, scoring, thresholds


def _aggregate_role(features: pd.DataFrame, id_col: str, name_col: str, pressure: pd.Series, proxy: pd.Series,
                    ordinary: pd.Series, wicket: pd.Series, role: str) -> pd.DataFrame:
    rows = []
    for player_id, all_rows in features.dropna(subset=[id_col]).groupby(id_col, sort=True):
        name = all_rows[name_col].dropna().astype(str).mode()
        name = name.iloc[0] if len(name) else "Unknown"
        p = all_rows.loc[pressure.loc[all_rows.index]]
        prox = all_rows.loc[proxy.loc[all_rows.index]]
        if role == "batter":
            # The batting rates use only ordinary, non-extra rows and are not full innings rates.
            p_ord = p.loc[ordinary.loc[p.index]]
            p_runs = _sum(p_ord["runs"])
            p_balls = len(p_ord)
            p_boundaries = int((p_ord["is_four"].fillna(False) | p_ord["is_six"].fillna(False)).sum())
            p_dots = int(pd.to_numeric(p_ord["runs"], errors="coerce").eq(0).sum())
            pressure_run_rate = _rate(p_runs, p_balls)
            pressure_boundary_rate = _rate(p_boundaries, p_balls)
            pressure_dot_rate = _rate(p_dots, p_balls)
            row = {
                "player_id": int(player_id), "player_name": name,
                "matches_observed": int(all_rows["match_id"].nunique()), "deliveries_observed": len(all_rows),
                "verified_pressure_deliveries": len(p), "verified_pressure_matches": int(p["match_id"].nunique()),
                "wicket_phase_proxy_deliveries": len(prox), "wicket_phase_proxy_matches": int(prox["match_id"].nunique()),
                "ordinary_deliveries": int(ordinary.loc[all_rows.index].sum()),
                "ordinary_run_sum_partial": _sum(all_rows.loc[ordinary.loc[all_rows.index], "runs"]),
                "ordinary_boundary_events": int((all_rows["is_four"].fillna(False) | all_rows["is_six"].fillna(False)).loc[ordinary.loc[all_rows.index]].sum()),
                "ordinary_dot_events": int(pd.to_numeric(all_rows.loc[ordinary.loc[all_rows.index], "runs"], errors="coerce").eq(0).sum()),
                "ordinary_run_coverage_pct": round(100 * ordinary.loc[all_rows.index].mean(), 2),
                "all_observed_ordinary_runs_per_delivery": _rate(_sum(all_rows.loc[ordinary.loc[all_rows.index], "runs"]), int(ordinary.loc[all_rows.index].sum())),
                "verified_pressure_ordinary_deliveries": p_balls,
                "pressure_ordinary_run_sum_partial": p_runs,
                "pressure_ordinary_boundary_rate": pressure_boundary_rate,
                "pressure_ordinary_dot_rate": pressure_dot_rate,
                "pressure_ordinary_runs_per_delivery": pressure_run_rate,
                "normal_baseline_status": "not identifiable: most rows have unknown pressure state",
                "pressure_retention_status": "not calculated; baseline cannot be classified as normal",
                "reliable_metrics_available": "boundary event counts; dismissed-player event count; ordinary-delivery subset runs/balls/boundaries/dots",
                "uncertain_or_missing_metrics": "complete runs/strike rate and balls faced; extras-row batter attribution; full dot rate",
                "batter_dismissals": 0, "dismissal_matches": 0,
            }
        else:
            p_wickets = int(wicket.loc[p.index].sum())
            p_rate = _rate(p_wickets, len(p))
            legal = all_rows["legal_delivery"].notna()
            row = {
                "player_id": int(player_id), "player_name": name,
                "matches_observed": int(all_rows["match_id"].nunique()), "deliveries_observed": len(all_rows),
                "verified_pressure_deliveries": len(p), "verified_pressure_matches": int(p["match_id"].nunique()),
                "wicket_phase_proxy_deliveries": len(prox), "wicket_phase_proxy_matches": int(prox["match_id"].nunique()),
                "bowler_credited_wickets": int(wicket.loc[all_rows.index].sum()),
                "pressure_bowler_credited_wickets": p_wickets,
                "known_legal_delivery_events": int(legal.sum()), "unknown_legal_delivery_events": int((~legal).sum()),
                "legal_event_classification_coverage_pct": round(100 * legal.mean(), 2),
                "pressure_wickets_per_delivery": p_rate,
                "all_observed_wickets_per_delivery": _rate(int(wicket.loc[all_rows.index].sum()), len(all_rows)),
                "normal_baseline_status": "not identifiable: most rows have unknown pressure state",
                "pressure_retention_status": "not calculated; baseline cannot be classified as normal",
                "reliable_metrics_available": "recognized bowler-credited wicket events; wickets per observed delivery (non-standard descriptive rate)",
                "uncertain_or_missing_metrics": "bowler-conceded runs/economy; complete legal-ball totals and conventional bowling strike rate",
            }
        rows.append(row)
    return pd.DataFrame(rows)


def _exclusion_reasons(row: pd.Series, thresholds: dict[str, int]) -> str:
    reasons = []
    if row["deliveries_observed"] < thresholds["baseline_deliveries_q1"]:
        reasons.append(f"deliveries below Q1 ({thresholds['baseline_deliveries_q1']})")
    if row["matches_observed"] < thresholds["baseline_matches_q1"]:
        reasons.append(f"matches below Q1 ({thresholds['baseline_matches_q1']})")
    if not row["verified_pressure_evidence_eligible"]:
        if row["verified_pressure_matches"] < thresholds["pressure_matches_min"]:
            reasons.append("verified pressure observed in fewer than 2 matches")
        if row["verified_pressure_deliveries"] < thresholds["pressure_deliveries_q1"]:
            reasons.append(f"verified-pressure deliveries below pressure Q1 ({thresholds['pressure_deliveries_q1']})")
    return "; ".join(reasons) if reasons else "none for descriptive cohort; not ranking eligible"


def _scoring_feasibility(features: pd.DataFrame, batters: pd.DataFrame, bowlers: pd.DataFrame) -> pd.DataFrame:
    n = len(features)
    p = int(features["match_state_pressure_eligible"].fillna(False).sum())
    ordinary = int(features["ordinary_delivery"].fillna(False).sum())
    b_credit = int(features["bowler_wicket_event"].fillna(False).sum())
    pressure_ordinary = features["match_state_pressure_eligible"].fillna(False) & features["ordinary_delivery"].fillna(False)
    batter_pressure_players = int(features.loc[pressure_ordinary, "striker_id"].nunique())
    batter_specs = [
        ("Batter runs / conventional strike rate", "Not eligible", "sum batter runs / balls faced × 100", "Runs on ordinary rows only; extras rows unresolved; balls faced incomplete.", ordinary),
        ("Ordinary-subset runs per delivery retention", "Candidate formula; blocked", "pressure ordinary runs / pressure ordinary deliveries, divided by a separately validated normal-baseline rate", "Ordinary subset outcome is supported, but unknown pressure labels on most archive rows prevent defining a normal baseline.", ordinary),
        ("Boundary-rate retention (ordinary subset)", "Candidate formula; blocked", "ordinary boundary events / ordinary deliveries in verified pressure vs a validated normal baseline", "Boundary flags validated and denominator can be restricted to ordinary rows; normal-pressure reference group is not identifiable.", ordinary),
        ("Dot-rate retention (ordinary subset)", "Candidate formula; blocked", "ordinary zero-run deliveries / ordinary deliveries in verified pressure vs a validated normal baseline", "Only ordinary events; unknown pressure labels prevent a clean baseline and extras are excluded.", ordinary),
        ("Dismissal count", "Available; one missing player ID", "wicket flag + dismissed_player_id by batter", "10,880/10,881 wicket events identify dismissed player.", int(features["batter_dismissal_event"].sum())),
    ]
    bowler_specs = [
        ("Bowler-conceded runs / economy", "Not eligible", "bowler-conceded runs × 6 / legal balls", "No complete bowler-conceded runs field; extras amounts unresolved.", 0),
        ("Conventional bowling strike rate", "Not eligible", "legal balls / bowler-credited wickets", "Per-bowler event legality incomplete; not a complete denominator.", 0),
        ("Wickets-per-delivery retention", "Candidate formula; blocked", "recognized bowler-credit wickets / observed bowler delivery rows, verified pressure vs validated normal baseline", "Wicket attribution is supported, but unknown pressure states prevent identifying a normal baseline. Not conventional bowling strike rate.", b_credit),
        ("Bowler-credited wicket count", "Available for recognized types", "is_wicket + dismissal_type in credited-type allowlist", "Excludes RunOut, Retire Out and Obstructing-field variants; unknown labels remain excluded.", b_credit),
    ]
    out = []
    for role, specs, table in [("Batter", batter_specs, batters), ("Bowler", bowler_specs, bowlers)]:
        for metric, status, formula, limits, events in specs:
            if metric == "Batter runs / conventional strike rate":
                player_count = 0
            elif metric == "Dismissal count":
                player_count = int(table["batter_dismissals"].gt(0).sum())
            elif metric == "Bowler-credited wicket count":
                player_count = int(table["bowler_credited_wickets"].gt(0).sum())
            elif "retention" in metric.lower():
                player_count = batter_pressure_players if role == "Batter" else int(table["verified_pressure_deliveries"].gt(0).sum())
            else:
                player_count = 0
            out.append({"role": role, "metric": metric, "feasibility": status, "proposed_calculation": formula,
                "players_with_relevant_observations": player_count,
                "source_event_count_or_coverage_basis": events, "limitations": limits,
                "pressure_retention_available": "no: normal baseline unidentifiable" if "retention" in metric.lower() else "not applicable"})
    return pd.DataFrame(out)


def run_player_eligibility() -> dict[str, object]:
    path = PROCESSED / "pressure_research_deliveries.csv.gz"
    if not path.exists():
        raise FileNotFoundError("Run `python -m src.pressure_analysis` before player eligibility")
    features = pd.read_csv(path, low_memory=False)
    batters, bowlers, scoring, thresholds = build_player_eligibility(features)
    REPORTS.mkdir(parents=True, exist_ok=True)
    batters.to_csv(REPORTS / "batter_eligibility.csv", index=False)
    bowlers.to_csv(REPORTS / "bowler_eligibility.csv", index=False)
    scoring.to_csv(REPORTS / "scoring_feasibility.csv", index=False)
    report = _eligibility_report(features, batters, bowlers, scoring, thresholds)
    (REPORTS / "player_eligibility_report.md").write_text(report, encoding="utf-8")
    return {"batter_players": len(batters), "bowler_players": len(bowlers),
            "batter_pressure_repeat_exposure": int(batters["verified_pressure_evidence_eligible"].sum()),
            "bowler_pressure_repeat_exposure": int(bowlers["verified_pressure_evidence_eligible"].sum()),
            "report": str(REPORTS / "player_eligibility_report.md")}


def _eligibility_report(features: pd.DataFrame, batters: pd.DataFrame, bowlers: pd.DataFrame,
                        scoring: pd.DataFrame, thresholds: dict[str, dict[str, int]]) -> str:
    pressure = features[features["match_state_pressure_eligible"].fillna(False)]
    summaries = []
    for role, frame in [("Batter", batters), ("Bowler", bowlers)]:
        pcol = "striker_id" if role == "Batter" else "bowler_id"
        grouped = pressure.groupby(pcol).agg(deliveries=("match_id", "size"), matches=("match_id", "nunique"))
        q = grouped.quantile([.25, .5, .75, .9]).round(2).reset_index().rename(columns={"index": "percentile"})
        q.insert(0, "role", role)
        summaries.append(q)
    quantiles = pd.concat(summaries, ignore_index=True)
    summary = pd.DataFrame([
        {"role": "Batters", "players_observed": len(batters), "baseline_Q1_eligible": int(batters.baseline_evidence_eligible.sum()),
         "repeat_pressure_eligible": int(batters.verified_pressure_evidence_eligible.sum()), "proxy_exploration_eligible": int(batters.proxy_exploration_eligible.sum()),
         "pressure_matches": int(pressure.match_id.nunique())},
        {"role": "Bowlers", "players_observed": len(bowlers), "baseline_Q1_eligible": int(bowlers.baseline_evidence_eligible.sum()),
         "repeat_pressure_eligible": int(bowlers.verified_pressure_evidence_eligible.sum()), "proxy_exploration_eligible": int(bowlers.proxy_exploration_eligible.sum()),
         "pressure_matches": int(pressure.match_id.nunique())},
    ])
    return f"""# Phase 2D — Player Eligibility and Scoring Feasibility

## Decision

The data do **not** support a verified-pressure Top 10 for either role. Only 321 deliveries across 28 matches have verified chase state. Ten batters and five bowlers have pressure exposure in at least two matches, but batting scoring is limited to ordinary-delivery subsets and the pressure samples remain small. A proxy-only Top 10 is also not justified: the proxy covers the archive but its performance outcomes are incomplete and it is not verified match pressure. Proxy-based stratified comparisons may be shown as exploratory research with exposure counts and limitations.

## Empirical eligibility thresholds

Normal-baseline exposure thresholds are the **role-specific first quartiles** of observed delivery counts and match counts across players with at least one delivery, rounded up to whole observations. Verified-pressure eligibility additionally requires the role-specific Q1 of verified-pressure deliveries and observations in at least **two distinct verified-pressure matches**. The pressure-match distribution's 90th percentile is about 2 matches for batters and 1.3 for bowlers, so two-match recurrence is restrictive and data-grounded. These are descriptive research screens, not evidence that a player rate is statistically stable.

| role | baseline deliveries Q1 | baseline matches Q1 | pressure deliveries Q1 | pressure-match minimum | observed participants | baseline eligible | repeat-pressure eligible | proxy exploratory eligible |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Batter | {thresholds['batter']['baseline_deliveries_q1']} | {thresholds['batter']['baseline_matches_q1']} | {thresholds['batter']['pressure_deliveries_q1']} | {thresholds['batter']['pressure_matches_min']} | {len(batters)} | {int(batters.baseline_evidence_eligible.sum())} | {int(batters.verified_pressure_evidence_eligible.sum())} | {int(batters.proxy_exploration_eligible.sum())} |
| Bowler | {thresholds['bowler']['baseline_deliveries_q1']} | {thresholds['bowler']['baseline_matches_q1']} | {thresholds['bowler']['pressure_deliveries_q1']} | {thresholds['bowler']['pressure_matches_min']} | {len(bowlers)} | {int(bowlers.baseline_evidence_eligible.sum())} | {int(bowlers.verified_pressure_evidence_eligible.sum())} | {int(bowlers.proxy_exploration_eligible.sum())} |

The baseline thresholds are derived from the source participant exposure distribution. Pressure-only sample quantiles below show why passing the repeat-match screen still does not make the rates ranking-grade.

{_md_table(quantiles)}

## Player coverage summary

{_md_table(summary)}

The batter and bowler CSVs contain each participant's total matches and delivery rows, verified-pressure rows/matches, wicket-phase proxy rows/matches, role-specific supported event counts, baseline and pressure subset sample counts, available metrics, uncertain metric coverage, empirical eligibility flags, and exclusion reasons. Batting subset rates are explicitly restricted to ordinary deliveries. The overall archive cannot be called a normal-pressure baseline: most rows have unknown state, so retention ratios are not calculated.

The batter table includes the union of striker IDs and dismissed-player IDs; dismissed-player-only rows have zero striker deliveries and are not treated as batting-exposure eligible. Current source coverage yields {int(batters.deliveries_observed.eq(0).sum())} such rows.

## Role-specific performance retention and scoring feasibility

{_md_table(scoring)}

For batters, candidate retention measures are ordinary-delivery runs per event, boundary-event rate and dot-event rate in verified-pressure ordinary deliveries against a validated normal-pressure ordinary-delivery baseline. For bowlers, the candidate is recognized credited wickets per observed delivery against that same bowler's validated normal baseline. These rates are not calculated because most archive deliveries have unknown pressure state, so a clean normal-pressure reference group cannot be identified. Even after that gap is resolved, rates must show both numerator and denominator and remain unranked until sample sufficiency is established. No bowler-conceded-runs retention metric is supported.

## Bias and comparability risks

- **Selection bias:** only 28 matches/321 rows survive verified match-state requirements. Extras ambiguity causes state censoring, and the kept segments may differ by match, phase, team or event type. Players who bat or bowl more in those segments have greater inclusion probability.
- **Small samples:** verified-pressure exposure has a median of {quantiles.loc[(quantiles.role.eq('Batter')) & (quantiles.percentile.eq(.5)), 'deliveries'].iloc[0]} deliveries per exposed batter and {quantiles.loc[(quantiles.role.eq('Bowler')) & (quantiles.percentile.eq(.5)), 'deliveries'].iloc[0]} per exposed bowler; median match exposure is one for both. Rates can move sharply after a single event.
- **Survivorship and role:** pressure cohort participation depends on batting order, innings completion, bowling allocation and match state, not only ability. Comparisons must not imply causal effects.
- **IPL/T20I comparability:** the archive mixes IPL and international T20Is across seasons, opponents, venues, rules/conditions and roles. The verified pressure cohort is not large enough to stratify or adjust these factors reliably. Do not pool raw rates as if contexts were interchangeable.
- **Outcome data limitations:** extra-run allocation and full balls-faced/legal-ball denominators remain incomplete; bowler-conceded runs are unavailable. Economy, conventional strike rates, and full batting strike rates remain blocked.

## Recommendation

Do not create verified-pressure Top 10 lists. Keep the verified cohort for case-level and descriptive research only. A separate proxy-pressure exploration is feasible by displaying phase/wicket strata, but not as a ranked list or retention-vs-normal claim. If proxy strata are compared, use only the explicitly labeled ordinary-delivery batter subsets and bowler credited-wicket-per-delivery rate, print numerator/denominator counts, and stratify IPL/T20I rather than pooling them. Obtain provider-defined extras/bowler-conceded runs and independently verified complete scorecards before moving to player selection.

## Reproduce

```powershell
.\\venv\\Scripts\\python.exe -m src.player_eligibility
.\\venv\\Scripts\\python.exe -m pytest -q
```
"""


def _md_table(frame: pd.DataFrame) -> str:
    columns = [str(c) for c in frame.columns]
    rows = [[str(v).replace("|", "\\|").replace("\n", " ") for v in row] for row in frame.itertuples(index=False, name=None)]
    return "| " + " | ".join(columns) + " |\n| " + " | ".join("---" for _ in columns) + " |\n" + "\n".join("| " + " | ".join(row) + " |" for row in rows)


if __name__ == "__main__":
    import json
    print(json.dumps(run_player_eligibility(), indent=2, default=str))
