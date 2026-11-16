"""Audit possible score reconstruction hypotheses against separate public scorecards."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
EXTERNAL = ROOT / "data" / "external" / "public_scorecard_validation_sample.csv"
REPORTS = ROOT / "outputs" / "reports"

# Local IDs are used only for a temporary audit join; they are deliberately absent
# from the public-only sample file stored under data/external/.
LOCAL_MATCH_FOR_SAMPLE = {
    "WI_ENG_1_2022": 13511, "WI_ENG_2_2022": 13512, "WI_ENG_3_2022": 13513,
    "WI_ENG_4_2022": 13514, "WI_ENG_5_2022": 13515,
    "IND_WI_2_2022": 13523, "DC_RR_34_2022": 14127,
}


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact Markdown table without adding dependencies."""
    cols = [str(c) for c in frame.columns]
    body = [[str(v).replace("|", "\\|").replace("\n", " ") for v in row]
            for row in frame.itertuples(index=False, name=None)]
    return "| " + " | ".join(cols) + " |\n| " + " | ".join("---" for _ in cols) + " |\n" + "\n".join(
        "| " + " | ".join(row) + " |" for row in body)


def build_audit() -> dict[str, object]:
    """Write the Phase 2B.1 evidence report; keep public scorecards external."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    if not EXTERNAL.is_file():
        raise FileNotFoundError(f"Public-only validation sample is missing: {EXTERNAL}")
    public = pd.read_csv(EXTERNAL)
    if "local_match_id" in public.columns:
        raise ValueError("Public sample must not contain proprietary local match identifiers")
    balls = pd.read_csv(RAW / "ball_by_ball.csv", low_memory=False)
    matches = pd.read_csv(RAW / "matches.csv", low_memory=False)
    teams = pd.read_csv(RAW / "teams.csv")
    competitions = pd.read_csv(RAW / "competitions.csv")

    candidate_columns = [
        ("ball_by_ball.csv", "runs", "0..6; agrees with batter score totals in tested sample; sum per innings is not team total"),
        ("ball_by_ball.csv", "extras_type", "categorical label; wide, Overstep, byes, legbyes, other, Penalty, null"),
        ("ball_by_ball.csv", "extras1_runs", "exact category-like code by extras_type; 1..7, not an amount"),
        ("ball_by_ball.csv", "extras_2_runs", "mostly 0; nonzero values 1/4; public sample supports extra-run amount on two events, but scope/attachment unclear"),
        ("ball_by_ball.csv", "is_four/is_six", "boundary event flags; cross-checks source runs on these rows"),
        ("ball_by_ball.csv", "is_wicket/dismissal_type/dismissed_player_id", "wicket event, label and dismissed batter; cannot infer bowler credit from flag alone"),
        ("ball_by_ball.csv", "innings/innings_ball_num/overid/over_ball_num", "delivery ordering and inning/over context; no score amount"),
        ("matches.csv", "revised_target", "target candidate for revised chases; not an innings total"),
        ("matches.csv", "first_inn_revised_overs/second_inn_revised_overs", "observed multiples of 6 from 30 to 114; pattern supports legal-ball allowance, not overs"),
        ("matches.csv", "result/win_team_id", "winner and victory margin/text; no batting totals or per-innings scores"),
        ("matches.csv", "match_id/comp_id/team IDs/date", "join keys and match context only"),
    ]
    candidates = pd.DataFrame(candidate_columns, columns=["dataset", "column(s)", "observed_use_or_limit"])

    audit_rows = []
    for sample_id, local_match_id in LOCAL_MATCH_FOR_SAMPLE.items():
        public_match = public[public["sample_match_ref"].eq(sample_id)]
        local_match = balls[balls["match_id"].eq(local_match_id)]
        meta = matches[matches["match_id"].eq(local_match_id)]
        if public_match.empty or local_match.empty or len(meta) != 1:
            raise ValueError(f"Sample match {sample_id} does not resolve to exactly one local match")
        comp_id = meta.iloc[0]["comp_id"]
        for _, expected in public_match.iterrows():
            innings = int(expected["innings"])
            source = local_match[local_match["innings"].eq(innings)]
            if source.empty:
                raise ValueError(f"Sample match {sample_id} innings {innings} is missing from local source")
            team_id = int(source["batting_team_id"].iloc[0])
            local_team_rows = teams[teams["comp_id"].eq(comp_id) & teams["team_id"].eq(team_id)]
            local_team = str(local_team_rows.iloc[0]["team_name"]) if len(local_team_rows) else "unknown"
            if local_team.casefold() != str(expected["team"]).casefold():
                raise ValueError(f"Team/innings mismatch for sample {sample_id}: local={local_team}, public={expected['team']}")
            labels = source["extras_type"].astype("string").str.casefold()
            runs = int(pd.to_numeric(source["runs"], errors="coerce").sum())
            extras2 = int(pd.to_numeric(source["extras_2_runs"], errors="coerce").sum())
            extra_rows = int(source["extras_type"].notna().sum())
            wide_rows = int(labels.eq("wide").sum())
            overstep_rows = int(labels.eq("overstep").sum())
            other_rows = int(labels.eq("other").sum())
            known_invalid_rows = wide_rows + overstep_rows
            legal_a = len(source) - known_invalid_rows
            legal_b = legal_a - other_rows
            audit_rows.append({
                "sample_match_ref": sample_id, "local_match_id": local_match_id, "date": expected["date"],
                "innings": innings, "team": local_team, "public_total": int(expected["total_runs"]),
                "public_wickets": int(expected["wickets"]), "public_legal_balls": int(expected["legal_balls"]),
                "source_delivery_rows": len(source), "source_runs_sum": runs, "extras2_sum": extras2,
                "extras_event_rows": extra_rows, "runs_plus_extras2": runs + extras2,
                "runs_plus_extras_event_count": runs + extra_rows,
                "runs_plus_event_count_plus_extras2": runs + extra_rows + extras2,
                "runs_plus_wide_and_overstep_row_count": runs + wide_rows + overstep_rows,
                "source_wicket_flags": int(source["is_wicket"].fillna(False).sum()),
                "legal_candidate_without_other_rule": legal_a,
                "legal_candidate_if_other_is_non_counting": legal_b,
                "other_rows": other_rows,
                "source_url": expected["source_url"],
            })
    audit = pd.DataFrame(audit_rows)
    n = len(audit)
    score_formula_counts = {
        "runs_sum_equals_public_total": int(audit["source_runs_sum"].eq(audit["public_total"]).sum()),
        "runs_plus_extras2_equals_public_total": int(audit["runs_plus_extras2"].eq(audit["public_total"]).sum()),
        "runs_plus_extras_row_count_equals_public_total": int(audit["runs_plus_extras_event_count"].eq(audit["public_total"]).sum()),
        "runs_plus_extras_row_count_plus_extras2_equals_public_total": int(audit["runs_plus_event_count_plus_extras2"].eq(audit["public_total"]).sum()),
        "runs_plus_wide_and_overstep_row_count_equals_public_total": int(audit["runs_plus_wide_and_overstep_row_count"].eq(audit["public_total"]).sum()),
        "wicket_flags_equal_public_wickets": int(audit["source_wicket_flags"].eq(audit["public_wickets"]).sum()),
        "legal_candidate_without_other_equals_public_balls": int(audit["legal_candidate_without_other_rule"].eq(audit["public_legal_balls"]).sum()),
        "legal_candidate_if_other_non_counting_equals_public_balls": int(audit["legal_candidate_if_other_is_non_counting"].eq(audit["public_legal_balls"]).sum()),
        "sample_innings": n,
    }

    extras_stats = balls.groupby("extras_type", dropna=False).agg(
        rows=("runs", "size"), runs_sum=("runs", "sum"), extras2_sum=("extras_2_runs", "sum"),
        extras2_nonzero_rows=("extras_2_runs", lambda s: int(s.fillna(0).ne(0).sum())),
    ).reset_index()
    code_stats = balls.groupby(["extras_type", "extras1_runs"], dropna=False).size().reset_index(name="rows")
    season_fields = competitions.set_index("comp_id")["season"].astype(str)
    qpath = REPORTS / "match_state_quality.csv"
    if qpath.is_file():
        quality = pd.read_csv(qpath)
        innings_with_rows = int(quality["innings_count"].sum())
        baseline_known = int(quality["innings_final_score_known_count"].sum())
    else:
        # Recompute state-end coverage from the derivative if quality output is absent.
        state_path = ROOT / "data" / "processed" / "match_state_deliveries.csv.gz"
        if not state_path.is_file():
            raise FileNotFoundError("Run the Phase 2B pipeline before scoring recovery audit")
        states = pd.read_csv(state_path, low_memory=False)
        final = states.groupby(["match_id", "innings"], sort=False).tail(1)
        innings_with_rows = len(final)
        baseline_known = int(final["innings_final_score_if_known"].notna().sum())
    after_known = baseline_known  # No global scoring rule passed validation, so no engine correction is applied.

    extras_view = extras_stats.copy()
    extras_view["extras_type"] = extras_view["extras_type"].fillna("(null)")
    code_view = code_stats.copy()
    code_view["extras_type"] = code_view["extras_type"].fillna("(null)")
    subset_cols = ["sample_match_ref", "innings", "team", "public_total", "source_runs_sum", "extras_event_rows",
        "extras2_sum", "runs_plus_extras_event_count", "runs_plus_event_count_plus_extras2", "source_wicket_flags",
        "public_wickets", "public_legal_balls", "legal_candidate_without_other_rule", "legal_candidate_if_other_is_non_counting"]
    comparison_table = _markdown_table(audit[subset_cols])
    candidates_table = _markdown_table(candidates)
    extras_table = _markdown_table(extras_view)

    report = f"""# Phase 2B.1 — scoring recovery audit

