# SupeRR Selector Season 2 — Final Submission

**Project:** SupeRR Selector 2027 — Rajasthan Royals performance analysis and auction readiness

This package contains the final application and project documentation, the validated 11-page Rajasthan Royals report in PDF and editable HTML formats, all 28 responsive dashboard screenshots, and the project completion and QA records.

## Completion and decision status

Software development and evidence-reporting scope is complete. The supplied evidence supports a performance and methodology report, but it does not support an actionable IPL 2027 auction strategy yet. That strategy remains pending official 2027 squad and retention information, the official auction registration and final player list, and verified purse and squad-resource information.

Bowling evidence is **0 competition-ready / 414 exploratory**. There is no Bowler Top 10. Do not invent one or present exploratory bowling evidence as competition-ready.

The validated report and editable source are in `report/`. Documentation and launch instructions are in `project_docs/`. Completion and QA records are in `qa/`. All 28 source screenshots are in `dashboard_screenshots/`.

## Package contents

- `report/Rajasthan_Royals_IPL_2027_Performance_Auction_Readiness.pdf` — validated 11-page PDF, copied byte-for-byte from the project output.
- `report/Rajasthan_Royals_IPL_2027_Performance_Auction_Readiness.html` — editable HTML report, copied byte-for-byte from the project output.
- `dashboard_screenshots/` — all 28 responsive screenshots for seven application sections at four viewport sizes.
- `project_docs/Project_Overview_and_Architecture.md` — project structure, system architecture, scope and limitations.
- `project_docs/Analytics_Methodology.md` — consolidated analytics methodology and evidence limitations.
- `project_docs/Startup_Instructions.md` — backend, React frontend and existing Streamlit startup commands.
- `qa/` — final project completion, application audit, final PDF QA, and PDF readiness reports.
- Existing Phase 5G/5H submission evidence remains alongside these files in this directory.

## Governance and use

Performance rankings and auction availability are separate evidence inputs. The local availability overlay is operator-managed and is not an official complete auction register. No 2027 auction recommendation, player price, purse allocation, squad-fit claim or predicted XI is established by this package.

The report describes a contextual wicket/phase proxy. It does not establish psychological pressure. Preserve source labels and denominators when quoting analytical evidence. Do not include or redistribute proprietary raw data, secrets, `.env` files, caches, virtual environments or dependency directories.

## Recommended review order

1. Read this README and `project_docs/Project_Overview_and_Architecture.md`.
2. Review `report/Rajasthan_Royals_IPL_2027_Performance_Auction_Readiness.pdf` or edit its HTML counterpart.
3. Read `qa/ipl_2027_report_final_qa.md` for the documented page-by-page PDF review.
4. Review `qa/final_application_audit.md` and `qa/final_project_completion_report.md` for application scope and validation history.
5. Use `project_docs/Startup_Instructions.md` to run the applications locally.
