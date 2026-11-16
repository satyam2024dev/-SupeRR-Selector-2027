"""Phase 2G metric-level evidence eligibility; no match or player ranking logic."""
from __future__ import annotations

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "pressure_research_deliveries.csv.gz"
REPORTS = ROOT / "outputs" / "reports"


def metric_eligibility(features: pd.DataFrame) -> pd.DataFrame:
    ordinary = features["ordinary_delivery"].fillna(False).astype(bool)
    extras = features["extras_type"].astype("string").str.casefold()
    legal = features["legal_delivery"].fillna(False).astype(bool)
    known_legal = ordinary | (extras.isin(["byes", "legbyes"]) & legal)
    boundaries = features["boundary_event"].fillna(False).astype(bool)
    dots = features["dot_ball_verified_subset"].fillna(False).astype(bool)
    team_wickets = features["is_wicket"].fillna(False).astype(bool)
    bowler_wickets = features["bowler_wicket_event"].fillna(False).astype(bool)
    metrics = [
        ("Batter runs", "eligible_limited_subset", "ball_by_ball.csv: runs, striker_id; ordinary rows only", "Cricsheet runs.batter; 965/965 control deliveries match; Phase 2C ordinary-delivery validation", "Extras-row attribution; complete total-run/extras decomposition", "Use runs summed only on verified ordinary rows; local player ID", "Provider field definition or per-delivery batter_runs field for all extras events."),
        ("Balls faced", "eligible_limited_subset", "ball_by_ball.csv: striker_id; ordinary_delivery", "Ordinary deliveries form a conservative subset; pressure research counted 189,166 rows", "Full faced-ball definition for wides/no-balls/other; Overstep remains inferred", "Count ordinary faced rows only; not conventional total balls faced", "Provider-defined is_ball_faced flag or documented event categories/overrides."),
        ("Strike rate", "eligible_limited_subset", "ordinary-subset batter runs and ordinary faced deliveries", "Both numerator and denominator are defined on the same ordinary subset", "Not conventional full strike rate; excludes extras events and has selection bias", "100 × ordinary-subset batter runs / ordinary-subset faced deliveries", "Complete batter runs and balls-faced event indicator for every delivery."),
        ("Boundaries", "eligible_full_event_count", "ball_by_ball.csv: striker_id, is_four, is_six", "All flags non-null; 0 four flags disagree with runs=4, 0 six flags disagree with runs=6, none overlap", "Counts only; boundary percentage needs complete batter runs; names are labels, aggregate by local ID", "Count is_four/is_six per striker_id", "No extra field for event counts; provider docs useful for cross-competition definition consistency."),
        ("Dot balls", "eligible_limited_subset", "ordinary rows: runs, striker_id", "Phase 2C verified 68,028 ordinary zero-run events", "Not full dot-ball count; excludes wides/no-balls/byes/leg-byes/other events", "Count ordinary rows with runs=0; denominator is ordinary faced rows", "Complete total runs and is_ball_faced classification to define dots across all event types."),
        ("Team wickets lost", "eligible_match_innings_level", "ball_by_ball.csv: is_wicket, match_id, innings", "is_wicket matches dismissal labels (10,881); public innings sample 14/14 agrees; retired hurt separately excluded where explicitly represented", "Team/innings metric, not player metric; wicket event is not bowler credit; Super Overs separate", "Sum is_wicket by match and innings, retaining retired-hurt review rule", "Independent scorecards across more seasons/formats; explicit retirement event type for all feeds."),
        ("Bowler-conceded runs", "blocked", "No complete local total-runs or bowler-conceded field", "Phase 2F.5 validates aggregate bowling-conceded sums only in 8 innings from 2 detailed controls", "Cannot reconcile per-delivery extras or assign verified player totals; match acceptance remains unresolved", "Do not calculate from local source", "Per-delivery bowler_conceded_runs, or documented total/typed extras plus independent bowling figures and authoritative player ID crosswalk."),
        ("Legal balls bowled", "eligible_limited_subset", "ordinary events plus byes/legbyes whose legal flag is true", "Ordinary/bye/leg-bye legality follows documented source review and cricket law; limited known subset excludes inferred Overstep and unknown Other/Penalty", "Not full legal-ball total; 266 rows have unknown legal status and Overstep is inferred; never label this conventional overs bowled", "Count only explicitly included known-legal events per bowler", "Provider-defined per-delivery is_legal_delivery for every event, including Overstep, Other and Penalty."),
        ("Bowler-credit wickets", "eligible_recognized_dismissals", "ball_by_ball.csv: is_wicket, dismissal_type, bowler_id", "Phase 2C recognized allowlist yields 10,272 events; 25 stumped wides remain creditable; no recognized credited type occurs on Overstep in the source", "Only recognized dismissal types; no-ball exceptions depend on documented event semantics; not independently player-crosswalked to Cricsheet", "Count Bowled/Caught/LBW/Stump/Hit Wicket by local bowler_id; keep team wickets separate", "Documented dismissal taxonomy and no-ball flag; independent complete bowling scorecards with authoritative player IDs."),
        ("Economy rate", "blocked", "Requires bowler-conceded runs and complete legal balls", "Neither complete input is available from official source; limited external checks do not supply full player joins", "Do not use event runs or extras codes as conceded runs; no partial denominator ratio", "Do not calculate", "Complete per-delivery conceded runs and legal-delivery flag, independently reconciled."),
        ("Bowling strike rate", "blocked", "Requires complete legal balls and bowler-credit wickets", "Recognized wicket counts are available, but the full legal-ball denominator is not", "A subset legal-ball count divided by all wickets is not conventional bowling strike rate", "Do not calculate", "Complete legal-ball status per delivery and validated wicket-credit rules/scorecards."),
    ]
    rows = []
    n = len(features)
    event_counts = {
        "Batter runs": int(ordinary.sum()), "Balls faced": int(ordinary.sum()), "Strike rate": int(ordinary.sum()),
        "Boundaries": int(boundaries.sum()), "Dot balls": int(dots.sum()), "Team wickets lost": int(team_wickets.sum()),
        "Bowler-conceded runs": 0, "Legal balls bowled": int(known_legal.sum()),
        "Bowler-credit wickets": int(bowler_wickets.sum()), "Economy rate": 0, "Bowling strike rate": 0,
    }
    for name, status, source, evidence, missing, formula, next_data in metrics:
        mask = {
            "Batter runs": ordinary, "Balls faced": ordinary, "Strike rate": ordinary,
            "Boundaries": pd.Series(True, index=features.index), "Dot balls": ordinary,
            "Team wickets lost": team_wickets, "Bowler-conceded runs": pd.Series(False, index=features.index),
            "Legal balls bowled": known_legal, "Bowler-credit wickets": bowler_wickets,
            "Economy rate": pd.Series(False, index=features.index), "Bowling strike rate": pd.Series(False, index=features.index),
        }[name]
        subset = features.loc[mask]
        rows.append({"metric": name, "eligibility_status": status, "source_fields": source,
            "validation_evidence": evidence, "source_rows_covered": int(mask.sum()),
            "metric_event_count": event_counts[name],
            "source_rows_total": n, "source_row_coverage_pct": round(100 * mask.mean(), 3) if n else 0,
            "matches_covered": int(subset.match_id.nunique()),
            "innings_covered": int(subset[["match_id", "innings"]].drop_duplicates().shape[0]),
            "players_with_metric_observations": int(subset.striker_id.nunique()) if name in {"Batter runs", "Balls faced", "Strike rate", "Boundaries", "Dot balls"} else int(subset.bowler_id.nunique()) if name in {"Legal balls bowled", "Bowler-credit wickets"} else 0,
            "player_level_comparison": "eligible for stated subset/count" if status.startswith("eligible_") and name != "Team wickets lost" else "match/innings only; not player-level" if name == "Team wickets lost" else "not eligible",
            "calculation_or_scope": formula, "missing_fields_or_limitations": missing,
            "smallest_additional_data_requirement": next_data})
    return pd.DataFrame(rows)