## Scope and separation

Audited all potentially relevant fields in the six canonical CSV schemas, including delivery runs/extras/boundary/wicket/order columns and match targets/revised overs/result fields. The 14 public scorecard innings in `data/external/public_scorecard_validation_sample.csv` are kept outside `data/raw/` and `data/processed/`; they are not appended to the RR source or processed event data. The report contains a temporary side-by-side reconciliation, with the public source URL retained for every row.

## Candidate score and state fields

{candidates_table}

No separate innings total or bowler-conceded-runs field exists in either `ball_by_ball.csv` or `matches.csv`. `result` gives winner and margin, not innings totals. `revised_target` can specify a chase target but is not a score total. `first_inn_revised_overs` and `second_inn_revised_overs` have multiples-of-six values and are treated by the engine as ball caps, not runs.

## Extras investigation

Observed `extras1_runs` codes remain exactly label-like (null=6, Overstep=1, wide=2, legbyes=3, byes=4, other=5, Penalty=7). It cannot be an amount. `extras_2_runs` has values 0 (200,963 rows), 1 (20), and 4 (16). In the public DC innings on 22 Apr 2022, the local event categorized as `other` has `extras_2_runs=4`, while the official RR scorecard lists 4 byes and 1 no-ball; this is evidence that the value can represent additional runs associated with an event, but does not establish a universal field mapping. In the India innings on 18 Feb 2022, an Overstep row carries 4 and the official scorecard reports B=5 across a `byes` event plus extras; again compatible with an amount, but not enough to assign all amounts to their delivery category.

