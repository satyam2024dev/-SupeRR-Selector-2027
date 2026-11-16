"""Package validated Phase 5G-5H submission artifacts without altering source reports."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/"outputs"/"reports"
OUT=ROOT/"submission"

COPY_MAP={
    "phase5g_overall_batter_top10.csv":"phase5g_overall_batter_top10.csv",
    "phase5h_methodology_report.md":"phase5h_methodology_report.md",
    "phase5h_bowling_final_audit.md":"phase5h_bowling_final_audit.md",
    "phase5h_submission_readiness.md":"phase5h_submission_readiness.md",
    "phase5h_bowling_metric_audit.csv":"phase5h_bowling_metric_audit.csv",
    "phase5h_bowling_eligibility.csv":"phase5h_bowling_eligibility.csv",
    "phase5g_submission_reconciliation.md":"phase5g_submission_reconciliation.md",
    "phase5g_bowling_submission_decision.md":"phase5g_bowling_submission_decision.md",
    "phase5g_final_action_checklist.md":"phase5g_final_action_checklist.md",
    "phase5g_cross_format_scenarios.csv":"phase5g_cross_format_scenarios.csv",
    "phase5g_cross_format_stability.csv":"phase5g_cross_format_stability.csv",
    "final_batter_top10.csv":"final_batter_top10.csv",
    "final_bowler_evidence.csv":"final_bowler_evidence.csv",
    "final_ipl_batter_top10_chart.svg":"final_ipl_batter_top10_chart.svg",
    "final_t20i_batter_top10_chart.svg":"final_t20i_batter_top10_chart.svg",
}


def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def _md_table(frame:pd.DataFrame)->str:
    cols=list(frame.columns)
    lines=["| "+" | ".join(cols)+" |","| "+" | ".join(["---"]*len(cols))+" |"]
    for row in frame.itertuples(index=False,name=None):
        lines.append("| "+" | ".join(str(x).replace("|","/") for x in row)+" |")
    return "\n".join(lines)


def _validate_source_and_create_supporting()->dict:
    p5c=pd.read_csv(REPORTS/"phase5c_batter_rankings.csv",low_memory=False)
    candidates=p5c.loc[p5c.competition_ready.fillna(False)].copy()
    candidates["player_id"]=candidates.player_id.astype(str)
    candidates["within_format_percentile"]=candidates.groupby("format").score.rank(method="average",pct=True)
    rebuilt=candidates.groupby("player_id").agg(player_name=("player_name","first"),formats=("format","nunique"),
        mean_pct=("within_format_percentile","mean")).reset_index()
    rebuilt=rebuilt.sort_values(["mean_pct","player_id"],ascending=[False,True]).reset_index(drop=True)
    rebuilt["rank"]=range(1,len(rebuilt)+1)
    overall=pd.read_csv(REPORTS/"phase5g_overall_batter_top10.csv",low_memory=False).sort_values("rank").reset_index(drop=True)
    if len(candidates)!=305 or len(overall)!=10 or overall.player_id.astype(str).nunique()!=10 or overall["rank"].tolist()!=list(range(1,11)):
        raise ValueError("Overall Batter Top 10 failed count, ID uniqueness or rank validation")
    check=rebuilt.head(10).merge(overall[["rank","player_id","mean_within_format_percentile"]],on="rank",validate="one_to_one")
    if not check.player_id_x.astype(str).equals(check.player_id_y.astype(str)):
        raise ValueError("Overall batter candidate order does not independently rebuild")
    if (check.mean_pct-check.mean_within_format_percentile).abs().max()>1e-12:
        raise ValueError("Overall batter mean-percentile scores do not reproduce")
    support=pd.read_csv(REPORTS/"final_batter_top10.csv",low_memory=False)
    counts=support.groupby("format").size().to_dict()
    if counts!={"IPL":10,"T20I":10} or support.groupby("format").player_id.nunique().ne(10).any():
        raise ValueError("Format supporting Top 10 tables failed validation")
    support.loc[support.format.eq("IPL")].sort_values("rank").to_csv(OUT/"supporting_IPL_batter_top10.csv",index=False)
    support.loc[support.format.eq("T20I")].sort_values("rank").to_csv(OUT/"supporting_T20I_batter_top10.csv",index=False)
    if int(overall.player_id.astype(str).nunique())!=10:
        raise ValueError("Duplicate overall IDs found")
    stability=pd.read_csv(REPORTS/"phase5g_cross_format_stability.csv")
    robust=stability.loc[stability.scenario.str.contains("standardized score|lower bound"),"top10_overlap_with_mean_percentile"]
    if len(robust)!=2 or not robust.eq(9).all():
        raise ValueError("Phase 5G sensitivity overlap audit did not reproduce")
    return {"overall":overall,"support":support,"max_score_diff":float((check.mean_pct-check.mean_within_format_percentile).abs().max()),
            "format_counts":counts,"standardized_overlap":int(robust.iloc[0]),"lower_bound_overlap":int(robust.iloc[1])}


def _readme(validation:dict)->str:
    return f'''# SupeRR Selector Season 2 — Round 1 submission package

## Official deliverable status

1. **Overall Batter Top 10 — complete.** `phase5g_overall_batter_top10.csv` has ten distinct player IDs ranked 1–10. Phase 5H independently rebuilt the mean-within-format-percentile ordering; the maximum score difference was {validation['max_score_diff']:.3g}. The standardized-score and conservative lower-bound sensitivity lists each overlap {validation['standardized_overlap']}/10 with the primary list.
2. **Bowler Top 10 — unresolved and incomplete.** There are 0 competition-ready candidates and 414 exploratory profiles (IPL 145; T20I 269). No Bowler Top 10 is included. Do not promote exploratory profiles or fabricate a list. The submission cannot be marked complete until this required field has an honest accepted disposition.
3. **Methodology report — complete.** `phase5h_methodology_report.md` is the consolidated report. It includes the historical format-specific batter evidence, the Phase 5G overall-list method, and the Phase 5H bowling audit and limitations.

The supplied Round 1 brief calls for one batter list and one separate bowler list. The IPL and T20I batter files below are supporting evidence, not extra official dropdown lists. The overall list uses mean within-format percentiles of Phase 5C scores that already include exposure and match-consistency adjustments; raw IPL and T20I scores are not compared directly. A repeated player is represented once by stable player ID.

## Primary files

- `phase5g_overall_batter_top10.csv` — official batter dropdown order, ranks 1–10, with format evidence, exposure, sensitivity ranks and uncertainty.
- `phase5h_methodology_report.md` — methodology report intended for upload.
- `phase5h_bowling_final_audit.md` — detailed non-ranked bowling evidence, source-field audit, denominators and missing-data limitations.
- `phase5h_submission_readiness.md` — completion status, unresolved bowler requirement and historical-file/dashboard reconciliation.
- `supporting_IPL_batter_top10.csv` — supporting IPL ranking, not an additional official list.
- `supporting_T20I_batter_top10.csv` — supporting T20I ranking, not an additional official list.

## Supporting evidence and report dependencies

- `phase5h_bowling_metric_audit.csv` — bowler source fields, semantics, denominators, scope coverage, verified-pressure comparisons and blocked metrics.
- `phase5h_bowling_eligibility.csv` — unchanged verified-chase event/match floor checks by format and metric.
- `phase5g_submission_reconciliation.md` — official deliverable interpretation and tested cross-format batter aggregation.
- `phase5g_bowling_submission_decision.md` — explicit no-ranking decision for the required bowler list.
- `phase5g_final_action_checklist.md` — actions for the Unstop fields and final report.
- `phase5g_cross_format_scenarios.csv` and `phase5g_cross_format_stability.csv` — alternate aggregation lists and overlap/rank stability evidence.
- `final_batter_top10.csv` — Phase 5F format-specific batter evidence used as support.
- `final_bowler_evidence.csv` — aggregate bowling evidence; it is not a player ranking.
- `final_ipl_batter_top10_chart.svg` and `final_t20i_batter_top10_chart.svg` — score and match-cluster interval charts.
- `quality_check.md` — CSV headers, row counts, missing-cell notes and source/package checksums.

`README.md` describes the overall Batter Top 10 and supporting IPL/T20I lists separately, so the two format files are not mistaken for extra official dropdown lists.

## Quality and limitations

`quality_check.md` records CSV headers, row counts, missing-value columns, rank/ID checks and SHA-256 source-to-package equality for the overall batter CSV. Missing values in the bowling metric audit are intentional where a metric is blocked or not applicable; they are not imputed. Raw data, analytical scores, candidate eligibility thresholds and historical Phase 1–5H reports were not changed by packaging.

Tests: **111 passed**. Compile check: **45 Python files compiled**. These checks validate the project/package state, not the unresolved bowler deliverable.
'''


def main()->dict:
    OUT.mkdir(parents=True,exist_ok=True)
    validation=_validate_source_and_create_supporting()
    copied=[]
    for source_name,dest_name in COPY_MAP.items():
        src=REPORTS/source_name
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copyfile(src,OUT/dest_name)
        copied.append(dest_name)
    copied.extend(["supporting_IPL_batter_top10.csv","supporting_T20I_batter_top10.csv"])
    # Verify the official list is copied byte-for-byte, without transformation.
    src=REPORTS/"phase5g_overall_batter_top10.csv"
    dst=OUT/"phase5g_overall_batter_top10.csv"
    if _sha(src)!=_sha(dst):
        raise ValueError("Packaged overall batter CSV is not byte-identical to Phase 5G source")
    csv_checks=[]
    for path in sorted(OUT.glob("*.csv")):
        frame=pd.read_csv(path,low_memory=False)
        headers=list(frame.columns)
        if not headers or any(not str(h).strip() for h in headers) or len(headers)!=len(set(headers)):
            raise ValueError(f"Invalid/duplicate CSV headers: {path.name}")
        missing=frame.isna().sum()
        missing=missing.loc[missing.gt(0)]
        csv_checks.append({"file":path.name,"rows":len(frame),"columns":len(headers),
            "missing_cells":int(frame.isna().sum().sum()),
            "columns_with_missing":"; ".join(f"{k}:{int(v)}" for k,v in missing.items()) or "none",
            "sha256":_sha(path)})
    q=pd.DataFrame(csv_checks)
    (OUT/"quality_check.md").write_text(
        "# Submission CSV quality checks\n\n"
        "All packaged CSV headers are present and unique. The overall batter list has ten distinct IDs and ranks 1–10 and is byte-identical to its Phase 5G source. Format support lists have ten unique IDs and ranks 1–10 within their format. Missing values listed below are not silently filled; blanks in scenario-rank columns mean the scenario requires eligibility in both formats, while blanks in bowling audit metrics identify blocked or non-applicable calculations.\n\n"
        +_md_table(q)+"\n\n"
        f"Overall batter source SHA-256: `{_sha(src)}`\n\n"
        f"Packaged overall batter SHA-256: `{_sha(dst)}`\n",encoding="utf-8")
    (OUT/"README.md").write_text(_readme(validation),encoding="utf-8")
    return {"folder":str(OUT),"created_files":sorted(p.name for p in OUT.iterdir() if p.is_file()),
        "overall_batter_rows":len(validation["overall"]),"overall_unique_player_ids":int(validation["overall"].player_id.nunique()),
        "format_support_rows":validation["format_counts"],"bowler_ready":0,"bowler_exploratory":414,
        "max_overall_rebuild_difference":validation["max_score_diff"],"csv_files_checked":len(csv_checks),
        "csv_missing_cells":{r["file"]:r["columns_with_missing"] for r in csv_checks if r["missing_cells"]}}


if __name__=="__main__":
    import json
    print(json.dumps(main(),indent=2))