def build_player_coverage(features: pd.DataFrame) -> pd.DataFrame:
    """Long-form coverage/value table for evidence-eligible player metrics only."""
    rows: list[dict] = []
    ordinary = features["ordinary_delivery"].fillna(False).astype(bool)
    for player_id, frame in features.dropna(subset=["striker_id"]).groupby("striker_id", sort=True):
        name = frame["striker_name"].dropna().astype(str).mode()
        player_name = name.iloc[0] if len(name) else "Unknown"
        ord_rows = frame.loc[ordinary.loc[frame.index]]
        runs = float(pd.to_numeric(ord_rows["batter_runs_verified_subset"], errors="coerce").fillna(0).sum())
        balls = int(pd.to_numeric(ord_rows["balls_faced_verified_subset"], errors="coerce").fillna(0).sum())
        fours = int(frame["four_event"].fillna(False).sum())
        sixes = int(frame["six_event"].fillna(False).sum())
        dots = int(ord_rows["dot_ball_verified_subset"].fillna(False).sum())
        for metric, value, sample, matches, innings, scope in [
            ("Batter runs (ordinary subset)", runs, balls, ord_rows.match_id.nunique(), ord_rows[["match_id", "innings"]].drop_duplicates().shape[0], "ordinary deliveries only"),
            ("Balls faced (ordinary subset)", balls, balls, ord_rows.match_id.nunique(), ord_rows[["match_id", "innings"]].drop_duplicates().shape[0], "ordinary deliveries only"),
            ("Strike rate (ordinary subset)", 100 * runs / balls if balls else None, balls, ord_rows.match_id.nunique(), ord_rows[["match_id", "innings"]].drop_duplicates().shape[0], "ordinary runs / ordinary faced balls × 100"),
            ("Boundaries (full event count)", fours + sixes, len(frame), frame.match_id.nunique(), frame[["match_id", "innings"]].drop_duplicates().shape[0], "verified is_four + is_six event count"),
            ("Dot balls (ordinary subset)", dots, balls, ord_rows.match_id.nunique(), ord_rows[["match_id", "innings"]].drop_duplicates().shape[0], "ordinary rows with runs=0"),
        ]:
            if metric != "Boundaries (full event count)" and not balls:
                continue
            rows.append({"player_id": int(player_id), "player_name": player_name, "role": "batter", "metric": metric,
                "eligibility_status": "eligible_full_event_count" if metric == "Boundaries (full event count)" else "eligible_limited_subset",
                "metric_value": value, "metric_sample_events": int(sample), "matches_with_metric_evidence": int(matches),
                "innings_with_metric_evidence": int(innings), "source_delivery_rows_observed": len(frame), "scope": scope,
                "fours_count": fours if metric == "Boundaries (full event count)" else "",
                "sixes_count": sixes if metric == "Boundaries (full event count)" else ""})
    # Conservative legal-ball sub-cohort; do not include inferred Overstep or unknown Other/Penalty.
    labels = features["extras_type"].astype("string").str.casefold()
    ordinary_all = features["ordinary_delivery"].fillna(False).astype(bool)
    known_legal = ordinary_all | (labels.isin(["byes", "legbyes"]) & features["legal_delivery"].fillna(False).astype(bool))
    credit = features["bowler_wicket_event"].fillna(False).astype(bool)
    for player_id, frame in features.dropna(subset=["bowler_id"]).groupby("bowler_id", sort=True):
        name = frame["bowler_name"].dropna().astype(str).mode()
        player_name = name.iloc[0] if len(name) else "Unknown"
        legal_frame = frame.loc[known_legal.loc[frame.index]]
        wicket_count = int(credit.loc[frame.index].sum())
        for metric, value, sample, evidence, scope in [
            ("Legal balls bowled (known-category subset)", int(len(legal_frame)), int(len(legal_frame)), legal_frame, "ordinary/byes/legbyes only; incomplete total"),
            ("Bowler-credit wickets (recognized types)", wicket_count, int(credit.loc[frame.index].sum()), frame.loc[credit.loc[frame.index]], "recognized dismissal allowlist; team wickets separate"),
        ]:
            rows.append({"player_id": int(player_id), "player_name": player_name, "role": "bowler", "metric": metric,
                "eligibility_status": "eligible_limited_subset" if metric.startswith("Legal balls") else "eligible_recognized_dismissals",
                "metric_value": value, "metric_sample_events": sample, "matches_with_metric_evidence": int(evidence.match_id.nunique()),
                "innings_with_metric_evidence": int(evidence[["match_id", "innings"]].drop_duplicates().shape[0]),
                "source_delivery_rows_observed": len(frame), "scope": scope, "fours_count": "", "sixes_count": ""})
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["role", "metric", "player_id"], kind="stable").reset_index(drop=True)


