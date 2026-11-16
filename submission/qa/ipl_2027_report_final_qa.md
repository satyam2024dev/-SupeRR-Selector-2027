# Rajasthan Royals IPL 2027 Report - Final QA

Audit date: 14 November 2026  
Project: `D:\ipl\SUPERR_SELECTOR_2027`  
Result: **PASS WITH WARNINGS**

## Summary

The regenerated PDF is suitable for submission as an evidence and methodology report. It is not an actionable auction strategy: the official 2027 RR squad, registered/final auction pool, purse and squad requirements are absent from the verified project snapshot. No Phase 5I-named artifact was found in the inspected `submission/` or `outputs/reports/` directories; the report states this directly.

The audit found two presentation defects and corrected them in the report generator:

1. Supplementary consistency, shrinkage and leave-one-out values wrapped mid-number in the IPL and T20I supporting tables. Those auxiliary values now display to three decimals. Stored ranking scores and confidence interval endpoints retain source precision.
2. The PDF renderer omitted its running header on the contents/summary page. A page-specific header fallback was added; the regenerated page now carries the same report title and cut-off header as the other pages.

No ranking logic, eligibility rule, analytics, source dataset, availability overlay, React UI, FastAPI API or Streamlit application was modified.

## Page-by-page visual review

All 11 pages were rendered from the generated PDF itself with the local Windows `Windows.Data.Pdf` renderer to individual PNG images at 992 x 1403 pixels and inspected (these are not HTML screenshots). Page numbering, margins, running headers/footers, typography, table alignment and page breaks were checked. The review images are retained at `temp_test/rendered_pdf_pages/page-01.png` through `page-11.png`.

| Page | Content | Review result |
|---:|---|---|
| 1 | Cover | Title, subtitle, cut-off and status are clear. Consistent margins; no clipping or overlap. |
| 2 | Contents and executive summary | Page references 2-11 are correct. Running header is present after the fix. Summary safeguards are legible. |
| 3 | Scope, chart and methodology | Match/delivery chart labels and coverage table align. Method caveats and source notes fit. |
| 4 | Phase 5G Overall Batter Top 10 | Ten rows are legible and in source order. IDs, stored scores, formats and evidence columns fit without clipping. |
| 5 | IPL supporting Batter Top 10 | Ten stored rows and intervals are present. Auxiliary stability fields now fit at three decimals; no score rounding. |
| 6 | T20I supporting Batter Top 10 | Ten stored rows and intervals are present. Auxiliary stability fields now fit at three decimals; no score rounding. |
| 7 | Exposure, consistency and stability | Scenario table is aligned. Contextual-proxy and uncertainty limits are visible. |
| 8 | Bowling evidence | The 0 / 414 status, denominators, blocked metrics and no-ranking decision are prominent and readable. |
| 9 | Availability audit | Status counts, date, trade/registration distinction and zero confirmed targets are readable. |
| 10 | Deferred strategy and limitations | Missing official inputs and deferred decisions are explicit; no invented strategy content appears. |
| 11 | Validation and source register | Validation facts and source references fit; footer and page number are present. |

Pages 2, 4, 7, 9 and 10 have visible lower-page whitespace because their content is shorter than the page. These are not blank pages; each contains its complete section and footer. No overlap, clipped table, awkward split, unreadable text or blank page was found after the corrections.

## Ranking reconciliation

- `submission/phase5g_overall_batter_top10.csv` and its report copy match on rank, player ID, name and stored mean within-format percentile for all 10 rows.
- Both supporting lists contain ranks 1-10 and remain separate by format. Each IPL and T20I row matches the Phase 5C source on rank, ID, name and stored score.
- All 30 ranking rows were checked in the extracted PDF text against their source CSVs for rank, player ID, player name and exact stored score. No score was rounded or recomputed.
- Phase 5H verification reproduced the overall order: 305 eligible player-format rows, 10 unique IDs, exact rank order, maximum absolute percentile difference 0.0.
- Phase 5G reconciliation scenarios and overlap counts are read from the stored scenario/stability artifacts.

## Bowling evidence verification

- Phase 5H status remains **0 competition-ready candidates / 414 exploratory profiles** (145 IPL and 269 T20I).
- All eight metric-format eligibility rows show zero players meeting both existing verified-chase floors.
- No Bowler Top 10 or bowling recommendation is included.
- Economy and conventional bowling strike rate remain blocked. The report describes credited wickets as event counts and does not treat wicket/phase context as validated bowling pressure evidence.
- Verified chase coverage and paired exposure counts are drawn from the Phase 5H audit artifacts; sparse coverage and the powerplay-only paired evidence limitation are stated.

## Auction availability verification

- The local overlay has 252 rows, all verified 13 November 2026: 107 rows labeled batter and 145 labeled bowler.
- Status counts are 245 `unknown_unverified` and 7 `traded_to_other_franchise` role rows across 6 distinct player IDs.
- There are no registered or final-register rows; API target-gate cross-check returned zero.
- Unknown records remain unknown. A trade or release is not presented as auction availability. The overlay was not modified; its SHA-256 remains `b705925a1595e8358e324aedf8eec5ec033f0a7f80dfeb66efa9974127c03109`.

## Regeneration and validation

Run from the project root with the existing project virtual environment, Node, Edge and installed `frontend/node_modules`:

```powershell
.\venv\Scripts\python.exe scripts\generate_ipl_2027_report.py
```

The generator validates source invariants, writes the editable HTML, and invokes the renderer. The renderer was also run separately:

```powershell
node scripts\render_ipl_2027_report.mjs outputs\reports\rajasthan_royals_ipl_2027_performance_auction_readiness.html outputs\reports\rajasthan_royals_ipl_2027_performance_auction_readiness.pdf
```

Both commands completed successfully. Final checks found:

- **11 PDF pages**, with page objects and extracted pages both numbering 11.
- All pages contain text, have page numbers 1-11, and rendered to nonblank full-page PNGs.
- PDF text extraction found no replacement glyphs and confirmed all required report sections.
- All 30 ranking rows match source ranks, IDs, names and exact scores in extracted PDF text.
- The report generator's Phase 5G, Phase 5H and availability source checks passed.
- The frozen Phase 5G CSV SHA-256 remains `c4be291e1eeb456984f1299132aa257449b2e9075b2abe75e8d62a7b7f74a630`.

## Project safety and remaining limitations

The report contains approved derived ranking/evidence summaries and overlay status counts, not raw ball-by-ball data. A scan of the generated HTML found no raw-data file references, credentials, environment-variable values or user-profile paths. The renderer reads `EDGE_PATH` only to locate a local browser executable; no environment value is written to the report. No files were staged or committed; the project directory has no `.git` metadata. `.gitignore` and overlay rules were not changed.

Phase 5I artifacts remain absent. The availability snapshot is dated and operator-managed, not a live feed or complete auction register. Because official 2027 retention/release, RR squad, registration/final register and auction resource information are missing, the report is ready as an evidence report but not as a final auction strategy.

## Final output paths

- PDF: `outputs/reports/rajasthan_royals_ipl_2027_performance_auction_readiness.pdf`
- Editable HTML: `outputs/reports/rajasthan_royals_ipl_2027_performance_auction_readiness.html`
- Generator: `scripts/generate_ipl_2027_report.py`
- Renderer: `scripts/render_ipl_2027_report.mjs`
