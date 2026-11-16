import type { PlayerEvidenceRow } from "../../components/PlayerEvidenceCard";

// Frozen values copied from the authoritative Phase 5G API artifact for UI contract tests.
export const overallTop10Fixture: PlayerEvidenceRow[] = [
  { rank: 1, player_id: "25534", player_name: "Chad Bowes", mean_within_format_percentile: 1, formats: "T20I" },
  { rank: 2, player_id: "25669", player_name: "Priyansh Arya", mean_within_format_percentile: 1, formats: "IPL" },
  { rank: 3, player_id: "3282", player_name: "Mehidy Hasan Miraz", mean_within_format_percentile: 0.9949494949494949, formats: "T20I" },
  { rank: 4, player_id: "6574", player_name: "Alick Athanaze", mean_within_format_percentile: 0.9848484848484849, formats: "T20I" },
  { rank: 5, player_id: "27469", player_name: "Aryansh Sharma", mean_within_format_percentile: 0.9747474747474747, formats: "T20I" },
  { rank: 6, player_id: "167", player_name: "Ajinkya Rahane", mean_within_format_percentile: 0.9719626168224299, formats: "IPL" },
  { rank: 7, player_id: "6819", player_name: "Yashasvi Jaiswal", mean_within_format_percentile: 0.9712074011139431, formats: "IPL; T20I" },
  { rank: 8, player_id: "24887", player_name: "Innocent Kaia", mean_within_format_percentile: 0.9646464646464646, formats: "T20I" },
  { rank: 9, player_id: "6272", player_name: "William Jacks", mean_within_format_percentile: 0.9628764278296988, formats: "IPL; T20I" },
  { rank: 10, player_id: "3635", player_name: "Jason Smith", mean_within_format_percentile: 0.9595959595959596, formats: "T20I" },
];
