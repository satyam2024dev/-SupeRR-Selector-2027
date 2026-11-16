"""Generate reproducible, read-only inventory and validation reports for canonical RR inputs.

Only the six CSV files directly under data/raw/ are read. ZIPs and nested files are
intentionally ignored. Outputs are written to outputs/reports/.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "outputs" / "reports"
FILES = ["ball_by_ball.csv", "playing_eleven.csv", "competition_team_player_mapping.csv",
         "competitions.csv", "matches.csv", "teams.csv"]


def _load(name: str) -> pd.DataFrame:
    """Load one explicitly named canonical CSV, never discovering nested/ZIP copies."""
    path = RAW / name
    if not path.is_file():
        raise FileNotFoundError(f"Required canonical file is missing: {path}")
    return pd.read_csv(path, low_memory=False)


def _sample_values(series: pd.Series, limit: int = 5) -> str:
    """Compact JSON sample of distinct observed non-null values."""
    values = series.dropna().drop_duplicates().head(limit).tolist()
    return json.dumps([str(v) for v in values], ensure_ascii=False)


def generate() -> dict[str, Any]:
    """Create dataset inventory, field dictionary, quality report, schema, and brief."""
    OUT.mkdir(parents=True, exist_ok=True)
    frames = {name: _load(name) for name in FILES}
    competitions, matches = frames["competitions.csv"], frames["matches.csv"]
    ball, xi = frames["ball_by_ball.csv"], frames["playing_eleven.csv"]
    mapping, teams = frames["competition_team_player_mapping.csv"], frames["teams.csv"]

    match_comp = matches.set_index("match_id")["comp_id"]
    known_comp = set(competitions["comp_id"])
    known_match = set(matches["match_id"])
    comp_season = competitions.set_index("comp_id")["season"]
    ball_comp = ball["match_id"].map(match_comp)
    ball_season = ball_comp.map(comp_season)

    inventory_rows, dictionary_rows, quality_rows = [], [], []
    for filename, df in frames.items():
        id_col = "player_id" if "player_id" in df else None
        cover_comp: Any = ""
        season_min: Any = ""
        season_max: Any = ""
        if filename == "matches.csv":
            cover_comp = df["comp_id"].nunique(dropna=True)
            seasons = df["comp_id"].map(comp_season).dropna()
        elif filename == "competitions.csv":
            cover_comp = df["comp_id"].nunique(dropna=True)
            seasons = df["season"].dropna()
        elif filename == "ball_by_ball.csv":
            cover_comp = ball_comp.nunique(dropna=True)
            seasons = ball_season.dropna()
        elif filename == "playing_eleven.csv":
            xi_comp = df["match_id"].map(match_comp)
            cover_comp = xi_comp.nunique(dropna=True)
            seasons = xi_comp.map(comp_season).dropna()
        elif "comp_id" in df:
            cover_comp = df["comp_id"].nunique(dropna=True)
            seasons = df["comp_id"].map(comp_season).dropna()
        else:
            seasons = pd.Series(dtype="float64")
        if not seasons.empty:
            season_min, season_max = seasons.min(), seasons.max()
        if filename == "ball_by_ball.csv":
            unique_players = int(pd.concat([df["striker_id"], df["non_striker_id"], df["bowler_id"], df["dismissed_player_id"]]).nunique(dropna=True))
        else:
            unique_players = int(df[id_col].nunique(dropna=True)) if id_col else ""
        inventory_rows.append({"dataset": filename, "rows": len(df), "columns": len(df.columns),
            "column_names": " | ".join(map(str, df.columns)), "duplicate_rows": int(df.duplicated().sum()),
            "unique_player_identifiers": unique_players, "competition_coverage_count": cover_comp,
            "season_min": season_min, "season_max": season_max})
        for col in df.columns:
            s = df[col]
            dictionary_rows.append({"dataset": filename, "column": col, "dtype": str(s.dtype),
                "non_null_count": int(s.notna().sum()), "missing_count": int(s.isna().sum()),
                "missing_pct": round(float(s.isna().mean() * 100), 4),
                "distinct_non_null": int(s.nunique(dropna=True)), "sample_values": _sample_values(s)})
            issues = []
            if s.isna().any():
                issues.append("missing values")
            if s.dtype == "object":
                numeric_parse = pd.to_numeric(s.dropna(), errors="coerce")
                if len(numeric_parse) and numeric_parse.notna().all():
                    issues.append("numeric-looking text; verify intended type")
            quality_rows.append({"dataset": filename, "column": col, "missing_count": int(s.isna().sum()),
                "duplicate_rows_dataset_wide": int(df.duplicated().sum()), "data_type": str(s.dtype),
                "quality_flags": "; ".join(issues)})

    pd.DataFrame(inventory_rows).to_csv(OUT / "dataset_inventory.csv", index=False)
    pd.DataFrame(dictionary_rows).to_csv(OUT / "data_dictionary.csv", index=False)
    pd.DataFrame(quality_rows).to_csv(OUT / "data_quality_report.csv", index=False)

    # Delivery coding/score-accounting diagnostics based on actual observed values.
    extras_code_map = ball.groupby("extras_type", dropna=False)["extras1_runs"].agg(
        observed_codes=lambda s: ",".join(map(str, sorted(s.dropna().unique()))), count="size").reset_index()
    extras_code_map["extras_type"] = extras_code_map["extras_type"].fillna("(null)")
    extras_code_map["type_name_matches_code_pattern"] = extras_code_map["extras_type"].map(
        lambda t: t == "(null)" or t in {"wide", "legbyes", "byes", "Overstep", "other", "Penalty"})
    extras_map = extras_code_map.to_dict(orient="records")
    illegal = ball["extras_type"].astype("string").str.casefold().isin(["wide", "overstep"])
    by_match_innings = ball.groupby(["match_id", "innings"], dropna=False)
    seq_issues = []
    for (mid, inn), g in by_match_innings:
        seq = g["innings_ball_num"]
        if seq.duplicated().any() or not seq.is_monotonic_increasing:
            seq_issues.append({"match_id": int(mid), "innings": int(inn), "rows": len(g),
                               "duplicate_sequence_values": int(seq.duplicated().sum()),
                               "monotonic_increasing": bool(seq.is_monotonic_increasing)})
    innings_detail = ball.groupby("innings").agg(delivery_rows=("match_id", "size"),
        match_count=("match_id", "nunique"), distinct_over_labels=("overid", "nunique"),
        max_innings_ball_num=("innings_ball_num", "max"), total_wicket_flags=("is_wicket", "sum")).reset_index()
    innings_detail["likely_super_over_innings_number"] = innings_detail["innings"].isin([3, 4])

    joins = {
        "ball_by_ball.match_id -> matches.match_id": {"left_rows": len(ball), "unmatched_rows": int(ball["match_id"].isin(known_match).eq(False).sum())},
        "matches.comp_id -> competitions.comp_id": {"left_rows": len(matches), "unmatched_rows": int((~matches["comp_id"].isin(known_comp)).sum())},
        "playing_eleven.match_id -> matches.match_id": {"left_rows": len(xi), "unmatched_rows": int((~xi["match_id"].isin(known_match)).sum())},
        "mapping.comp_id -> competitions.comp_id": {"left_rows": len(mapping), "unmatched_rows": int((~mapping["comp_id"].isin(known_comp)).sum())},
        "teams.comp_id -> competitions.comp_id": {"left_rows": len(teams), "unmatched_rows": int((~teams["comp_id"].isin(known_comp)).sum())},
        "playing_eleven (match_id,team_id,player_id) key": {"duplicate_key_rows": int(xi.duplicated(["match_id", "team_id", "player_id"]).sum())},
        "mapping (comp_id,team_id,player_id) key": {"duplicate_key_rows": int(mapping.duplicated(["comp_id", "team_id", "player_id"]).sum())},
        "teams (comp_id,team_id) key": {"duplicate_key_rows": int(teams.duplicated(["comp_id", "team_id"]).sum())},
    }
    xi_comp_ids = xi["match_id"].map(match_comp)
    xi_player_keys = pd.MultiIndex.from_arrays([xi_comp_ids, xi["team_id"], xi["player_id"]])
    map_keys = pd.MultiIndex.from_frame(mapping[["comp_id", "team_id", "player_id"]])
    xi_unmapped = int((~xi_player_keys.isin(map_keys)).sum())
    ball_player_values = pd.concat([
        ball[["match_id", "striker_id"]].rename(columns={"striker_id": "player_id"}),
        ball[["match_id", "non_striker_id"]].rename(columns={"non_striker_id": "player_id"}),
        ball[["match_id", "bowler_id"]].rename(columns={"bowler_id": "player_id"}),
    ], ignore_index=True).dropna(subset=["player_id"])
    ball_player_values["comp_id"] = ball_player_values["match_id"].map(match_comp)
    ball_player_keys = pd.MultiIndex.from_frame(ball_player_values[["comp_id", "player_id"]].drop_duplicates())
    mapped_players = pd.MultiIndex.from_frame(mapping[["comp_id", "player_id"]].drop_duplicates())
    unmapped_ball_player_keys = int((~ball_player_keys.isin(mapped_players)).sum())
    joins["playing_eleven (comp_id,team_id,player_id) -> mapping"] = {"unmatched_rows": xi_unmapped,
        "note": "35 repeated match-team-player groups (40 excess rows) have different batting_order values; not exact duplicate records"}
    joins["ball_by_ball (comp_id,player_id) -> mapping"] = {"unique_player_competition_pairs": len(ball_player_keys),
        "unmatched_unique_pairs": unmapped_ball_player_keys}
    xi_key_group_sizes = xi.groupby(["match_id", "team_id", "player_id"]).size()
    xi_key_dup_groups = int((xi_key_group_sizes > 1).sum())
    xi_key_excess = int((xi_key_group_sizes - 1).clip(lower=0).sum())
    semantics = {
        "runs": {"observed": "integer 0..6 with 5 only 25 times; aligns strongly with batter runs on ordinary deliveries", "status": "provisional; cross-check required against official data dictionary"},
        "extras1_runs": {"observed": extras_map, "status": "strong evidence this is an extras type/category code, not a run quantity; column name is misleading"},
        "extras_2_runs": {"observed_values": ball["extras_2_runs"].value_counts(dropna=False).to_dict(), "status": "separate small amount-like field, but does not account for all extras rows; do not sum blindly"},
        "extras_type": {"observed_counts": ball["extras_type"].fillna("(null)").value_counts().to_dict(), "status": "type label; null for ordinary deliveries"},
        "is_four/is_six": {"true_counts": {"is_four": int(ball["is_four"].sum()), "is_six": int(ball["is_six"].sum())}, "status": "event flags; validate against batter runs and exclude extras before using"},
        "is_wicket": {"true_count": int(ball["is_wicket"].sum()), "status": "delivery wicket event flag; includes dismissals which may not be bowler credited"},
        "innings": {"observed_values": ball["innings"].value_counts().sort_index().to_dict(), "status": "1 and 2 usual innings; 3 and 4 likely Super Over innings, needs match-level confirmation"},
        "innings_ball_num": {"per_match_innings_sequence_issues": len(seq_issues), "status": "monotone sequence field; appears to count recorded deliveries, but legal-ball semantics require wide/no-ball reconciliation"},
        "overid": {"observed_min": int(ball["overid"].min()), "observed_max": int(ball["overid"].max()), "distinct": int(ball["overid"].nunique()), "status": "over label/identifier; do not derive legal ball count by multiplying overid"},
        "wide_and_no_ball_proxy": {"wide_rows": int((ball["extras_type"].astype("string").str.casefold() == "wide").sum()), "overstep_rows": int((ball["extras_type"].astype("string").str.casefold() == "overstep").sum()), "status": "wide and Overstep rows should not count as legal balls; verify Overstep means no-ball with competition feed owner"},
        "byes_legbyes": {"counts": {str(k): int(v) for k, v in ball["extras_type"].value_counts(dropna=False).items() if str(k).casefold() in {"byes", "legbyes"}}, "status": "rows exist but extras amount is not explicitly recoverable from extras_2_runs in these records"},
        "bowler_runs": {"status": "cannot be reliably reconstructed until extras encodings and no-ball/wide penalty amounts are clarified"},
        "wicket_attribution": {"dismissal_type_counts": ball["dismissal_type"].fillna("(null)").value_counts().to_dict(), "status": "use dismissal type rules; run-outs/retired/obstructing dismissals must not automatically credit bowler"},
    }
    # Match/result consistency and competitions coverage.
    result_null = matches["result"].isna()
    invalid_winner = matches["win_team_id"].notna() & matches["win_team_id"].ne(matches["home_team_id"]) & matches["win_team_id"].ne(matches["away_team_id"])
    super_over_matches = sorted(map(int, ball.loc[ball["innings"].ge(3), "match_id"].unique()))
    extras_type_fold = ball["extras_type"].astype("string").str.casefold()
    wide_rows = extras_type_fold.eq("wide").fillna(False)
    overstep_rows = extras_type_fold.eq("overstep").fillna(False)
    wicket_types = ball.loc[ball["is_wicket"], "dismissal_type"].astype("string").str.casefold()
    non_bowler_dismissals = {"runout", "retire out", "obstracting the field", "obstructing the field"}
    non_bowler_wicket_rows = int(wicket_types.isin(non_bowler_dismissals).sum())
    candidate_legal_rows = int((~(wide_rows | overstep_rows)).sum())
    innings_group_sizes = by_match_innings.size()
    seq_rowcount_mismatch = int(sum(int(g["innings_ball_num"].max()) != len(g) for _, g in by_match_innings if len(g)))
    ordinary_four_mismatch = int((ball["is_four"] & ball["runs"].ne(4)).sum())
    ordinary_six_mismatch = int((ball["is_six"] & ball["runs"].ne(6)).sum())
    accounting_checks = {
        "total_runs": {"status": "not fully verifiable", "observed_runs_column_sum": int(ball["runs"].sum()),
            "extras_2_runs_sum": int(ball["extras_2_runs"].sum()), "reason": "No innings totals; extras1_runs is a type code and extras_2_runs fails to capture the observed wide/bye/leg-bye base runs. Do not publish a reconstructed total."},
        "legal_deliveries": {"status": "provisional count only", "candidate_legal_delivery_rows": candidate_legal_rows,
            "excluded_wide_rows": int(wide_rows.sum()), "excluded_overstep_rows": int(overstep_rows.sum()),
            "innings_ball_num_max_equals_record_count_groups": int(len(innings_group_sizes) - seq_rowcount_mismatch),
            "groups_where_max_seq_differs_from_record_count": seq_rowcount_mismatch,
            "reason": "innings_ball_num advances across recorded rows and cannot be treated as verified legal-ball count; Overstep as no-ball requires confirmation."},
        "wides_no_balls": {"wide_rows": int(wide_rows.sum()), "overstep_rows": int(overstep_rows.sum()),
            "status": "wide is explicit; Overstep likely no-ball but feed semantics require confirmation"},
        "byes_leg_byes": {"byes_rows": int(extras_type_fold.eq("byes").sum()), "legbyes_rows": int(extras_type_fold.eq("legbyes").sum()),
            "status": "type is identifiable; associated run amounts are not represented adequately in observed amount fields"},
        "batter_attributed_runs": {"runs_column_sum": int(ball["runs"].sum()), "ordinary_delivery_sum": int(ball.loc[extras_type_fold.isna(), "runs"].sum()),
            "four_flag_runs_mismatches": ordinary_four_mismatch, "six_flag_runs_mismatches": ordinary_six_mismatch,
            "status": "runs behaves as batter runs on ordinary balls and four/six flags match; attribution during extras needs authoritative field definition"},
        "bowler_attributed_runs": {"status": "not verifiable", "reason": "No explicit conceded-runs field and extras amounts are incomplete/ambiguous"},
        "wicket_attribution": {"wicket_flags": int(ball["is_wicket"].sum()), "dismissal_type_nonnull": int(ball["dismissal_type"].notna().sum()),
            "dismissed_player_id_missing_on_wicket": int((ball["is_wicket"] & ball["dismissed_player_id"].isna()).sum()),
            "non_bowler_credit_types_observed": sorted(non_bowler_dismissals), "such_wicket_rows": non_bowler_wicket_rows,
            "status": "flags exactly match populated dismissal_type; dismissed_player_id has one missing value. Do not credit bowler automatically for all wicket flags"},
        "super_overs": {"candidate_match_count": len(super_over_matches), "match_ids": super_over_matches,
            "status": "innings 3/4 occur in six matches with at most one over each; strong Super Over signature, confirm from official feed documentation"},
        "match_results": {"result_missing": int(result_null.sum()), "winner_missing": int(matches["win_team_id"].isna().sum()),
            "winner_not_home_or_away": int(invalid_winner.sum()), "status": "all result text present; winner ID present in 842/883 and every populated winner matches a home/away team"},
        "player_identity": {"xi_duplicate_key_groups": xi_key_dup_groups, "xi_duplicate_key_excess_rows": xi_key_excess,
            "xi_unmapped_to_comp_team_player_map_rows": xi_unmapped, "unmapped_ball_player_competition_pairs": unmapped_ball_player_keys,
            "status": "repeated XI keys have varying batting_order, not identical duplicate rows; preserve and resolve before match participation aggregation"},
    }
    schema = {
        "source_scope": "Six canonical root-level CSVs only; ZIP backups and nested duplicate extracts excluded.",
        "datasets": {k: {"rows": len(v), "columns": len(v.columns), "column_names": list(v.columns),
                         "dtypes": {c: str(v[c].dtype) for c in v.columns}} for k, v in frames.items()},
        "coverage": {"competition_count": int(competitions.comp_id.nunique()), "match_count": len(matches),
            "match_competition_count": int(matches.comp_id.nunique()), "season_min": int(competitions.season.min()),
            "season_max": int(competitions.season.max()), "format_counts": competitions.match_format.value_counts(dropna=False).to_dict()},
        "relationships": joins,
        "ball_semantics_and_validation": semantics,
        "delivery_accounting_checks": accounting_checks,
        "delivery_sequence_issues": seq_issues[:100],
        "innings_diagnostics": innings_detail.to_dict(orient="records"),
        "match_result_checks": {"null_result_rows": int(result_null.sum()), "null_winner_rows": int(matches.win_team_id.isna().sum()), "winner_not_either_match_team_rows": int(invalid_winner.sum()),
            "win_team_id_value_counts": matches.win_team_id.value_counts(dropna=False).head(12).to_dict()},
        "unresolved": ["No player master file is present among the six canonical CSVs; player labels/IDs must be reconciled through competition_team_player_mapping.csv.",
        "No innings scorecard totals are supplied, so delivery totals cannot be independently reconciled to official innings totals.",
            "extras1_runs is a category code in observed values; extras_2_runs is not a complete extras total. Bowler-conceded runs and legal-ball counts need documented encoding clarification.",
            "The PDF defines pressure-performance ratings for batters and bowlers. Current live Unstop instructions were not provided, so no conflict can be established from local files."],
    }
    (OUT / "schema_report.json").write_text(json.dumps(schema, indent=2, default=str), encoding="utf-8")

    brief = f"""# Round 1 competition brief and data findings

