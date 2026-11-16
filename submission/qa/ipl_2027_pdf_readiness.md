# IPL 2027 Auction Strategy PDF — Readiness Audit

Prepared: 2026-11-14  
Evidence snapshot in the project availability overlay: 2026-11-13

## Readiness decision

**Partially ready for an evidence and methodology report; not ready for an actionable auction strategy.** The validated performance chapter and bowling limitations can be prepared from existing artifacts. A player-by-player RR auction target list, squad-fit assessment, purse allocation or price strategy cannot yet be responsibly finalized because official 2027 retention/release, RR squad, registration/final auction pool and auction resource information are not present in the project snapshot.

The requested reference 2026 Rajasthan Royals auction strategy PDF was not found in `docs/`, `submission/`, `presentation/` or the inspected local PDF inventory. The only project PDF found was the original SupeRR Selector problem statement. The final report can use the outline below, but its visual/style comparison against that reference requires the reference file.

## Verified content ready for use

### Performance evidence

- `submission/phase5g_overall_batter_top10.csv` is the frozen 10-row overall Batter Top 10. Do not alter its ranks, scores, methodology or order.
- Phase 5H independently rebuilds and validates the Phase 5G list from eligible Phase 5C evidence. This is the authoritative overall ranking verification. Format-level IPL and T20I supporting lists are separate artifacts (`submission/supporting_IPL_batter_top10.csv` and `submission/supporting_T20I_batter_top10.csv`) and must not be merged or presented as another overall list.
- Rank-level evidence supports reporting player ID, player name, rank, stored score, format coverage, observed contextual/baseline exposure, match consistency, exposure shrinkage, stability flag, and the available leave-one-match/season stability indicators, where each field exists.
- Pressure/baseline strike-rate and dot/boundary evidence are cohort-specific contextual indicators already stored in Phase 5C outputs. The report must say the validated construct uses a wicket/phase contextual proxy and does not establish verified scoreboard pressure or a psychological effect.
- Phase 5G scores are mean within-format percentile reconciliation; format scores are not pooled as raw scores. Report stored scores at their source precision and distinguish format-level uncertainty fields from any overall-list rank.

The 2026-11-13 overlay contains 252 IPL player-role records (107 batter profiles and 145 bowler profiles). Its status distribution is 245 `unknown_unverified` and 7 traded role rows across 6 distinct player IDs. All records have a verification date, but the 245 unknown rows have blank publication dates and link to a general IPL news index rather than player-specific source announcements. The traded rows include official dated announcement references. Historical franchise mapping does not establish 2027 contract status. The current snapshot contains no registered/final-register auction candidates; the API's confirmed batter-target count is zero.

### Bowling evidence

- Phase 5H decision: **0 competition-ready candidates; 414 exploratory profiles**. No ranked bowling recommendations are supported.
- Credited recognized wickets and ordinary-subset event descriptions can be reported with their denominators and explicit caveats. Ordinary rows exclude extras; ordinary batter runs are not bowler-conceded runs. Credited wickets per observed delivery row is not conventional bowling strike rate.
- Economy rate and conventional bowling strike rate are blocked. Source evidence does not provide attributable bowler-conceded runs and complete provider-validated legal-ball denominators.
- Verified chase evidence is sparse: 31/42,085 IPL chase rows and 261/49,849 T20I chase rows. Paired match/phase evidence is powerplay-only and no candidate meets both existing exposure floors. State this limitation beside every use of this evidence.
- A contextual wicket/phase proxy is a batting-resource depletion context, not valid bowling pressure evidence or a validated bowler recommendation.

### Availability and current RR context

