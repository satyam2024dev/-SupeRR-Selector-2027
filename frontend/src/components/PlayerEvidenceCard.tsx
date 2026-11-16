import { motion } from "framer-motion";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { displayValue } from "../api/types";

export type PlayerEvidenceRow = Record<string, unknown> & {
  rank: number;
  player_id: string;
  player_name: string;
  format?: string;
};

export function PlayerEvidenceCard({ row, score, scoreLabel, formatLabel, compact = false }: {
  row: PlayerEvidenceRow;
  score: unknown;
  scoreLabel: string;
  formatLabel: string;
  compact?: boolean;
}) {
  const pressureEvents = row.mean_pressure_events ?? row.pressure_events;
  const baselineEvents = row.mean_baseline_events ?? row.baseline_events;
  const pressureMatches = row.mean_pressure_matches ?? row.pressure_matches;
  const baselineMatches = row.mean_baseline_matches ?? row.baseline_matches;
  const shrinkage = row.mean_exposure_shrinkage ?? row.exposure_shrinkage_factor;
  const consistency = row.mean_consistency_factor ?? row.consistency_factor;
  const playerPath = `/discovery/${encodeURIComponent(String(row.player_id))}${row.format ? `?format=${encodeURIComponent(row.format)}` : ""}`;

  return (
    <motion.article className={`player-evidence-card ${compact ? "player-evidence-compact" : ""}`} whileHover={{ y: -3 }} transition={{ duration: 0.16 }}>
      <div className="player-card-topline">
        <span className={`player-rank-medal ${row.rank <= 3 ? "rank-medal-featured" : ""}`}>{String(row.rank).padStart(2, "0")}</span>
        <span className="player-format-tag">{formatLabel}</span>
      </div>
      <div className="player-card-identity">
        <span className="player-avatar-fallback" aria-label="Player image unavailable">{row.player_name.trim().charAt(0).toUpperCase() || "?"}</span>
        <div className="player-card-name-wrap"><h3>{row.player_name}</h3><span>Player ID <code>{row.player_id}</code></span></div>
      </div>
      <div className="player-card-score"><span>{scoreLabel}</span><strong>{typeof score === "number" ? String(score) : displayValue(score)}</strong></div>
      <div className="player-card-evidence">
        <div><span>Pressure context</span><strong>{displayValue(pressureEvents)} events / {displayValue(pressureMatches)} matches</strong></div>
        <div><span>Baseline context</span><strong>{displayValue(baselineEvents)} events / {displayValue(baselineMatches)} matches</strong></div>
        <div><span>Exposure adjustment</span><strong>{displayValue(shrinkage)}</strong></div>
        <div><span>Consistency adjustment</span><strong>{displayValue(consistency)}</strong></div>
      </div>
      {!compact && typeof row.stability_flag === "string" ? <div className="player-stability">{row.stability_flag.replaceAll("_", " ")}</div> : null}
      <Link className="player-profile-link" to={playerPath}>Open player evidence <ArrowUpRight size={14} aria-hidden="true" /></Link>
    </motion.article>
  );
}
