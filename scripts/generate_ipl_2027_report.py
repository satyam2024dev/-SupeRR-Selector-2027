from __future__ import annotations

import csv
import html
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REPORTS = ROOT / "outputs" / "reports"
SUBMISSION = ROOT / "submission"
OVERLAY = ROOT / "data" / "external" / "ipl_2027_player_availability.csv"
HTML_OUT = REPORTS / "rajasthan_royals_ipl_2027_performance_auction_readiness.html"
PDF_OUT = REPORTS / "rajasthan_royals_ipl_2027_performance_auction_readiness.pdf"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def fmt_int(value: object) -> str:
    return f"{int(float(value)):,}"


def fnum(value: object, places: int = 3) -> str:
    if value in (None, ""):
        return "-"
    return f"{float(value):.{places}f}"


def table(headers: list[str], rows: list[list[object]], classes: str = "", widths: list[int] | None = None) -> str:
    head = "".join(f"<th>{esc(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(x)}</td>" for x in row) + "</tr>" for row in rows)
    colgroup = "" if widths is None else "<colgroup>" + "".join(f'<col style="width:{x}%">' for x in widths) + "</colgroup>"
    return f'<table class="{esc(classes)}">{colgroup}<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def validate_sources() -> dict[str, object]:
    overall = read_csv(SUBMISSION / "phase5g_overall_batter_top10.csv")
    overall_report = read_csv(REPORTS / "phase5g_overall_batter_top10.csv")
    assert len(overall) == len(overall_report) == 10
    assert [r["rank"] for r in overall] == [str(i) for i in range(1, 11)]
    assert [(r["rank"], r["player_id"], r["player_name"], r["mean_within_format_percentile"]) for r in overall] == [
        (r["rank"], r["player_id"], r["player_name"], r["mean_within_format_percentile"]) for r in overall_report
    ]
    supporting = {fmt: read_csv(SUBMISSION / f"supporting_{fmt}_batter_top10.csv") for fmt in ("IPL", "T20I")}
    phase5c_batters = read_csv(REPORTS / "phase5c_batter_rankings.csv")
    phase5c_by_key = {(r["format"], r["player_id"]): r for r in phase5c_batters if r["competition_ready"].casefold() == "true"}
    for fmt, rows in supporting.items():
        assert len(rows) == 10 and [r["rank"] for r in rows] == [str(i) for i in range(1, 11)]
        assert all(r["format"] == fmt for r in rows)
        for row in rows:
            base = phase5c_by_key[(fmt, row["player_id"])]
            assert (row["rank"], row["player_name"], row["score"]) == (base["rank"], base["player_name"], base["score"])

    coverage = read_csv(REPORTS / "confirmed_scope_coverage_summary.csv")
    assert {r["format"] for r in coverage} == {"IPL", "T20I"}
    bowling = read_csv(REPORTS / "phase5c_bowler_rankings.csv")
    assert len(bowling) == 414 and not any(r["competition_ready"].casefold() == "true" for r in bowling)
    assert Counter(r["format"] for r in bowling) == {"IPL": 145, "T20I": 269}
    eligibility = read_csv(SUBMISSION / "phase5h_bowling_eligibility.csv")
    assert len(eligibility) == 8 and all(int(r["players_meeting_both_sides"]) == 0 for r in eligibility)
    metric_audit = read_csv(SUBMISSION / "phase5h_bowling_metric_audit.csv")
    scenarios = read_csv(SUBMISSION / "phase5g_cross_format_scenarios.csv")
    stability = read_csv(SUBMISSION / "phase5g_cross_format_stability.csv")
    assert len(scenarios) == len(stability) == 5

    overlay = read_csv(OVERLAY)
    assert len(overlay) == 252 and {r["verification_date"] for r in overlay} == {"2026-11-13"}
    statuses = Counter(r["ipl_2027_status"] for r in overlay)
    assert statuses == {"unknown_unverified": 245, "traded_to_other_franchise": 7}
    assert Counter(r["candidate_role"] for r in overlay) == {"batter": 107, "bowler": 145}
    traded_ids = {r["player_id"] for r in overlay if r["ipl_2027_status"] == "traded_to_other_franchise"}
    assert len(traded_ids) == 6
    assert all(r["source_url"] and r["source_publication_date"] for r in overlay if r["ipl_2027_status"] == "traded_to_other_franchise")
    assert not any(r["ipl_2027_status"] in {"officially_registered_for_auction", "included_in_final_auction_register"} for r in overlay)
    assert all(not r["source_publication_date"] for r in overlay if r["ipl_2027_status"] == "unknown_unverified")
    assert all(r["source_url"] == "https://www.iplt20.com/news" for r in overlay if r["ipl_2027_status"] == "unknown_unverified")

    try:
        from src.phase5h_final_audit import verify_overall_batters
        audit_summary, _ = verify_overall_batters()
        if isinstance(audit_summary, dict):
            audit = audit_summary
        else:
            audit = audit_summary.to_dict()
    except Exception as exc:
        raise RuntimeError(f"Phase 5H independent Phase 5G verification failed: {exc}") from exc
    assert audit.get("overall_rank_order_reproduced") is True
    assert audit.get("mean_percentile_score_max_abs_diff") == 0.0
    assert audit.get("overall_unique_player_ids") == 10
    return {
        "overall": overall, "supporting": supporting, "coverage": coverage,
        "bowling": bowling, "eligibility": eligibility, "metric_audit": metric_audit,
        "scenarios": scenarios, "stability": stability,
        "overlay": overlay, "statuses": statuses, "traded_ids": traded_ids, "audit": audit,
    }