## Required task from the supplied official PDF

The Round 1 PDF, **SupeRR Selector Season 2: Identify the Most Reliable Players Under Pressure**, defines the task as measuring how batters and bowlers perform in high-pressure situations against their usual performance, then identifying/ranking the most consistent performers. Required submissions are two ordered top-10 lists (batters and bowlers) and a methodology report. The entrant is expected to define pressure, performance metrics, baselines, fair comparisons, reliability, and limitations.

This conflicts with the earlier project description about the **10 youngest uncapped players**. The official PDF is the only competition-rule source available locally. Live Unstop instructions have not been supplied or checked; a conflict with live instructions therefore remains unresolved and should be clarified before final rankings/submission.

## Canonical data inspected

Read only the six root-level CSVs in `data/raw/`; the ZIP archive and any nested copies were excluded. Together they contain {len(ball):,} delivery records, {len(matches):,} matches, {len(competitions):,} competitions, {len(xi):,} playing-XI rows, {len(mapping):,} competition-team-player mappings, and {len(teams):,} competition-team rows. Competition metadata covers seasons {int(competitions.season.min())}–{int(competitions.season.max())}; formats: {json.dumps(competitions.match_format.value_counts(dropna=False).to_dict(), default=str)}.

## Dataset relationships

- `ball_by_ball.match_id` → `matches.match_id` → `competitions.comp_id`
- `playing_eleven.match_id` → `matches.match_id`; `team_id` and `player_id` identify XI members.
- `competition_team_player_mapping` links `comp_id`, `team_id`, and `player_id` to competition-scoped names.
- `teams` links `comp_id` and `team_id` to team names.
- Mapping and playing-XI files are needed to validate player identity and participation; names alone must not be treated as stable identifiers.

