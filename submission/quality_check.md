# Submission CSV quality checks

All packaged CSV headers are present and unique. The overall batter list has ten distinct IDs and ranks 1–10 and is byte-identical to its Phase 5G source. Format support lists have ten unique IDs and ranks 1–10 within their format. Missing values listed below are not silently filled; blanks in scenario-rank columns mean the scenario requires eligibility in both formats, while blanks in bowling audit metrics identify blocked or non-applicable calculations.

| file | rows | columns | missing_cells | columns_with_missing | sha256 |
| --- | --- | --- | --- | --- | --- |
| final_batter_top10.csv | 20 | 32 | 0 | none | 6cb8332f5624af425d06d3ac53def268ff86fa2cf71f088158e21c66b69b0e2a |
| final_bowler_evidence.csv | 8 | 19 | 0 | none | 4e100c7758b03e3d905bf10d32c266c62cedac53665cbb15b7b2712602b9c623 |
| phase5g_cross_format_scenarios.csv | 5 | 6 | 0 | none | 7c6fa897d1787a988738d06a6d3cfd4bf8dba5f7d4fcb6adde38b5015d98a38a |
| phase5g_cross_format_stability.csv | 5 | 5 | 0 | none | a27309b6c0cae91f1a57164c6e91da90e8ca73532d4462308b690b8839263500 |
| phase5g_overall_batter_top10.csv | 10 | 19 | 8 | both_formats_only_rank:8 | c4be291e1eeb456984f1299132aa257449b2e9075b2abe75e8d62a7b7f74a630 |
| phase5h_bowling_eligibility.csv | 8 | 11 | 0 | none | e360eedbd3e614029985bfdad0a753fa82a25323304eb582f9eff6ea92b592e3 |
| phase5h_bowling_metric_audit.csv | 24 | 35 | 202 | metric_numerator_or_observed_value:10; metric_denominator:10; calculated_value_or_coverage:10; scope_row_coverage_pct:2; verified_pressure_metric_value:14; verified_baseline_metric_value:14; verified_pressure_minus_baseline:14; paired_match_cluster_count:14; match_cluster_ci95_low:14; match_cluster_ci95_high:14; contextual_proxy_numeric_floor_pass_not_role_valid:22; contextual_proxy_ordinary_floor_pass_not_role_valid:22; pressure_side_floor_pass_players:14; baseline_side_floor_pass_players:14; both_sides_floor_pass_players:14 | 05fd3a4be43d2cf7a204e020b97142c0a27daebd3119560b1548327eb984c284 |
| supporting_IPL_batter_top10.csv | 10 | 32 | 0 | none | 65174433d9485e94f99b5edbfc5de07f2a5b67e11a0385b846fc74431eb23789 |
| supporting_T20I_batter_top10.csv | 10 | 32 | 0 | none | da26812177f5e8e39d10ceba5362599f934fd6a689ed44e0ebfb32497a5717b0 |

Overall batter source SHA-256: `c4be291e1eeb456984f1299132aa257449b2e9075b2abe75e8d62a7b7f74a630`

Packaged overall batter SHA-256: `c4be291e1eeb456984f1299132aa257449b2e9075b2abe75e8d62a7b7f74a630`