def build_html(data: dict[str, object]) -> str:
    overall = data["overall"]
    supporting = data["supporting"]
    coverage = {r["format"]: r for r in data["coverage"]}
    overlay = data["overlay"]
    statuses = data["statuses"]
    metric_audit = data["metric_audit"]
    eligibility = data["eligibility"]
    audit = data["audit"]

    overall_rows = []
    for r in overall:
        overall_rows.append([
            r["rank"], r["player_id"], r["player_name"], r["mean_within_format_percentile"], r["formats"],
            f'{fmt_int(r["mean_pressure_events"])} / {fmt_int(r["mean_pressure_matches"])}',
            f'{fmt_int(r["mean_baseline_events"])} / {fmt_int(r["mean_baseline_matches"])}',
            f'{fnum(r["mean_consistency_factor"], 3)} / {fnum(r["mean_exposure_shrinkage"], 3)}',
        ])
    overall_table = table(
        ["Rank", "Player ID", "Player", "Stored mean percentile", "Format support", "Contextual cohort events / matches", "Baseline events / matches", "Consistency / shrinkage"],
        overall_rows, "rank-table tight", [5, 9, 18, 16, 10, 14, 14, 14],
    )

    def support_table(rows: list[dict[str, str]]) -> str:
        values = []
        stability_values = []
        for r in rows:
            values.append([
                r["rank"], r["player_id"], r["player_name"], r["score"],
                f'{r["score_ci95_low"]} - {r["score_ci95_high"]}',
                f'{r["pressure_events"]} / {r["pressure_matches"]}',
                f'{r["baseline_events"]} / {r["baseline_matches"]}',
            ])
            label = {"stable_top10_candidate": "Stable top-10", "method_or_sample_sensitive": "Method/sample-sensitive"}.get(r["stability_flag"], r["stability_flag"])
            stability_values.append([
                r["rank"], r["player_id"], fnum(r["consistency_factor"]), fnum(r["exposure_shrinkage_factor"]),
                fnum(r["leave_one_match_top10_rate"]), fnum(r["leave_one_season_top10_rate"]), label,
            ])
        primary = table(
            ["Rank", "Player ID", "Player", "Stored Phase 5C score", "Stored 95% score interval", "Contextual events / matches", "Baseline events / matches"],
            values, "rank-table tight support-table", [5, 9, 19, 17, 23, 14, 13],
        )
        stability = table(
            ["Rank", "Player ID", "Consistency factor", "Exposure shrinkage", "Leave-one-match Top 10 rate", "Leave-one-season Top 10 rate", "Stored stability flag"],
            stability_values, "rank-table tight support-table", [5, 9, 13, 14, 19, 19, 21],
        )
        return primary + '<h3 class="compact-heading">Stored consistency and stability indicators</h3>' + stability + '<p class="note">Display labels shorten the source flags: "Stable top-10" = <code>stable_top10_candidate</code>; "Method/sample-sensitive" = <code>method_or_sample_sensitive</code>. Auxiliary consistency, shrinkage, and leave-one-out rates are shown to three decimals for readability.</p>'

    def chart() -> str:
        max_matches = max(int(r["match_count"]) for r in coverage.values())
        max_deliveries = max(int(r["delivery_count"]) for r in coverage.values())
        lines = []
        for fmt in ("IPL", "T20I"):
            r = coverage[fmt]
            mwidth = max(3, round(280 * int(r["match_count"]) / max_matches))
            dwidth = max(3, round(280 * int(r["delivery_count"]) / max_deliveries))
            lines.append(f'<div class="chart-row"><strong>{fmt}</strong><div class="chart-cell"><span class="bar-label">{fmt_int(r["match_count"])} matches</span><i style="width:{mwidth}px"></i></div><div class="chart-cell"><span class="bar-label">{fmt_int(r["delivery_count"])} deliveries</span><i class="delivery" style="width:{dwidth}px"></i></div></div>')
        return '<div class="coverage-chart"><div class="chart-head"><span>Format</span><span>Confirmed-scope matches</span><span>Confirmed-scope deliveries</span></div>' + "".join(lines) + '<p class="chart-note">Each measure uses its own zero-to-maximum scale across these two formats; labels show exact stored counts. This compares evidence volume only.</p></div>'

    def audit_row(fmt: str, metric: str) -> dict[str, str]:
        return next(r for r in metric_audit if r["format"] == fmt and r["metric"] == metric)

    bowling_rows = []
    for fmt in ("IPL", "T20I"):
        chase = audit_row(fmt, "verified chase pressure exposure")
        wickets = audit_row(fmt, "recognized bowler-credited wickets")
        economy = audit_row(fmt, "economy rate")
        sr = audit_row(fmt, "conventional bowling strike rate")
        eligible = [r for r in eligibility if r["format"] == fmt]
        bowling_rows.extend([
            [fmt, "Verified chase-state rows", f'{fmt_int(chase["metric_numerator_or_observed_value"])} / {fmt_int(chase["metric_denominator"])}', f'{fnum(float(chase["calculated_value_or_coverage"]) * 100, 3)}%', "Sparse observed chase-state coverage; not player eligibility"],
            [fmt, "Recognized credited wicket events", f'{fmt_int(wickets["metric_numerator_or_observed_value"])} / {fmt_int(wickets["metric_denominator"])} scoped rows', "Event count only", "Not conventional bowling strike rate"],
            [fmt, "Economy rate", "Not calculated", "Blocked", economy["decision"]],
            [fmt, "Conventional bowling strike rate", "Not calculated", "Blocked", sr["decision"]],
            [fmt, "Players meeting both verified-chase floors", str(sum(int(x["players_meeting_both_sides"]) for x in eligible)), "0 competition-ready", "No candidate passes both sides; floors unchanged"],
        ])
    bowling_table = table(["Format", "Evidence item", "Observed value / denominator", "Status", "Interpretation"], bowling_rows, "tight", [9, 27, 20, 16, 28])

    role_counts = Counter(r["candidate_role"] for r in overlay)
    status_rows = [
        ["Unknown / unverified", statuses["unknown_unverified"], "Player-specific 2027 status not verified; publication date absent in these rows"],
        ["Traded to another franchise", statuses["traded_to_other_franchise"], f'{len(data["traded_ids"])} distinct player IDs; trade alone does not prove release or auction registration'],
        ["Released, registration unverified", 0, "No row in this status category in the dated overlay"],
        ["Retained / contracted", 0, "No row in this status category in the dated overlay"],
        ["Officially registered for auction", 0, "No player-specific registration record in the dated overlay"],
        ["Included in final auction register", 0, "Final register not present in the project snapshot"],
    ]
    status_table = table(["Overlay status category", "Role rows", "Meaning / limit"], status_rows, "tight", [30, 12, 58])

    covrows = [[fmt, fmt_int(coverage[fmt]["competition_count"]), f'{coverage[fmt]["season_count"]} ({coverage[fmt]["season_labels"].split(";")[0]}-{coverage[fmt]["season_labels"].split(";")[-1]})', fmt_int(coverage[fmt]["match_count"]), fmt_int(coverage[fmt]["innings_count"]), fmt_int(coverage[fmt]["delivery_count"]), coverage[fmt]["date_min"] + " - " + coverage[fmt]["date_max"]] for fmt in ("IPL", "T20I")]
    covtable = table(["Format", "Competitions", "Seasons", "Matches", "Innings", "Deliveries", "Data window"], covrows, "tight", [9, 12, 24, 9, 9, 12, 25])

    stability_by_scenario = {r["scenario"]: r for r in data["stability"]}
    scenario_rows = []
    for row in data["scenarios"]:
        label = row["scenario"]
        overlap = stability_by_scenario[label]["top10_overlap_with_mean_percentile"]
        if label.startswith("mean within-format percentile"):
            interpretation = "Selected reference method"
        elif "lower bound" in label:
            interpretation = "Event-count interval; not cluster-robust for full pool"
        elif "best available" in label:
            interpretation = "Optimistic duplicate rule; rejected"
        elif "both formats" in label:
            interpretation = "Eligibility participation filter; rejected"
        else:
            interpretation = "Sensitivity; not a replacement list"
        scenario_rows.append([label, row["candidate_pool"], f'{overlap}/10', interpretation])
    scenario_table = table(["Phase 5G diagnostic", "Candidate pool", "Top 10 overlap", "Use"], scenario_rows, "tight", [43, 14, 18, 25])

    source_items = [
        ("Phase 5G frozen overall list", "submission/phase5g_overall_batter_top10.csv"),
        ("Phase 5C IPL/T20I supporting lists", "submission/supporting_IPL_batter_top10.csv; submission/supporting_T20I_batter_top10.csv"),
        ("Phase 5H independent ranking verification", "src/phase5h_final_audit.py; submission/phase5h_submission_readiness.md"),
        ("Phase 5H bowling metric evidence", "submission/phase5h_bowling_metric_audit.csv; submission/phase5h_bowling_eligibility.csv; submission/phase5h_bowling_final_audit.md"),
        ("Coverage and Phase 5C ranking source", "outputs/reports/confirmed_scope_coverage_summary.csv; outputs/reports/phase5c_batter_rankings.csv; outputs/reports/phase5c_bowler_rankings.csv"),
        ("Availability audit overlay (local operator-managed input)", "data/external/ipl_2027_player_availability.csv; snapshot verified 2026-11-13"),
        ("Application quality and interpretation controls", "docs/final_application_audit.md; docs/ipl_2027_pdf_readiness.md"),
        ("Phase 5I artifacts", "No Phase 5I-named artifact was found in submission/ or outputs/reports/; none is represented as completed or used."),
    ]
    source_table = table(["Evidence", "Source reference"], [[a, b] for a, b in source_items], "tight source-table", [31, 69])

    p5h_rows = [
        ["Ready player-format rows", audit["competition_ready_format_rows"]],
        ["Frozen overall rows / unique IDs", f'{audit["overall_top10_rows"]} / {audit["overall_unique_player_ids"]}'],
        ["Rank order reproduced", str(audit["overall_rank_order_reproduced"])],
        ["Maximum absolute percentile difference", str(audit["mean_percentile_score_max_abs_diff"])],
        ["Scenario count", audit["scenario_count"]],
        ["Supporting format rows", "IPL 10; T20I 10"],
    ]
    validate_table = table(["Independent validation check", "Result"], p5h_rows, "tight", [73, 27])

    html_doc = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Rajasthan Royals IPL 2027 - Performance Analysis &amp; Auction Readiness Report</title>
