# Phase 5G final action checklist

## Official submission fields

- [x] Confirm the supplied Round 1 PDF asks for one overall batter Top 10 list (ranks 1–10), a separate bowler Top 10 list (ranks 1–10), plus a methodology report upload.
- [x] Produce the cross-format, within-format-percentile-adjusted batter list in `phase5g_overall_batter_top10.csv`; keep the separate validated IPL and T20I rankings as supporting evidence.
- [x] Deduplicate the overall list by stable player ID; do not append the two format Top 10s as twenty entries.
- [ ] Upload the methodology report and evidence under the actual live Unstop fields; live portal labels have not been independently checked.
- [ ] Do not mark submission complete until the required bowler list is resolved.

## Cross-format comparison guardrails

- [x] Tested within-format percentiles and standardized scores; raw format score magnitudes were not directly compared.
- [x] Included exposure and consistency adjustments already encoded in Phase 5C scores; tested event-count lower-bound percentile as an uncertainty sensitivity.
- [x] Tested duplicate handling (mean percentile, optimistic maximum percentile, and both-formats-only pool) and Top 10 overlap/rank stability.
- [x] The two reasonable aggregation sensitivities each retain 9/10 players; interval limits and cross-format uncertainty are disclosed.

## Bowling action

- [x] Preserve 0 competition-ready and 414 exploratory profiles; do not lower floors or create bowler scores.
- [ ] Seek organizer clarification on how to handle the required bowler dropdown when supplied data cannot support ten defensible candidates.
- [ ] Obtain validated bowler-conceded runs, legal-ball denominators and broader verified challenge-state coverage only if authorized and available; then recompute under unchanged rules.

## Package quality

- [x] Keep the Phase 5F format-level batter table and bowler evidence separate and traceable.
- [x] Keep source data unchanged; no fabricated values or rankings.
- [x] Run the full test suite, compile checks and artifact validation before submission.