def _make_report(matrix: pd.DataFrame, coverage: pd.DataFrame) -> str:
    def table(frame: pd.DataFrame, cols: list[str]) -> str:
        view = frame[cols].copy()
        for c in view:
            view[c] = view[c].astype(str).str.replace("|", "\\|", regex=False).str.replace("\n", " ", regex=False)
        return "| " + " | ".join(cols) + " |\n|" + "|".join(["---"] * len(cols)) + "|\n" + "\n".join("| " + " | ".join(row) + " |" for row in view.values)
    counts = coverage.groupby(["role", "metric"]).agg(players=("player_id", "nunique"), observations=("metric_sample_events", "sum")).reset_index()
    eligible_players = int(coverage["player_id"].nunique()) if not coverage.empty else 0
    return f'''# Phase 2G — Metric-level evidence eligibility audit

## Decision and separation from match acceptance

This audit applies metric-specific evidence rules without changing the Phase 2E full-match gate. Phase 2F still has **0 accepted matches**; no unresolved fixture is relabeled accepted here. The four Cricsheet controls validate selected fields, while Cricsheet values and independent scorecards are not merged into the official player dataset. Metric-level eligibility means only that the stated source value/scope can support the listed use.

The official source has 200,999 ball-by-ball rows. Ordinary batter analyses below use the Phase 2C conservative subset (**189,166 rows**). Batter IDs and bowler IDs are grouped by the official local numeric IDs; display names are labels only. Candidate/ambiguous external crosswalks are never used.

## Metric eligibility matrix

{table(matrix, ['metric','eligibility_status','source_rows_covered','metric_event_count','source_rows_total','source_row_coverage_pct','matches_covered','innings_covered','players_with_metric_observations','player_level_comparison','calculation_or_scope','validation_evidence','missing_fields_or_limitations','smallest_additional_data_requirement'])}

## Player coverage for eligible scopes only

Rows are emitted only for metrics with `eligible_` status in the matrix. Subset metrics are named as subsets and must not be presented as conventional full-match rates. The file is long-form: one row per local player ID and eligible metric, with value, event sample size, match/innings exposure, and scope. It contains no rankings.

{table(counts, ['role','metric','players','observations'])}

Across these eligible metric scopes, **{eligible_players} unique local player IDs** have at least one listed evidence row. This is exposure coverage, not ranking eligibility. The ordinary subset has 887 strikers; full boundary counts include 888 observed strikers (36,094 boundary events; 741 have at least one boundary). Recognized bowler-credit wickets total 10,272 events across 556 bowlers; zero-event bowlers are retained with zero values in the coverage file. Team wickets lost is not a player-level metric and is summarized only by match/innings source evidence.

## What independent scorecards add

Phase 2F.5 checked event-derived totals/overs/wickets against scorecard sources in 12 innings and typed extras against detailed scorecards in 8 innings. Bowler-conceded sums were independently corroborated at aggregate innings level in 8 innings across 2 controls. This supports those **match/innings aggregates** for validation; it does not establish a complete player-level join. The full match acceptance gate remains unresolved, and no scorecard player values are imported. Exact player-level scorecard metrics would require authoritative player IDs and a row-level crosswalk.

## Blocked standard metrics and minimum additions

- **Conventional batter runs, balls faced and strike rate:** the eligible local output is restricted to ordinary deliveries. Need documented per-delivery batter-run attribution and `is_ball_faced` (or equivalent typed event semantics) for every delivery.
- **Full dot-ball rate:** requires total team runs and faced-ball semantics on extras events; only ordinary zero-run events are eligible now.
- **Boundary percentage:** event counts are reliable; the denominator (complete batter runs) is not. Do not calculate the percentage.
- **Full legal balls bowled:** 200,733 rows have a current classified legal flag, but 576 Overstep rows depend on inference and 266 Other/Penalty rows remain unknown. The player table reports only ordinary/byes/legbyes known-legal events (not total overs). A provider-defined legal-delivery flag resolves this.
- **Bowler-conceded runs and economy:** require per-delivery bowler-conceded runs or complete typed extras and independent bowling figures. No scorecard-derived per-player values are imported.
- **Conventional bowling strike rate:** requires complete legal balls plus verified bowler-credit wickets. Recognized dismissal counts are available, but they cannot repair the incomplete legal-ball denominator.
- **Team wickets lost:** usable as a match/innings count from `is_wicket` with retired-hurt handled separately; it does not describe individual player performance.

## Provenance and reproducibility

Official local evidence comes from the canonical `data/raw/ball_by_ball.csv` and `matches.csv`; feature masks are from `data/processed/pressure_research_deliveries.csv.gz`. External controls are the four Cricsheet JSON files under `data/external/cricsheet/pilot/matches/`, licensed ODC-BY 1.0; URLs, hashes and attribution remain recorded in Phase 2F status reports. The source data and Phase 2E acceptance criteria were not altered.

```powershell
.\\venv\\Scripts\\python.exe -m src.metric_evidence
.\\venv\\Scripts\\python.exe -m pytest -q tests
```
'''


def run() -> dict[str, int]:
    if not PROCESSED.is_file():
        raise FileNotFoundError("Run `python -m src.pressure_analysis` before Phase 2G")
    features = pd.read_csv(PROCESSED, low_memory=False)
    matrix = metric_eligibility(features)
    coverage = build_player_coverage(features)
    REPORTS.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(REPORTS / "metric_evidence_eligibility.csv", index=False)
    coverage.to_csv(REPORTS / "player_metric_coverage.csv", index=False)
    (REPORTS / "metric_evidence_eligibility.md").write_text(_make_report(matrix, coverage), encoding="utf-8")
    return {"source_deliveries": len(features), "eligible_metric_types": int(matrix.eligibility_status.str.startswith("eligible_").sum()),
            "player_metric_rows": len(coverage), "unique_players": int(coverage.player_id.nunique()) if len(coverage) else 0}


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