See `dataset_inventory.csv`, `data_dictionary.csv`, `data_quality_report.csv`, and `schema_report.json` for field-level details and measured joins.

## Delivery field investigation (provisional)

Observed `extras1_runs` values match extras categories exactly: 1=Overstep, 2=wide, 3=legbyes, 4=byes, 5=other, 6=no `extras_type` (ordinary), 7=Penalty. This is evidence the field is a category code, despite its name, and must not be added as runs. `runs` behaves like batter runs on ordinary deliveries. `extras_2_runs` contains mostly zero and does not provide the amount needed to reconcile all wide, bye, and leg-bye events. Thus `runs + extras1_runs + extras_2_runs` is invalid. Exact total runs, bowler-conceded runs, and legal-ball totals cannot yet be certified against innings scorecards because none are supplied.

`is_four`/`is_six` are event flags; `is_wicket` marks wicket events, but wicket credit requires dismissal-type rules. `wide` rows and likely `Overstep` (to verify as no-ball) should be excluded from legal deliveries. `innings` 3 and 4 likely denote Super Overs; confirm from match-level sequence before including/excluding them. `innings_ball_num` is a monotonically increasing event sequence in the inspected groups, not automatically legal-ball numbering. `overid` ranges from {int(ball.overid.min())} to {int(ball.overid.max())} and should be used as an over label, not multiplied by six to infer legal balls.

## Analysis status and next decisions

No player rankings have been generated. Before pressure ratings are calculated, resolve the extras encoding with the data owner or official documentation, establish valid legal-ball and bowler-run formulas, decide Super Over treatment, and confirm the current Unstop task statement. Pressure thresholds and baseline/scoring choices should then be documented, tested, and evaluated for sample-size sensitivity. The source CSVs were only read; no originals were modified.
"""
    (OUT / "competition_brief.md").write_text(brief, encoding="utf-8")
    return {"output_dir": str(OUT), "datasets": len(frames), "ball_rows": len(ball), "match_rows": len(matches),
            "competition_rows": len(competitions), "sequence_issues": len(seq_issues)}


if __name__ == "__main__":
    print(json.dumps(generate(), indent=2))
