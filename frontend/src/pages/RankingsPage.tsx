import { useState } from "react";
import { useApi } from "../api/client";
import type { ApiEnvelope } from "../api/types";
import { DataSource, EmptyPanel, ErrorPanel, PageIntro, Panel } from "../components/ui";
import { PlayerEvidenceCard, type PlayerEvidenceRow } from "../components/PlayerEvidenceCard";

type RankingView = "overall" | "IPL" | "T20I";

export default function RankingsPage() {
  const [view, setView] = useState<RankingView>("overall");
  const path = view === "overall" ? "/rankings/batters/overall" : `/rankings/batters/supporting?format=${view}`;
  const { data, loading, error, reload } = useApi<ApiEnvelope<PlayerEvidenceRow>>(path);
  const rows = data?.records ?? [];
  const overall = view === "overall";

  return (
    <div>
      <PageIntro eyebrow="Validated performance evidence" title="Batter Rankings" description="Review the frozen overall Phase 5G Top 10 and the separate IPL and T20I supporting lists. Player order and scores come directly from the project artifacts." aside={<DataSource>{data?.source ?? "Authoritative ranking artifact"}</DataSource>} />
      <Panel title={overall ? "Overall Batter Top 10" : `${view} supporting Top 10`} description={overall ? "The overall score is the stored mean within-format percentile. It is not recalculated or sorted in the frontend." : "Format-specific Phase 5C stored score and order. These lists remain separate and are not combined."}>
        <div className="ranking-filter-row" role="group" aria-label="Ranking format filter">
          {(["overall", "IPL", "T20I"] as const).map((option) => <button key={option} type="button" className={`ranking-filter ${view === option ? "ranking-filter-active" : ""}`} aria-pressed={view === option} onClick={() => setView(option)}>{option === "overall" ? "Overall Top 10" : `${option} evidence`}</button>)}
        </div>
        {loading ? <div className="player-card-grid">{Array.from({ length: 6 }, (_, index) => <div className="player-card-skeleton" key={index}><span /><i /><i /></div>)}</div> : null}
        {error ? <ErrorPanel message={error.message} onRetry={reload} /> : null}
        {data && rows.length ? <div className="player-card-grid">{rows.map((row) => <PlayerEvidenceCard key={row.player_id} row={row} score={overall ? row.mean_within_format_percentile : row.score} scoreLabel={overall ? "Mean within-format percentile" : "Stored Phase 5C score"} formatLabel={overall ? (typeof row.formats === "string" ? row.formats : "Overall") : view} />)}</div> : null}
        {data && !rows.length ? <EmptyPanel title="No ranking records returned">The selected artifact returned no records. No substitute or client-generated ranking is shown.</EmptyPanel> : null}
      </Panel>
      <div className="notice notice-blue">Pressure and baseline event counts describe the documented contextual wicket/phase proxy. They are not verified scoreboard-pressure or psychological-pressure measurements. Exposure shrinkage, consistency adjustment, and stability are displayed only where the source artifact contains them.</div>
    </div>
  );
}
