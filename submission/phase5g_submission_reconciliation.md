# Phase 5G competition submission reconciliation

## Exact official deliverables

The supplied Round 1 problem statement PDF (`data/raw/Round 1 Problem Statement _ SupeRR Selector Season 2.docx.pdf`) explicitly requires **two** ordered Top 10 lists: one batter list (ranks 1–10) and one bowler list (ranks 1–10), selected through separate Unstop dropdown fields, plus a methodology-report upload. The batter list is one overall role list, not a separate official list for each format. The source PDF prohibits repeating a player within the same role list. The IPL and T20I Phase 5F rankings remain format-specific supporting evidence.

The supplied data support a single overall batter list when candidates are compared by within-format standing rather than incompatible raw score values. The resulting cross-format order is an explicit aggregation of the independently validated format-level evidence, not a claim that IPL and T20I performances are identical.

## Cross-format candidate and score audit

Within each format, Phase 5C scores are already standardized against that format's eligible evidence pool and include harmonic exposure shrinkage `n_eff/(n_eff+20)` plus the match-consistency discount. The pools contain 107 IPL and 198 T20I competition-ready player-format candidates. 60 player IDs meet the unchanged floors in both formats; 185 qualify in only one. Consequently, any single combined list must choose how to handle candidates with one versus two format observations, and the conditions/eligible pools are not exchangeable competitions.

We compared five diagnostics: mean within-format percentile; mean within-format standardized score; mean percentile of Phase 5C approximate event-count 95% lower scores; maximum percentile across eligible formats (an optimistic duplicate rule); and mean percentile restricted to candidates eligible in both formats. Percentile and standardized transforms avoid comparing raw format score magnitudes. Exposure and consistency are already reflected in base score; the lower-bound sensitivity adds a conservative uncertainty adjustment but relies on Phase 5C's non-cluster event-count interval for the complete candidate pool. Match-cluster intervals exist for each format's baseline Top 10 only, so there is no like-for-like cluster interval for all cross-format candidates.

### Official overall batter Top 10

The selected list uses each player's **mean percentile among formats in which that player independently passes the unchanged competition-ready floors**. The player ID is the deduplication key. This averages repeated entries (rather than counting a dual-format player twice) and does not penalize a player for a format in which they have no qualifying evidence. Phase 5C scores already include format-specific exposure shrinkage and match-consistency adjustment before percentile conversion. Full per-format ranks, scores, exposure and uncertainty are retained in the CSV's `format_evidence_json` column.

| rank | batter | mean within-format percentile | eligible format(s) | standardized rank sensitivity | conservative lower-bound rank sensitivity | max-percentile rank sensitivity |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Chad Bowes | 1.0 | T20I | 2 | 1 | 1 |
| 2 | Priyansh Arya | 1.0 | IPL | 1 | 2 | 2 |
| 3 | Mehidy Hasan Miraz | 0.9949494949494949 | T20I | 3 | 3 | 3 |
| 4 | Alick Athanaze | 0.9848484848484849 | T20I | 4 | 4 | 6 |
| 5 | Aryansh Sharma | 0.9747474747474747 | T20I | 7 | 7 | 9 |
| 6 | Ajinkya Rahane | 0.9719626168224299 | IPL | 5 | 5 | 10 |
| 7 | Yashasvi Jaiswal | 0.9712074011139431 | IPL;T20I | 9 | 8 | 8 |
| 8 | Innocent Kaia | 0.9646464646464646 | T20I | 10 | 10 | 12 |
| 9 | William Jacks | 0.9628764278296988 | IPL;T20I | 6 | 6 | 7 |
| 10 | Jason Smith | 0.9595959595959596 | T20I | 11 | 11 | 13 |

The separate IPL and T20I Top 10 tables in Phase 5F are retained as detailed supporting evidence; the aggregate list's `format_evidence_json` records each contributing format row and uncertainty field.

### Cross-format aggregation scenarios

These are diagnostics only, not a submission list:

| scenario | candidate_pool | top10_distinct_players | top10_names | score_adjustments |
| --- | --- | --- | --- | --- |
| mean within-format percentile; deduplicate by player ID | 245 | 10 | Chad Bowes; Priyansh Arya; Mehidy Hasan Miraz; Alick Athanaze; Aryansh Sharma; Ajinkya Rahane; Yashasvi Jaiswal; Innocent Kaia; William Jacks; Jason Smith | Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount |
| mean within-format standardized score; deduplicate by player ID | 245 | 10 | Priyansh Arya; Chad Bowes; Mehidy Hasan Miraz; Alick Athanaze; Ajinkya Rahane; William Jacks; Aryansh Sharma; Jake McGurk; Yashasvi Jaiswal; Innocent Kaia | Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount |
| mean percentile of approximate event-count 95% lower bound | 245 | 10 | Chad Bowes; Priyansh Arya; Mehidy Hasan Miraz; Alick Athanaze; Ajinkya Rahane; William Jacks; Aryansh Sharma; Yashasvi Jaiswal; Muhammad Waseem; Innocent Kaia | Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount; lower bound uses event-count normal interval, not cluster bootstrap |
| best available format percentile (max; optimistic duplicate rule) | 245 | 10 | Chad Bowes; Priyansh Arya; Mehidy Hasan Miraz; Jake McGurk; Rishabh Pant; Alick Athanaze; William Jacks; Yashasvi Jaiswal; Aryansh Sharma; Ajinkya Rahane | Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount |
| mean percentile among candidates independently eligible in both formats | 60 | 10 | Yashasvi Jaiswal; William Jacks; Jake McGurk; Moeen Ali; Vaibhav Sooryavanshi; Abhishek Sharma; Travis Head; Phil Salt; Jitesh Sharma; Rahmanullah Gurbaz | Phase 5C score already includes harmonic exposure shrinkage and match-consistency discount |

### Ranking stability and overlap

Overlap is against the mean-percentile diagnostic Top 10; Spearman correlation is computed on candidates shared by each scenario pool. Scenario differences reflect legitimate yet arbitrary choices of scale, uncertainty and duplicate policy.

| scenario | top10_overlap_with_mean_percentile | spearman_rank_correlation_on_common_candidates |
| --- | --- | --- |
| mean within-format percentile; deduplicate by player ID | 10 | 1.0 |
| mean within-format standardized score; deduplicate by player ID | 9 | 0.9932598389215743 |
| mean percentile of approximate event-count 95% lower bound | 9 | 0.9837346693975473 |
| best available format percentile (max; optimistic duplicate rule) | 8 | 0.9522672563627612 |
| mean percentile among candidates independently eligible in both formats | 2 | 1.0 |

The two Phase 5F format-specific Top 10s contain 10 IPL rows and 10 T20I rows. The union contains 19 distinct player IDs, meaning a player appears in both lists; this is allowed because duplicates are barred only within each role list. A hypothetical one-list cross-format output would have to deduplicate, changing its membership/order under average, max or both-formats-only rules. The overlapping candidate does not justify selecting a duplicate or merging list ranks.

## Batter submission decision

The official single batter list is `phase5g_overall_batter_top10.csv`. The chosen mean-percentile aggregation is supported as a transparent, format-normalized decision: its candidate set does not compare raw format scores, it carries forward exposure/consistency shrinkage, and its Top 10 retains 9/10 candidates under both a within-format standardized-score alternative and an event-uncertainty lower-bound alternative. This stability is useful but not proof of a uniquely correct cross-format ordering. The lower-bound sensitivity uses Phase 5C event-count intervals for the full pool, not cluster-robust intervals. The overall list has no combined-format bootstrap CI; format-level intervals remain alongside source evidence.

Mean percentile and mean standardized score orderings have Spearman correlation 0.9933 on their common candidate pool. The uncertainty-adjusted lower-bound percentile Top 10 overlaps 9/10. The optimistic maximum-percentile duplicate rule overlaps 8/10 and is rejected because it lets one exceptional format dominate; requiring eligibility in both formats leaves only 60 candidates and overlaps just 2/10 with the main list, so it is rejected as a format-participation filter. A player appears in both Phase 5F format Top 10s; the player-ID aggregation correctly places that player only once in the official overall list.

## Bowling deliverable reconciliation

The official PDF requires a separate ordered Top 10 bowler list (ranks 1–10) in its own Unstop dropdown, in addition to the batter list. The supplied data support no competition-ready bowlers: Phase 5C/5E report 0 ready and 414 exploratory player-format profiles. Verified chase containment demand, RRR > CRR compared with RRR <= CRR within match and phase, remains the most role-relevant available pressure definition, but pressure/baseline exposure is only IPL 18/4 events across 3 match clusters and T20I 98/89 across 12 clusters; none meet the unchanged bowling floors. Wicket-depletion alone is rejected for bowlers because it can ease the bowling task.

No defensible Top 10 can be selected. If Unstop enforces the required field, the analysis cannot complete an honest submission under current evidence. Leave it unresolved and seek organizer guidance or validated missing bowling/context data; do not enter names from the 414 exploratory pool. See `phase5g_bowling_submission_decision.md`.

## Reproducibility and boundaries

All calculations use the supplied Phase 5C, 5D and 5F output tables; raw data are not modified. `phase5g_overall_batter_top10.csv` retains format ranks, standardized rank/percentile sensitivities, event and match exposure, exposure/consistency factors, cluster intervals where available, and per-format source evidence. The separate Phase 5F tables remain traceable. The scenario and stability CSVs document aggregation choices and overlap.