- Use only the local, operator-managed `data/external/ipl_2027_player_availability.csv`. Snapshot verified 2026-11-13. This is an audit overlay, not an official full auction pool.
- Current rows distinguish unknown status from traded status. There are no recorded registered or final-register statuses. A release by itself would still require verified auction registration before being called an auction-pool candidate.
- The project does not provide an official 2027 RR squad/retention list, 2027 auction registration pool or final register, current available auction purse, open slots, role/overseas constraints, or official squad requirements. Do not derive RR needs from an old squad state.
- Official IPL material describes player regulations for the 2025–2027 cycle, but this is not a 2027-specific RR auction purse, retained squad, auction date or candidate register. Its 2027 total salary-cap rule must not be mislabeled as auction purse or remaining franchise budget. [IPL Governing Council: 2025–2027 player regulations](https://www.iplt20.com/news/article/ipl-governing-council-announces-tata-ipl-player-regulations-2025-27)
- The official RR site exposes a 2026 auction page and 2026 roster/auction information; those are historical context only and are not 2027 facts. [Rajasthan Royals 2026 auction page](https://www.rajasthanroyals.com/ipl-auction) [IPL 2026 retained players announcement](https://www.iplt20.com/news/article/tata-ipl-2026-player-retentions-announced)
- Current 2027 official source search found RR IPL 2027 ticket pre-registration, not a squad or auction announcement. This does not constitute player availability evidence. [RR IPL 2027 ticket pre-registration](https://www.rajasthanroyals.com/ipl-2027-tickets-pre-registration)

## Missing before actionable strategy publication

1. Official IPL/BCCI 2027 retention and release register, including player IDs/names and franchise attribution.
2. Official player auction-registration pool and final register, with publication dates and player-specific sources.
3. Current official RR contracted squad after all 2027 retentions/trades, including role, domestic/overseas status and replacement updates.
4. Officially stated 2027 auction rules, purse available to RR after retentions, squad limits and slots. Do not transplant 2026 values.
5. Final auction date, market/price data after auction, and verified player results if the report is written post-auction.
6. The user-referenced 2026 RR auction strategy PDF, if direct structural/style comparison is required.
7. Any current verified injury/availability information or role classifications if these are to be used. Do not infer from names or prior seasons.

Auction prices, projected bids, player ages, biographies, role/squad gaps, overseas slots, purse, retention decisions, demand, and expected availability must not be invented. A performance shortlist is not itself evidence that a player is registered, released, affordable, or needed by RR.

## Suitable tables and figures

- Frozen Phase 5G overall Batter Top 10 table: rank, ID, player, exact stored score, format support, pressure/baseline exposure, consistency and stability fields.
- Separate IPL and T20I supporting Top 10 tables, visibly labeled format-specific.
- Confirmed IPL/T20I coverage bar chart using stored match/delivery counts.
- Batter evidence cards or a descriptive pressure-versus-baseline plot only when directly based on stored metrics and labeled “contextual wicket/phase cohort”; include exposure counts and avoid psychological-pressure wording.
- Exposure/consistency and ranking-stability table with available fields and their source limitations.
- Bowling evidence matrix: metric, calculability, denominator, coverage, interpretation limit, and blocked/available status. Include the 0/414 safeguard prominently.
- Availability status count table split into unknown, traded, released-pending, retained, registered and final-register categories; show zero only for categories actually absent in the dated overlay.
- Source-quality and “what remains unknown” panel, with a visible as-of date.

Do not add a fictional auction purse allocation, price/value scatterplot, squad-gap heatmap, target-cost forecast, predicted XI, or player role matrix until required official inputs exist.

## Proposed report outline

1. Cover, version and data cut-off date.
2. Executive summary: what is verified, what is unknown, and whether auction decisions are possible.
3. Scope, source provenance and availability-state definitions.
4. Frozen performance evidence: Phase 5G overall Top 10 plus separate IPL/T20I support.
5. Batter evidence interpretation: exposure, consistency, uncertainty and contextual cohort limitations.
6. Auction eligibility gate: registered/final-register candidates only; unknown and unavailable statuses kept separate.
7. Bowling evidence decision: zero ready, 414 exploratory, calculable metrics and source-semantic blocks.
8. RR squad fit and resources: **defer until current official 2027 squad, rules and purse are sourced**.
9. Candidate strategy and bid planning: **defer until auction pool, squad needs and resource limits are verified**.
10. Data quality, limitations, refresh process and source register.
11. Appendix: full source-backed tables, field definitions and validation record.

## Safe local availability update procedure

The overlay is approved to remain local and operator-managed. Back it up before an intentional refresh. Add or revise rows only from official player-specific announcements, preserving source URL, publication date, verification date, confidence/status and explanation. Verify schema, unique player-role records, status values and date fields, then verify the API target gate against the official registration/final register. The module `python -m src.ipl_2027_availability` rebuilds/overwrites the local file from curated transaction records; do not run it as a routine viewing action. Never commit the ignored CSV, remove its ignore rule, or replace absent records with guesses.
