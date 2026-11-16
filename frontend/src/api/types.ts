export type ApiEnvelope<T> = {
  source?: string;
  count: number;
  records: T[];
};

export type OverviewData = {
  formats: Array<{ format: string; matches: number; deliveries: number; seasons: string }>;
  matches_analyzed: number;
  deliveries_analyzed: number;
  eligible_batter_player_format_rows: number;
  eligible_batter_distinct_players?: number | null;
  overall_batter_top10_count: number;
  bowling: { competition_ready: number; exploratory: number };
  availability_snapshot: string | null;
};

export type OverallBatter = {
  rank: number;
  player_id: string;
  player_name: string;
  mean_within_format_percentile: number;
  formats: string;
  mean_pressure_matches: number | null;
  mean_baseline_matches: number | null;
  mean_exposure_shrinkage: number | null;
  mean_consistency_factor: number | null;
  format_evidence_json: Array<Record<string, unknown>> | string;
  limitations: string | null;
  [key: string]: unknown;
};

export type PlayerExposure = {
  player_id: string;
  player_name: string;
  role: "batter" | "bowler";
  format: "IPL" | "T20I";
  pressure_observed_deliveries: number | null;
  baseline_observed_deliveries: number | null;
  pressure_matches: number | null;
  baseline_matches: number | null;
  [key: string]: unknown;
};

export type AuctionRecord = {
  player_id: string;
  player_name: string;
  candidate_role: "batter" | "bowler";
  ipl_2027_status: string;
  confidence_status: string;
  verification_date: string;
  [key: string]: unknown;
};

export function displayValue(value: unknown, digits = 2): string {
  if (value === null || value === undefined || value === "") return "Not available";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: digits }) : "Not available";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}
