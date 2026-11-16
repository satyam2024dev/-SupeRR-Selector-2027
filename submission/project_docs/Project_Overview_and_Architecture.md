# Project Overview and Architecture

## Overview

SupeRR Selector Season 2 is an evidence-led cricket scouting and analytics project for IPL and T20I performance evidence. The SupeRR Selector 2027 interface presents validated rankings, player discovery and comparison, bowling evidence limits, methodology, and a dated auction-availability view. The final Rajasthan Royals report is an evidence and methodology report, not an auction plan.

Software development and evidence-reporting scope is complete. Actionable IPL 2027 auction strategy remains pending official squad and retention information, the registration/final player list, and purse and squad-resource information.

## Architecture

- **React + TypeScript frontend (`frontend/`)**: Vite application with seven routed sections, responsive navigation, tables, cards, and visualizations. The UI presents API-served artifacts and does not calculate or reorder rankings.
- **FastAPI adapter (`api/`)**: local read-only `GET` endpoints over validated project artifacts. It binds to `127.0.0.1:8000`; CORS is limited to local Vite origins.
- **Analytics and evidence (`src/`, `outputs/`, `submission/`)**: Python analysis and frozen reports/tables remain separate from the presentation layer. Scores, rank order, eligibility, and source classifications are not recomputed by the React UI.
- **Streamlit dashboard (`dashboard/`)**: existing analytics dashboard remains available as a separate entry point.
- **Data**: source and local governed inputs support the analysis. Proprietary raw data and the operator-managed auction overlay are not part of this submission package.

## Application sections

1. Overview
2. Batter Rankings
3. Player Discovery
4. Player Comparison
5. Bowling Intelligence
6. RR Auction Targets
7. Methodology

Bowling evidence is **0 competition-ready / 414 exploratory**. No Bowler Top 10 is supported. Exploratory profiles must not be presented as competition-ready. The batter contextual wicket/phase construct is a proxy and does not establish verified scoreboard or psychological pressure.

## Evidence and auction boundary

The report preserves frozen performance artifacts and separately describes the dated local availability snapshot. A trade, historical franchise mapping, or performance rank does not establish 2027 auction registration or availability. Official 2027 squad/retention details, auction registration/final list, purse, and squad resources are required before an actionable auction strategy can be prepared.

See `../qa/final_project_completion_report.md` and `../qa/final_application_audit.md` for recorded scope and audit results.
