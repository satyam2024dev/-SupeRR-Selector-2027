import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { displayValue, type ApiEnvelope, type PlayerExposure } from "../api/types";
import { useApi } from "../api/client";
import { DataSource, EmptyPanel, ErrorPanel, LoadingPanel, PageIntro, Panel } from "../components/ui";

type EvidenceRow = Record<string, unknown>;
type ComparedPlayer = { player_id: string; player_name: string; exposure: EvidenceRow[]; profiles: { batter: EvidenceRow[]; bowler: EvidenceRow[] }; ranking_evidence: EvidenceRow[] };
type ComparisonResponse = { source: string; format: string; records: ComparedPlayer[] };

const metricFields = [
  ["observed_deliveries", "Observed deliveries"], ["ordinary_subset_balls", "Ordinary subset balls"],
  ["matches", "Matches"], ["innings", "Innings"], ["batter_runs_ordinary_subset", "Batter runs on ordinary rows"],
  ["ordinary_subset_strike_rate", "Ordinary subset strike rate"], ["ordinary_subset_dot_rate", "Ordinary subset dot rate"],
  ["boundary_events_full_eligible_scope", "Boundary events"], ["boundary_event_rate_per_observed_delivery", "Boundary events / observed delivery"],
] as const;

export default function ComparisonPage() {
  const [format, setFormat] = useState("IPL");
  const [selected, setSelected] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const params = new URLSearchParams({ format, limit: "200" });
  if (query.trim()) params.set("query", query.trim());
  const players = useApi<ApiEnvelope<PlayerExposure>>(`/players/comparison-candidates?${params.toString()}`);
  const comparePath = selected.length >= 2 ? `/players/compare?ids=${selected.map(encodeURIComponent).join(",")}&format=${format}` : "/players?limit=1";
  const comparison = useApi<ComparisonResponse>(comparePath);
  const eligiblePlayers = (players.data?.records ?? []).filter((p) => p.performance_eligible === true);
  const records = comparison.data?.records ?? [];
  const toggle = (id: string) => setSelected((current) => current.includes(id) ? current.filter((item) => item !== id) : current.length < 4 ? [...current, id] : current);
  const scoreChart = useMemo(() => records.map((player) => {
    const ranking = (player.ranking_evidence ?? []).find((row) => row.format === format);
    const score = ranking?.score ?? ranking?.rating ?? ranking?.performance_score;
    return { name: player.player_name, score: typeof score === "number" ? score : null };
  }), [records, format]);
  const chartSupported = scoreChart.length >= 2 && scoreChart.every((row) => row.score !== null);

  return (
    <div>
      <PageIntro eyebrow="Like-for-like evidence" title="Player Comparison" description="Compare eligible batter profiles within one selected format. Stored Phase 5C scores and descriptive profile evidence retain their original definitions; no composite is created." />
      <Panel className="comparison-layout" title="Select eligible batters" description="Candidates come from the stored Phase 5C competition-ready ranking rows. Search narrows the profiles; it does not change scores or eligibility." action={<DataSource>{players.data?.source ?? "Phase 5C ranking artifact"}</DataSource>}>
        <div className="toolbar">
          <div className="field"><label htmlFor="compare-format">Format</label><select id="compare-format" className="select" value={format} onChange={(event) => { setFormat(event.target.value); setSelected([]); }}><option>IPL</option><option>T20I</option></select></div>
          <div className="field search-field"><label htmlFor="compare-search">Search eligible profiles</label><input id="compare-search" className="input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Player name or ID" /></div>
        </div>
        {players.loading ? <LoadingPanel label="Loading eligible batter profiles" /> : null}
        {players.error ? <ErrorPanel message={players.error.message} onRetry={players.reload} /> : null}
        {players.data && eligiblePlayers.length ? <div className="choice-grid">{eligiblePlayers.map((player) => { const hasExposure = player.pressure_matches !== null && player.pressure_matches !== undefined || player.baseline_matches !== null && player.baseline_matches !== undefined; return <label className={`player-choice ${selected.includes(player.player_id) ? "player-choice-selected" : ""}`} key={player.player_id}><input type="checkbox" checked={selected.includes(player.player_id)} onChange={() => toggle(player.player_id)} /><span><strong>{player.player_name}</strong><small>{`ID ${player.player_id} · ${hasExposure ? `${displayValue(player.pressure_matches)} pressure / ${displayValue(player.baseline_matches)} baseline matches` : "Exposure profile unavailable"}`}</small></span><Link className="compare-profile-link" to={`/discovery/${player.player_id}?format=${format}`} onClick={(event) => event.stopPropagation()}>Profile</Link></label>; })}</div> : null}
        {players.data && !eligiblePlayers.length ? <EmptyPanel title="No eligible profiles match this search">The selected format has no profiles with the required stored comparison-evidence flag.</EmptyPanel> : null}
        <div className="selection-note">Select 2–4 profiles · {selected.length} selected.</div>
      </Panel>
      {selected.length >= 2 ? <Panel title="Side-by-side evidence" description="Pressure and baseline profile rows remain separate; like cohorts are compared only within the selected format." action={<DataSource>{comparison.data?.source ?? "Comparison endpoint"}</DataSource>}>
        {comparison.loading ? <LoadingPanel label="Loading stored comparison evidence" /> : null}
        {comparison.error ? <ErrorPanel message={comparison.error.message} onRetry={comparison.reload} /> : null}
        {!comparison.loading && comparison.data && records.length ? <>
          <div className="comparison-player-grid">{records.map((player) => {
            const profileRows = (player.profiles?.batter ?? []).filter((row) => row.format === format);
            const exposure = (player.exposure ?? []).find((row) => row.format === format);
            const ranking = (player.ranking_evidence ?? []).find((row) => row.format === format);
            const contextEvidence = (cohort: string) => cohort === "pressure" ? {
              events: ranking?.pressure_metric_events, matches: ranking?.pressure_matches, runs: ranking?.pressure_batter_runs,
              strikeRate: ranking?.pressure_sr, dotRate: ranking?.pressure_dot_rate, boundaryRate: ranking?.pressure_boundary_rate,
            } : {
              events: ranking?.baseline_metric_events, matches: ranking?.baseline_matches, runs: ranking?.baseline_batter_runs,
              strikeRate: ranking?.baseline_sr, dotRate: ranking?.baseline_dot_rate, boundaryRate: ranking?.baseline_boundary_rate,
            };
            return <article className="comparison-player-card" key={player.player_id}><div className="comparison-player-head"><div><span>PLAYER ID {player.player_id}</span><h3>{player.player_name}</h3></div><Link to={`/discovery/${player.player_id}?format=${format}`}>Open profile</Link></div><div className="comparison-score"><span>Stored {format} score</span><strong>{displayValue(ranking?.score ?? ranking?.rating ?? ranking?.performance_score, 4)}</strong><small>Phase 5C eligible ranking artifact · {ranking ? `rank ${displayValue(ranking.rank)}` : "no score available"}</small></div><div className="comparison-exposure"><span>Exposure</span>{exposure ? <><strong>{displayValue(exposure.pressure_observed_deliveries)} pressure deliveries / {displayValue(exposure.pressure_matches)} matches</strong><strong>{displayValue(exposure.baseline_observed_deliveries)} baseline deliveries / {displayValue(exposure.baseline_matches)} matches</strong></> : <><strong>{displayValue(ranking?.pressure_events)} pressure cohort events / {displayValue(ranking?.pressure_matches)} matches</strong><strong>{displayValue(ranking?.baseline_events)} baseline cohort events / {displayValue(ranking?.baseline_matches)} matches</strong></>}</div><div className="comparison-cohorts">{["pressure", "baseline"].map((cohort) => { const row = profileRows.find((profile) => profile.cohort === cohort); const context = contextEvidence(cohort); return <div className="comparison-cohort" key={cohort}><div className="comparison-cohort-head"><strong>{cohort} contextual cohort</strong><span>{row ? `${displayValue(row.observed_deliveries)} profile rows` : `${displayValue(context.events)} metric events · ${displayValue(context.matches)} matches`}</span></div>{row ? metricFields.filter(([field]) => row[field] !== null && row[field] !== undefined).map(([field, label]) => <div className="comparison-value-row" key={field}><span>{label}</span><strong>{displayValue(row[field])}</strong></div>) : <><div className="comparison-value-row"><span>Batter runs in cohort</span><strong>{displayValue(context.runs)}</strong></div><div className="comparison-value-row"><span>Ordinary subset strike rate</span><strong>{displayValue(context.strikeRate)}</strong></div><div className="comparison-value-row"><span>Ordinary subset dot rate</span><strong>{displayValue(context.dotRate)}</strong></div><div className="comparison-value-row"><span>Ordinary boundary-event rate</span><strong>{displayValue(context.boundaryRate)}</strong></div><small>Stored Phase 5C context values; profile detail unavailable.</small></>}</div>; })}</div><p className="comparison-disclaimer">The stored metric definition is <strong>{displayValue(ranking?.pressure_definition)}</strong>. This wicket/phase contextual cohort is not verified scoreboard or psychological pressure.</p></article>;
          })}</div>
          {chartSupported ? <div className="comparison-score-chart"><h3>Stored {format} score comparison</h3><p>Same-format values are read directly from Phase 5C; this chart does not recalculate ranking.</p><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={scoreChart} layout="vertical" margin={{ left: 8, right: 24 }}><CartesianGrid strokeDasharray="3 3" stroke="#dce3ec" horizontal={false} /><XAxis type="number" stroke="#52657a" fontSize={14} /><YAxis type="category" dataKey="name" width={125} stroke="#52657a" fontSize={14} /><Tooltip contentStyle={{ background: "#ffffff", color: "#142b45", border: "1px solid #dce3ec", borderRadius: 8, fontSize: 14 }} /><Bar dataKey="score" name="Stored score" fill="#e94b78" radius={[0, 5, 5, 0]} /></BarChart></ResponsiveContainer></div></div> : null}
          <p className="comparison-disclaimer">Ordinary-subset rates describe observed rows and are not complete scoreboard statistics. Contextual wicket/phase indicators are not verified psychological pressure.</p>
        </> : null}</Panel> : <EmptyPanel title="Choose at least two players">Comparison is available after selecting two to four eligible profiles from the same format.</EmptyPanel>}
    </div>
  );
}
