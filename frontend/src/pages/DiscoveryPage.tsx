import { useApi } from "../api/client";
import { ApiRequestError } from "../api/client";
import { displayValue, type PlayerExposure } from "../api/types";
import { PlayerEvidenceCard, type PlayerEvidenceRow } from "../components/PlayerEvidenceCard";
import { DataSource, EmptyPanel, ErrorPanel, LoadingPanel, PageIntro, Panel } from "../components/ui";
import { ArrowLeft, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

type ProfileResponse = {
  player_id: string;
  player_name: string;
  exposure: PlayerExposure[];
  profiles: Record<string, Array<Record<string, unknown>>>;
  ranking_evidence?: { overall: PlayerEvidenceRow[]; formats: PlayerEvidenceRow[] };
  source: string;
};

function metricLabel(key: string): string {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function PlayerProfile({ playerId, format, query }: { playerId: string; format: string; query: string }) {
  const profilePath = `/players/${encodeURIComponent(playerId)}/profiles${format === "all" ? "" : `?format=${format}`}`;
  const { data, loading, error, reload } = useApi<ProfileResponse>(profilePath);
  const navigate = useNavigate();
  const backPath = `/discovery?${new URLSearchParams({ ...(format === "all" ? {} : { format }), ...(query ? { query } : {}) }).toString()}`;

  return (
    <Panel title="Player evidence profile" description="Observed exposure and stored descriptive metrics. Missing fields remain unavailable." className="profile-panel">
      <button type="button" className="button button-quiet profile-back" onClick={() => navigate(backPath)}><ArrowLeft size={14} /> Back to discovery</button>
      {loading ? <LoadingPanel label="Loading player evidence" /> : null}
      {error && error instanceof ApiRequestError && error.status === 404 ? <EmptyPanel title="No supported profile details for this player">This ID is not present in the available exposure or descriptive-profile artifacts for the selected format.</EmptyPanel> : null}
      {error && !(error instanceof ApiRequestError && error.status === 404) ? <ErrorPanel message={error.message} onRetry={reload} /> : null}
      {data ? <div className="profile-stack">
        <div className="profile-hero">
          <span className="player-avatar-fallback profile-avatar" aria-label="Player image unavailable">{String(data.player_name ?? "?").trim().charAt(0).toUpperCase() || "?"}</span>
          <div><div className="eyebrow">Analyzed player · local ID {data.player_id}</div><h2>{data.player_name}</h2><p>No biography or personal details are supplied by the project artifacts.</p></div>
          <DataSource>{data.source}</DataSource>
        </div>
        {data.ranking_evidence?.overall?.length ? <div className="profile-ranking-grid"><PlayerEvidenceCard row={data.ranking_evidence.overall[0]} score={data.ranking_evidence.overall[0].mean_within_format_percentile} scoreLabel="Overall mean within-format percentile" formatLabel="Phase 5G overall" compact />{data.ranking_evidence.formats.map((row) => <PlayerEvidenceCard key={`${row.format}-${row.player_id}`} row={row} score={row.score} scoreLabel="Stored Phase 5C score" formatLabel={`${row.format} supporting`} compact />)}</div> : null}
        <Panel title="Observed exposure" description="Counts are stored exposure records for the selected role and format; they do not imply additional eligibility." className="nested-panel">
          {data.exposure.length ? <div className="exposure-card-grid">{data.exposure.map((row, index) => <article className="exposure-card" key={`${row.role}-${row.format}-${index}`}><div className="exposure-card-head"><strong>{row.role}</strong><span className="player-format-tag">{row.format}</span></div><div className="exposure-pair"><div><span>Contextual proxy cohort</span><strong>{displayValue(row.pressure_observed_deliveries)} deliveries</strong><small>{displayValue(row.pressure_matches)} matches</small></div><div><span>Baseline cohort</span><strong>{displayValue(row.baseline_observed_deliveries)} deliveries</strong><small>{displayValue(row.baseline_matches)} matches</small></div></div><div className="exposure-card-foot">Comparison evidence sufficient: {displayValue(row.sufficient_evidence_for_future_pressure_comparison)}</div></article>)}</div> : <EmptyPanel title="Exposure summary unavailable">Ranking evidence may still be available, but this player has no matching exposure summary row.</EmptyPanel>}
        </Panel>
        <Panel title="Descriptive performance metrics" description="Values remain grouped by role, format, and source cohort; no profile metric is substituted for a ranking score." className="nested-panel">
          {Object.entries(data.profiles).some(([, records]) => records.length) ? <div className="descriptive-profile-grid">{Object.entries(data.profiles).flatMap(([role, records]) => records.map((row, index) => <section className="descriptive-profile-card" key={`${role}-${String(row.format)}-${String(row.cohort)}-${index}`}><div className="profile-record-head"><strong>{role} profile</strong><span className="player-format-tag">{String(row.format)} · {String(row.cohort)}</span></div><dl>{Object.entries(row).filter(([key]) => !["player_id", "player_name", "format", "cohort"].includes(key)).map(([key, value]) => <div key={key}><dt>{metricLabel(key)}</dt><dd>{displayValue(value)}</dd></div>)}</dl></section>))}</div> : <EmptyPanel title="No descriptive metric records">The project has no descriptive profile values for this player and format. The page does not fill gaps with inferred statistics.</EmptyPanel>}
        </Panel>
        <div className="notice notice-blue">The ranking’s wicket/phase contextual indicator is not a verified scoreboard-pressure or psychological-pressure measure. Descriptive cohorts and exposure remain separately labeled.</div>
      </div> : null}
    </Panel>
  );
}

export default function DiscoveryPage() {
  const { playerId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [format, setFormat] = useState(searchParams.get("format") ?? "all");
  const [role, setRole] = useState("batter");
  const params = new URLSearchParams({ limit: "100" });
  if (query.trim()) params.set("query", query.trim());
  if (format !== "all") params.set("format", format);
  if (role !== "all") params.set("role", role);
  const { data, loading, error, reload } = useApi<{ source: string; count: number; records: PlayerExposure[] }>(playerId ? null : `/players?${params.toString()}`);

  const updateFormat = (value: string) => {
    setFormat(value);
    setSearchParams((current) => { const next = new URLSearchParams(current); value === "all" ? next.delete("format") : next.set("format", value); return next; });
  };
  const updateQuery = (value: string) => {
    setQuery(value);
    setSearchParams((current) => { const next = new URLSearchParams(current); value.trim() ? next.set("query", value.trim()) : next.delete("query"); return next; });
  };

  return (
    <div>
      <PageIntro eyebrow="Search the analyzed player pool" title={playerId ? "Player Profile" : "Player Discovery"} description={playerId ? "View only ranking, exposure, and descriptive evidence present in project artifacts." : "Find players by name or local ID, then inspect available profile records without inferred biography or statistics."} />
      {playerId ? <PlayerProfile playerId={playerId} format={format} query={query} /> : <>
        <Panel title="Find a player" description="Search uses analyzed player exposure records. Search by name or ID; filter by format and role." action={<DataSource>{data?.source ?? "Player exposure artifact"}</DataSource>}>
          <div className="discovery-toolbar">
            <label className="field search-field" htmlFor="player-search"><span>Player name or ID</span><span className="search-input-wrap"><Search size={16} aria-hidden="true" /><input id="player-search" className="input" placeholder="e.g. player name or ID" value={query} onChange={(event) => updateQuery(event.target.value)} /></span></label>
            <div className="field"><label htmlFor="player-format">Format</label><select id="player-format" className="select" value={format} onChange={(event) => updateFormat(event.target.value)}><option value="all">All formats</option><option value="IPL">IPL</option><option value="T20I">T20I</option></select></div>
            <div className="field"><label htmlFor="player-role">Analysis role</label><select id="player-role" className="select" value={role} onChange={(event) => setRole(event.target.value)}><option value="all">All roles</option><option value="batter">Batter</option><option value="bowler">Bowler</option></select></div>
          </div>
          {loading ? <div className="player-card-grid">{Array.from({ length: 6 }, (_, index) => <div className="player-card-skeleton" key={index}><span /><i /><i /></div>)}</div> : null}
          {error ? <ErrorPanel message={error.message} onRetry={reload} /> : null}
          {data?.records.length ? <><div className="results-heading"><strong>{data.count.toLocaleString()} records</strong><span>Ordered by stored player name and format</span></div><div className="discovery-card-grid">{data.records.map((player) => <article className="discovery-player-card" key={`${player.player_id}-${player.role}-${player.format}`}><div className="player-card-topline"><span className="player-format-tag">{player.format}</span><span className="player-role-tag">{player.role}</span></div><div className="player-card-identity"><span className="player-avatar-fallback" aria-label="Player image unavailable">{player.player_name.trim().charAt(0).toUpperCase() || "?"}</span><div className="player-card-name-wrap"><h3>{player.player_name}</h3><span>Player ID <code>{player.player_id}</code></span></div></div><div className="discovery-evidence-pair"><div><span>Contextual cohort exposure</span><strong>{displayValue(player.pressure_observed_deliveries)} deliveries · {displayValue(player.pressure_matches)} matches</strong></div><div><span>Baseline exposure</span><strong>{displayValue(player.baseline_observed_deliveries)} deliveries · {displayValue(player.baseline_matches)} matches</strong></div></div><div className="discovery-player-foot"><span>{player.sufficient_evidence_for_future_pressure_comparison ? "Comparison evidence available" : "Limited paired exposure"}</span><Link className="player-profile-link" to={`/discovery/${encodeURIComponent(player.player_id)}?${new URLSearchParams({ ...(format === "all" ? {} : { format }), ...(query ? { query } : {}) }).toString()}`}>View evidence <span aria-hidden="true">↗</span></Link></div></article>)}</div></> : null}
          {data && !data.records.length ? <EmptyPanel title="No players match this search">Try a different name, ID, role, or format. The search does not add unmatched players.</EmptyPanel> : null}
        </Panel>
        <div className="notice notice-blue">Exposure cohorts are contextual wicket/phase groupings. They do not establish verified scoreboard pressure or a psychological effect. A missing profile photo is represented by an initial, not a generated likeness.</div>
      </>}
    </div>
  );
}