<style>
@page {{ size: A4 portrait; margin: 17mm 16mm 18mm; }}
* {{ box-sizing: border-box; }}
html {{ color: #142237; background: #fff; font-family: "Aptos", "Arial", sans-serif; }}
body {{ margin: 0; font-size: 9.2pt; line-height: 1.43; }}
.running-head {{ position: fixed; top: -12mm; left: 0; right: 0; height: 6mm; border-bottom: .5pt solid #bdc9d8; color: #63748a; font-size: 7.5pt; letter-spacing: .08em; text-transform: uppercase; }}
.running-foot {{ position: fixed; bottom: -13mm; left: 0; right: 0; height: 6mm; border-top: .5pt solid #bdc9d8; display: flex; justify-content: space-between; color: #63748a; font-size: 7.5pt; padding-top: 2mm; }}
.page-number:after {{ content: counter(page); }}
.cover {{ min-height: 255mm; display: flex; flex-direction: column; justify-content: space-between; padding: 30mm 9mm 15mm; page-break-after: always; background: linear-gradient(145deg,#102740,#173e58 62%,#0f273a); color: #fff; margin: -17mm -16mm -18mm; padding-left: 25mm; padding-right: 25mm; }}
.cover-mark {{ color: #c8e5d1; font-size: 10pt; font-weight: 700; letter-spacing: .23em; text-transform: uppercase; }}
.cover h1 {{ max-width: 160mm; margin: 18mm 0 7mm; font-family: Georgia, serif; font-size: 33pt; line-height: 1.09; font-weight: 500; letter-spacing: -.03em; }}
.cover-subtitle {{ max-width: 148mm; color: #d5e3e9; font-size: 16pt; line-height: 1.35; }}
.cover-rule {{ width: 38mm; height: 2mm; margin: 10mm 0; background: #d2b071; }}
.cover-meta {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm 15mm; max-width: 145mm; border-top: 1px solid rgba(255,255,255,.28); padding-top: 7mm; }}
.cover-meta span {{ display: block; color: #a9c1cb; font-size: 7.5pt; letter-spacing: .12em; text-transform: uppercase; }}
.cover-meta strong {{ display: block; margin-top: 1.5mm; font-size: 10pt; font-weight: 600; }}
.cover-note {{ max-width: 148mm; color: #b8cbd2; font-size: 8.5pt; }}
h1,h2,h3 {{ break-after: avoid; }} h2 {{ margin: 0 0 3mm; color: #14324b; font-family: Georgia,serif; font-size: 21pt; font-weight: 500; }}
h3 {{ margin: 5mm 0 2mm; color: #1c4560; font-size: 11pt; }}
p {{ margin: 0 0 3.2mm; }} .eyebrow {{ margin-bottom: 2mm; color: #9a7133; font-size: 7.5pt; font-weight: 700; letter-spacing: .16em; text-transform: uppercase; }}
.section + .section {{ page-break-before: always; }} .section-intro {{ color: #52647a; font-size: 10pt; }}
.callout {{ margin: 4mm 0; padding: 4mm 5mm; border-left: 3px solid #bd9b5d; background: #f3f6f8; }} .callout strong {{ color: #133650; }}
.callout.warn {{ border-left-color: #bd7658; background: #fbf3ee; }}
.kpis {{ display: grid; grid-template-columns: repeat(4,1fr); gap: 3mm; margin: 5mm 0; }}
.kpi {{ min-height: 22mm; padding: 3.5mm; background: #f0f4f6; border-top: 2px solid #557f92; }} .kpi strong {{ display:block; color:#14324b; font-size:18pt; line-height:1.05; }} .kpi span {{ display:block; margin-top:2mm; color:#65778a; font-size:7.2pt; }}
ol.toc {{ margin: 3mm 0 6mm; padding-left: 7mm; columns: 2; column-gap: 14mm; }} ol.toc li {{ display:flex; justify-content:space-between; gap:3mm; padding:0 1mm 1mm 0; margin:0 0 2.4mm; border-bottom:.4pt solid #e0e6ea; break-inside:avoid; }} ol.toc li span:last-child {{ color:#9a7133; font-weight:700; white-space:nowrap; }}
table {{ width:100%; border-collapse:collapse; margin:3mm 0 4mm; table-layout:fixed; font-size:8pt; line-height:1.23; }}
thead {{ display: table-header-group; }} tr {{ break-inside:avoid; page-break-inside:avoid; }} th {{ padding:2.2mm 1.6mm; color:#fff; background:#193e56; text-align:left; font-size:7.4pt; font-weight:700; vertical-align:bottom; }}
td {{ padding:1.9mm 1.6mm; border-bottom:.5pt solid #dbe2e8; vertical-align:top; overflow-wrap:anywhere; }} tbody tr:nth-child(even) {{ background:#f5f7f8; }} .tight {{ font-size:7.8pt; }} .rank-table {{ font-size:7.7pt; }} .support-table {{ font-size:7.3pt; }}
.note {{ color:#607187; font-size:7.7pt; }} .source-note {{ margin-top:2mm; color:#63758a; font-size:7.4pt; }} .compact-heading {{ margin-top:3mm; font-size:9pt; }}
.coverage-chart {{ margin:4mm 0 5mm; padding:4mm; border:1px solid #dbe3e8; }} .chart-head,.chart-row {{ display:grid; grid-template-columns:18mm 1fr 1fr; align-items:center; gap:3mm; }} .chart-head {{ margin-bottom:2mm; color:#65778a; font-size:7pt; font-weight:700; }} .chart-row {{ margin:2.5mm 0; }} .chart-row > strong {{ color:#1b435d; }} .chart-cell {{ position:relative; min-height:8mm; padding:1.5mm 2mm; background:#f1f4f6; }} .chart-cell i {{ display:block; height:2.2mm; background:#49829a; }} .chart-cell i.delivery {{ background:#bb9654; }} .bar-label {{ display:block; position:relative; z-index:1; margin-bottom:1mm; font-size:7.3pt; font-weight:700; }} .chart-note {{ margin:3mm 0 0; color:#65778a; font-size:7pt; }}
.deferred {{ display:grid; grid-template-columns:1fr 1fr; gap:3mm; margin:3mm 0; }} .deferred div {{ padding:3mm; border:1px solid #dce4e8; background:#f8fafb; }} .deferred strong {{ display:block; color:#19435c; }} .deferred span {{ display:block; margin-top:1mm; color:#62758a; font-size:7.6pt; }}
.smallcaps {{ color:#8a6a38; font-size:7pt; font-weight:700; letter-spacing:.1em; text-transform:uppercase; }}
.rank-table td {{ padding:1.5mm 1.2mm; }} .support-table {{ font-size:7.3pt; }} .support-table th {{ font-size:7pt; }}
.running-head,.running-foot {{ display:none; }}
.toc-running-head {{ position:absolute; top:-14mm; left:0; right:0; height:6mm; border-bottom:.5pt solid #bdc9d8; color:#63748a; font-size:7.5pt; letter-spacing:.08em; text-transform:uppercase; }}
.page-break {{ page-break-before:always; }} .nowrap {{ white-space:nowrap; }}
@media screen {{ body {{ max-width:210mm; margin:15mm auto; padding:17mm 16mm 18mm; box-shadow:0 2px 16px #ced5dc; }} .cover {{ margin:-17mm -16mm -18mm; }} }}
</style></head><body>
<div class="running-head">Rajasthan Royals IPL 2027 | Evidence report | Data cut-off 13 November 2026</div><div class="running-foot"><span>SupeRR Selector | Source-led analysis</span><span>Page <b class="page-number"></b></span></div>
<section class="cover"><div><div class="cover-mark">SupeRR Selector | Season 2</div><div class="cover-rule"></div><h1>Rajasthan Royals<br>IPL 2027</h1><div class="cover-subtitle">Performance Analysis &amp;<br>Auction Readiness Report</div></div><div><div class="cover-meta"><div><span>Evidence cut-off</span><strong>13 November 2026</strong></div><div><span>Report status</span><strong>Evidence report | strategy deferred</strong></div><div><span>Ranking baseline</span><strong>Phase 5G / Phase 5H audited</strong></div><div><span>Auction pool</span><strong>Not verified in local snapshot</strong></div></div><p class="cover-note">Prepared only from the project's frozen ranking artifacts, Phase 5H audits and local operator-managed availability overlay. This report does not establish RR squad needs, auction eligibility, affordability or a predicted XI.</p></div></section>

<section class="section"><div class="toc-running-head">Rajasthan Royals IPL 2027 | Evidence report | Data cut-off 13 November 2026</div><div class="eyebrow">Report guide</div><h2>Contents &amp; decision summary</h2><ol class="toc"><li>Executive summary <span>2</span></li><li>Scope, sources &amp; methodology <span>3</span></li><li>Frozen Phase 5G overall Batter Top 10 <span>4</span></li><li>IPL supporting Batter Top 10 <span>5</span></li><li>T20I supporting Batter Top 10 <span>6</span></li><li>Stability &amp; interpretation <span>7</span></li><li>Phase 5H bowling evidence <span>8</span></li><li>2027 availability audit <span>9</span></li><li>Deferred decisions &amp; limitations <span>10</span></li><li>Validation record &amp; source register <span>11</span></li></ol>
<div class="kpis"><div class="kpi"><strong>10</strong><span>frozen overall batter ranks</span></div><div class="kpi"><strong>0 / 414</strong><span>competition-ready / exploratory bowling profiles</span></div><div class="kpi"><strong>0</strong><span>registered/final-register batter targets in snapshot</span></div><div class="kpi"><strong>13 Nov</strong><span>2026 availability verification date</span></div></div>
<div class="callout"><strong>Decision status:</strong> the project supports a validated batter performance report. It does not support an actionable Rajasthan Royals auction strategy. The official 2027 RR squad, registered player pool/final register, available purse and squad requirements are not present in the verified local evidence.</div>
<p>The Phase 5G Overall Batter Top 10 is frozen and independently reproduced by Phase 5H. IPL and T20I supporting rankings are retained as separate format lists. The ranking evidence uses contextual wicket/phase cohorts; it is not verified scoreboard pressure or a measure of psychological response.</p>
<p>The local availability overlay contains 252 analyzed player-role rows: 245 unknown/unverified and 7 traded-status rows across 6 distinct player IDs. No row is verified as registered for auction or included in the final register. A trade or release is not auction registration.</p>
<div class="callout warn"><strong>Bowling:</strong> 0 competition-ready candidates and 414 exploratory profiles. No bowler Top 10 or bowling recommendation is presented.</div></section>

<section class="section"><div class="eyebrow">01 | Evidence base</div><h2>Scope, sources &amp; method</h2><p class="section-intro">The report uses validated local artifacts only. It does not recalculate rankings, change eligibility, infer missing fields or use raw data to create new analytics.</p>
<h3>Confirmed analysis coverage</h3>{chart()}{covtable}
<p class="note">The IPL scope contains five seasons (2022-2026); the T20I scope contains eight season labels across 2022-2026. The underlying confirmed-scope table reports dates through 31 May 2026 for IPL and 1 November 2026 for T20I. These are dataset coverage windows, not a claim of complete league history.</p>
<h3>Ranking method</h3><p>Phase 5C format scores are retained from their source artifacts. Phase 5G reconciles the overall list using each player's mean within-format percentile among formats where the unchanged eligibility floors are met; format scores are not pooled as raw values. Player ID is the deduplication key. Phase 5C scores already contain the existing exposure shrinkage and match-consistency adjustment.</p>
<p>The contextual cohort is defined using wicket/phase context and the stored baseline cohort. It is a contextual proxy, not verified scoreboard-pressure evidence and not evidence of a psychological effect. The IPL and T20I support lists remain separate.</p>
<div class="callout"><strong>Phase 5I audit:</strong> no Phase 5I-named artifacts were found in the inspected submission and report directories. The report uses the available Phase 5G and Phase 5H artifacts and does not claim Phase 5I validation.</div>
<p class="source-note">Sources: <code>outputs/reports/confirmed_scope_coverage_summary.csv</code>; <code>submission/phase5g_submission_reconciliation.md</code>; <code>submission/phase5h_submission_readiness.md</code>; <code>src/phase5h_final_audit.py</code>.</p></section>

<section class="section"><div class="eyebrow">02 | Frozen performance evidence</div><h2>Phase 5G Overall Batter Top 10</h2><p class="section-intro">Authoritative stored order and stored mean within-format percentile. Do not interpret this as an auction shortlist or availability list.</p>{overall_table}
<p class="note">The pressure and baseline columns report mean contextual-cohort event and match counts as stored in Phase 5G; "consistency / shrinkage" reports stored mean factors. Stability text is carried from each contributing format evidence record. The full source contains detailed per-format scores and uncertainty data.</p>
<div class="callout"><strong>Exact list check:</strong> 10 rows, ranks 1-10, 10 unique IDs. Phase 5H independently reproduced the exact rank order with maximum absolute percentile difference 0.0. Scores above retain the source CSV representation.</div>
<p class="source-note">Source: <code>submission/phase5g_overall_batter_top10.csv</code>; cross-check: <code>outputs/reports/phase5g_overall_batter_top10.csv</code>.</p></section>

<section class="section"><div class="eyebrow">03 | Format-specific supporting evidence</div><h2>IPL Batter Top 10</h2><p class="section-intro">Supporting Phase 5C IPL ranking. This is a format-specific table and is not combined with T20I scores.</p>{support_table(supporting["IPL"])}
<p class="note">Scores and interval endpoints are stored Phase 5C values at source precision. The interval is score uncertainty, not rank probability. Exposure fields count contextual and baseline cohort observations; they do not establish scoreboard pressure. "Stable top-10 candidate" is the stored stability flag.</p>
<p class="source-note">Source: <code>submission/supporting_IPL_batter_top10.csv</code>. Supplemental source: <code>outputs/reports/phase5c_batter_rankings.csv</code>.</p></section>

<section class="section"><div class="eyebrow">04 | Format-specific supporting evidence</div><h2>T20I Batter Top 10</h2><p class="section-intro">Supporting Phase 5C T20I ranking. This is a format-specific table and is not combined with IPL scores.</p>{support_table(supporting["T20I"])}
<p class="note">Scores and interval endpoints are stored Phase 5C values at source precision. The interval is score uncertainty, not rank probability. Exposure fields count contextual and baseline cohort observations; they do not establish scoreboard pressure. "Stable top-10 candidate" is the stored stability flag.</p>
<p class="source-note">Source: <code>submission/supporting_T20I_batter_top10.csv</code>. Supplemental source: <code>outputs/reports/phase5c_batter_rankings.csv</code>.</p></section>

<section class="section"><div class="eyebrow">05 | Reading the batter evidence</div><h2>Exposure, consistency &amp; stability</h2><p class="section-intro">Ranks and scores summarize the current stored evidence under the documented eligibility and scoring design. They do not indicate auction availability or franchise fit.</p>
<h3>Cross-format sensitivity checks</h3>{scenario_table}
<p>The Phase 5G reconciliation records five aggregation/duplicate scenarios. The selected mean-percentile Top 10 overlaps 9/10 with the standardized-score alternative and 9/10 with the approximate event-count lower-bound alternative. These checks support robustness to those alternatives; they do not show a uniquely correct ordering.</p>
<h3>Interpretation controls</h3><ul><li>Phase 5G overall scores are format-normalized percentiles; no raw IPL/T20I score pooling is performed.</li><li>Format-level uncertainty intervals do not combine into an overall-list confidence interval.</li><li>Match-cluster intervals are available for supporting format Top 10 evidence; event-count intervals used in one cross-format sensitivity are not cluster-robust for the complete candidate pool.</li><li>Contextual wicket/phase evidence reflects the documented proxy. It is not verified scoreboard pressure or psychological pressure.</li><li>Performance eligibility is not registration, release, affordability, role fit or a recommendation for Rajasthan Royals.</li></ul>
<p class="source-note">Source: <code>submission/phase5g_cross_format_scenarios.csv</code>; <code>submission/phase5g_cross_format_stability.csv</code>; <code>submission/phase5g_submission_reconciliation.md</code>; Phase 5H readiness audit.</p></section>

<section class="section"><div class="eyebrow">06 | Phase 5H decision</div><h2>Bowling evidence: no validated shortlist</h2><p class="section-intro">Phase 5H supports no competition-ready bowling candidates. Exploratory profiles are not ranked recommendations.</p>
<div class="kpis"><div class="kpi"><strong>0</strong><span>competition-ready bowlers</span></div><div class="kpi"><strong>414</strong><span>exploratory profiles</span></div><div class="kpi"><strong>145 / 269</strong><span>IPL / T20I exploratory profiles</span></div><div class="kpi"><strong>0</strong><span>players passing both verified-chase floors</span></div></div>
{bowling_table}
<p>Verified chase-state coverage is sparse: IPL 31/42,085 chase rows (0.074%) and T20I 261/49,849 (0.524%). Paired pressure/baseline bowling evidence is powerplay-only: IPL 18/4 events over 3 match clusters; T20I 98/89 events over 12 clusters. The evidence is too sparse for individual bowling ranking.</p>
<p>Recognized credited wicket counts use the project's dismissal allowlist and are event counts, not full scorecard totals. Ordinary-row outcomes exclude extras; ordinary batter runs are not bowler-conceded runs. Economy and conventional bowling strike rate remain blocked because attributable conceded runs and provider-validated legal-ball denominators are incomplete.</p>
<div class="callout warn"><strong>Decision:</strong> no Bowler Top 10 is created. Wicket/phase depletion is a batting-resource context and is not valid evidence of a demanding bowling situation.</div>
<p class="source-note">Sources: <code>submission/phase5h_bowling_metric_audit.csv</code>; <code>submission/phase5h_bowling_eligibility.csv</code>; <code>submission/phase5h_bowling_final_audit.md</code>; <code>outputs/reports/phase5c_bowler_rankings.csv</code>.</p></section>

<section class="section"><div class="eyebrow">07 | Local operator-managed evidence</div><h2>IPL 2027 availability audit</h2><p class="section-intro">Snapshot verified 13 November 2026. The CSV is a dated status overlay on analyzed IPL player-role profiles; it is not an official full auction pool.</p>
<div class="kpis"><div class="kpi"><strong>252</strong><span>overlay player-role rows</span></div><div class="kpi"><strong>{role_counts["batter"]}</strong><span>rows labeled batter in overlay</span></div><div class="kpi"><strong>{role_counts["bowler"]}</strong><span>rows labeled bowler in overlay</span></div><div class="kpi"><strong>0</strong><span>verified registered/final-register batter targets</span></div></div>
{status_table}
<p>All 252 rows carry the 2026-11-13 verification date. The 245 unknown rows have no player-specific publication date and point to a general IPL news index; they remain unknown/unverified. Seven trade-status role rows represent six distinct IDs and carry dated official announcement references. "Previous franchise" is historical project mapping and is not proof of a 2027 contract.</p>
<div class="callout warn"><strong>A trade or release does not establish auction availability.</strong> Only a verified official registration or final-register status can qualify a batter target. The current overlay has no such record; therefore the confirmed target count is zero.</div>
<p>The overlay is kept local and operator-managed. It was read for this report and was not changed. Its source URLs and status notes remain in the local CSV; unknown statuses are not replaced by prediction or inference.</p>
<p class="source-note">Source: local <code>data/external/ipl_2027_player_availability.csv</code>; API cross-check: <code>GET /api/v1/auction/targets</code> returned 0.</p></section>

<section class="section"><div class="eyebrow">08 | Decision boundaries</div><h2>Deferred strategy &amp; limitations</h2><p class="section-intro">This report is not an actionable auction plan. Official inputs required for those decisions are absent from the verified local snapshot.</p>
<h3>Deferred until official information is available</h3><div class="deferred"><div><strong>RR squad and retention state</strong><span>Official 2027 contracted roster, retention/release decisions, trades and replacement updates.</span></div><div><strong>Registered player pool</strong><span>Player-specific registration evidence and the final auction register.</span></div><div><strong>Auction resources and rules</strong><span>Official 2027 purse remaining, slots, squad limits and applicable auction rules. A salary cap is not an auction purse.</span></div><div><strong>Squad fit and bidding</strong><span>Verified role classifications, overseas/domestic constraints, needs, prices and affordability. No target costs or bid strategy are inferred.</span></div></div>
<p>The requested reference 2026 RR auction strategy PDF was not found in the inspected project PDF inventory. Historical 2026 squad or auction material is not substituted for 2027 facts. This report contains no price forecast, purse allocation, squad-gap heatmap, target-cost ranking or predicted XI.</p>
<h3>Known analytical limits</h3><ul><li>Performance evidence covers the confirmed project data windows only; it is not a complete history claim.</li><li>Contextual wicket/phase cohorts do not establish verified scoreboard pressure or psychological response.</li><li>Bowling outcomes have source-semantic and denominator limitations; no competition-ready candidate exists.</li><li>Availability classifications are a local snapshot, not a live feed or complete auction register.</li><li>No Phase 5I artifact was located in the inspected report/submission directories.</li><li>Player biography, age, role beyond source labels, health, demand, price, squad need and likely XI are not inferred.</li></ul></section>

<section class="section"><div class="eyebrow">09 | Reproducibility</div><h2>Validation record</h2><p class="section-intro">The PDF generator validates its source invariants before writing this report.</p>{validate_table}
<ul><li>Frozen overall ranking package and report copy match on rank, ID, name and stored score.</li><li>Overall list has exactly ranks 1-10 and ten distinct player IDs; each supporting list contains exactly ten rows in rank order and a single format.</li><li>Phase 5H independent rebuild passed: exact overall rank order, ten unique IDs, maximum score difference 0.0.</li><li>All 414 Phase 5C bowler rows are exploratory; all eight metric-format eligibility rows report zero players meeting both floors.</li><li>Availability overlay is 252 rows, all verified 2026-11-13; observed statuses and registration gate were validated before report creation.</li><li>No ranking, eligibility, raw dataset or availability overlay was written by the report generator.</li></ul>
<h3>Source register</h3>{source_table}
<p class="smallcaps">Report version 1.0 | Evidence cut-off 13 November 2026</p>
<p class="source-note">Generation source: <code>scripts/generate_ipl_2027_report.py</code>. PDF rendering: <code>scripts/render_ipl_2027_report.mjs</code>. Editable report source: this HTML file.</p></section>
</body></html>'''
    return html_doc


def main() -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    data = validate_sources()
    HTML_OUT.write_text(build_html(data), encoding="utf-8")
    renderer = ROOT / "scripts" / "render_ipl_2027_report.mjs"
    result = subprocess.run(["node", str(renderer), str(HTML_OUT), str(PDF_OUT)], cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
    payload = PDF_OUT.read_bytes()
    if not payload.startswith(b"%PDF-") or len(payload) < 20_000:
        raise RuntimeError("Generated PDF failed basic file validation")
    pages = len(re.findall(rb"/Type\s*/Page\b", payload))
    if pages < 8:
        raise RuntimeError(f"Expected a complete multi-page report; found {pages} pages")
    print(f"Editable source: {HTML_OUT}")
    print(f"PDF: {PDF_OUT}")
    print(f"Bytes: {len(payload):,}; page objects: {pages}")
    print("Source checks passed: Phase 5G parity; Phase 5H 0/414; availability 252 rows, 2026-11-13, 0 registered/final-register targets.")


if __name__ == "__main__":
    main()