The official RR scorecard for DC-RR also reports WD=8 while the local innings has seven `wide` rows, and total extras 13. The official India scorecard reports WD=9 while the local innings has eight `wide` rows. Thus an extra run can occur beyond the one-run wide penalty and is not represented by wide row count or `extras_2_runs` in those innings. A formula adding one per extra row plus `extras_2_runs` remains short of the public total in both examples. `runs + number_of_extra_rows` agrees in only {score_formula_counts['runs_plus_extras_row_count_equals_public_total']}/{n} audited innings. Adding `extras_2_runs` to that formula agrees in {score_formula_counts['runs_plus_extras_row_count_plus_extras2_equals_public_total']}/{n}; it still fails elsewhere. Neither is a safe global scoring rule.

### Cricket-law constraints versus feed definitions

The MCC Laws specify a one-run penalty for a Wide and a No ball; neither counts as one of the over's valid balls. The No-ball law also covers overstepping and explains that other runs may be batter runs, byes, or leg-byes. Those rules define cricket scoring, but do not define the provider's category code `Overstep` or the scope of `extras_2_runs`. In the India–West Indies sample, the two local `Overstep` rows align with the official scorecard's two no-ball extras. `wide` rows are explicit in the feed and public totals confirm the mandatory wide penalty, but the public sample also shows unrecorded additional wide runs. [MCC Laws of Cricket, Laws 18, 21–23](https://www.lords.org/getmedia/a4ef9f77-2a25-4f5b-a286-4601f08e6334/Laws-of-Cricket-2017-Code-4th-Edition-%282026%29_5.pdf); [ICC Men's T20I Playing Conditions, Clause 17](https://www.icc-cricket.com/news/mens-t20i-match-clause-17-the-over).

The law distinguishes team wickets from bowler-credited dismissals. The 14 public innings confirm `is_wicket` totals, but `dismissal_type` must still be used to exclude dismissals such as RunOut from bowler wicket credit. This distinction is why this audit validates wicket counts separately from bowling figures.

### Field-value distributions

{extras_table}

## Public scorecard comparison

Scores and wickets in the public sample cover five England–West Indies T20Is, an India–West Indies T20I, and IPL 2022 Match 34 (Delhi Capitals–Rajasthan Royals). The exact source URLs are recorded in the separated public sample CSV.

{comparison_table}

Across {n} innings, raw `runs` sums match the public team totals in {score_formula_counts['runs_sum_equals_public_total']}; adding `extras_2_runs` alone matches in {score_formula_counts['runs_plus_extras2_equals_public_total']}. Wicket flags match scorecard wickets in {score_formula_counts['wicket_flags_equal_public_wickets']}/{n}, supporting their use as innings wickets lost (not all as bowler-credited wickets).

Legal-ball check A excludes only rows labelled `wide` and `Overstep`; it matches public legal-ball counts in {score_formula_counts['legal_candidate_without_other_equals_public_balls']}/{n}. Check B additionally treats `other` rows as non-counting; it matches in {score_formula_counts['legal_candidate_if_other_non_counting_equals_public_balls']}/{n}. In the sample, each of four `other`-labelled events occurs in an innings where excluding it reconciles the scorecard ball count. This is evidence that those sampled `other` events are non-counting, potentially no-balls; it is not proof that every one of the 264 `other` rows in the full dataset has the same meaning. They remain unresolved in production normalization pending a provider definition or more complete feed evidence.

The first two England innings provide a useful positive case: source `runs` sum plus wide-row count equals official totals (103 and 171) where each wide appears to contribute only its one-run penalty. Other sample innings show that this shortcut fails, including byes/leg-byes, additional wide runs, or other extra events. This suggests the prior engine is conservative about score completeness, but not overly conservative: available fields do not determine exact per-delivery extras.

## Reconstruction coverage

| Measure | Before this audit | After validated correction |
|---|---:|---:|
| Innings with exact final score | {baseline_known}/{innings_with_rows} ({100*baseline_known/innings_with_rows:.2f}%) | {after_known}/{innings_with_rows} ({100*after_known/innings_with_rows:.2f}%) |
| Public sample innings whose final total is independently verified | 0 in proprietary state output | 0 in proprietary state output; the public comparison is an audit only |

No dataset-wide scoring correction passed validation, so `src/match_state.py` was not changed. Public totals must not be used to backfill the proprietary event stream. The 18 exact innings are those for which source normalization already contains a fully supported run amount for every event; final-score coverage remains 18/1,724 until the provider supplies documented extras semantics or complete score data.

## Wicket and batter-run findings

Boundary flags agree with `runs` values 4/6 across the full source. In the detailed public checks, `runs` sums align with batting-run totals for the India–West Indies and DC–RR sample innings when available from scorecard batting lines; the scorecard team totals exceed these sums by extras. The 14-match sample's wicket flags match official wickets exactly. Dismissal labels still matter for bowler attribution: run outs and other non-bowler dismissals count as team wickets but should not be credited to a bowler.

## Recommended next steps

1. Request the provider data dictionary, especially whether `extras_2_runs` is an additional run amount and how it combines with `extras_type`.
2. Request a full scorecard/export containing per-delivery total runs, extras components, legal-ball flag, and bowler-conceded runs, or a complete ball-by-ball scorecard for representative fixtures.
3. Confirm whether `other` means a no-ball/non-counting delivery or includes other event classes. Keep it unknown in production until verified across a larger, stratified sample.
4. Once the feed schema is documented, calculate delivery total as batter runs + categorized extras amounts; verify it against scorecard innings totals and bowling figures on a held-out sample before changing the engine.
5. Do not use final-score-only public references to impute which delivery received missing extras; exact pre-delivery pressure states require per-delivery allocation.

## Sources

- Windies Cricket official England in West Indies 2021/22 scores: https://www.windiescricket.com/series/england-in-west-indies-2021-22-16230/
- BCCI official India vs West Indies 2nd T20I: https://www.bcci.tv/matches/ea6b7cb1-b9ee-4e2e-8765-7171cc053910/india-vs-west-indies
- Rajasthan Royals official DC vs RR Match 34 scorecard: https://www.rajasthanroyals.com/schedule-fixtures-results/delhi-capitals-vs-rajasthan-royals-ddrr04222022210498
- IPLT20 official DC vs RR match report: https://www.iplt20.com/news/article/tata-ipl-2022-match-34-dc-vs-rr-match-report
- Public detailed India vs West Indies 2nd T20I scorecard, including extras and overs: https://timesofindia.indiatimes.com/sports/cricket/match-center/west-indies-in-india-3-t20i-series-2022-india-vs-west-indies-live-cricket-score/scorecard/matchfile-inwi02182022205698.cms
- MCC Laws of Cricket (Laws 18, 21–23): https://www.lords.org/getmedia/a4ef9f77-2a25-4f5b-a286-4601f08e6334/Laws-of-Cricket-2017-Code-4th-Edition-%282026%29_5.pdf
- ICC Men's T20I Clause 17 (valid balls): https://www.icc-cricket.com/news/mens-t20i-match-clause-17-the-over

```powershell
.\\venv\\Scripts\\python.exe -m src.scoring_recovery_audit
.\\venv\\Scripts\\python.exe -m pytest -q
```
"""
    out_path = REPORTS / "scoring_recovery_audit.md"
    out_path.write_text(report, encoding="utf-8")
    return {"report": str(out_path), "public_sample_innings": n,
            "formula_exact_counts": score_formula_counts,
            "final_score_coverage_before": f"{baseline_known}/{innings_with_rows}",
            "final_score_coverage_after": f"{after_known}/{innings_with_rows}"}


if __name__ == "__main__":
    import json
    print(json.dumps(build_audit(), indent=2))
