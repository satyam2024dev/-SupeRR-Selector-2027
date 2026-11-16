import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { useApi } from "../api/client";
import type { ApiEnvelope, OverallBatter, OverviewData } from "../api/types";
import { DataSource, EmptyPanel, ErrorPanel, LoadingPanel, MetricCard, PageIntro, Panel } from "../components/ui";
import { PlayerEvidenceCard } from "../components/PlayerEvidenceCard";

type AvailabilityOverview = { overlay_present: boolean; as_of: string | null; count: number; records: Array<Record<string, unknown>>; reason?: string };
type TargetOverview = { overlay_present: boolean; as_of: string | null; count: number; empty_reason?: string; reason?: string };

function CoverageChart({ rows }: { rows: OverviewData["formats"] }) {
  if (!rows.length) return <EmptyPanel title="Coverage is unavailable">No confirmed-scope rows were returned by the API.</EmptyPanel>;
  return (
    <div className="chart-wrap" role="img" aria-label="Confirmed deliveries analyzed by competition format">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 10, bottom: 0, left: -12 }}>
          <CartesianGrid stroke="#dce3ec" vertical={false} />
          <XAxis dataKey="format" tick={{ fill: "#40566d", fontSize: 14 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: "#52657a", fontSize: 13 }} axisLine={false} tickLine={false} tickFormatter={(value: number) => `${Math.round(value / 1000)}k`} />
          <Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #dce3ec", borderRadius: 8, color: "#142b45", fontSize: 14 }} formatter={(value) => [Number(value).toLocaleString(), "Delivery records"]} />
          <Bar dataKey="deliveries" fill="#168c83" radius={[5, 5, 0, 0]} maxBarSize={46} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function OverviewPage() {
  const overview = useApi<OverviewData>("/overview");
  const ranking = useApi<ApiEnvelope<OverallBatter>>("/rankings/batters/overall");
  const availability = useApi<AvailabilityOverview>("/auction/availability?role=batter");
  const targets = useApi<TargetOverview>("/auction/targets");
  return (
    <div>
      <PageIntro eyebrow="Executive workspace" title="Overview" description="A clear view of the analyzed competition scope, validated batter evidence, and current bowling readiness." />
      <section className="hero-panel">
        <div className="hero-overline">Rajasthan Royals - Auction Intelligence Platform</div>
        <h1>Build decisions on<br />evidence that holds up.</h1>
        <p>SupeRR Selector 2027 brings together verified performance artifacts and dated availability records. Ranking, eligibility, and auction status remain separate signals.</p>
        <div className="hero-meta"><span className="tag tag-pink">IPL + T20I</span><span className="tag">Validated evidence</span><span className="tag">Local data only</span></div>
      </section>
      {overview.loading ? <div className="metric-grid">{[1, 2, 3, 4].map((n) => <div className="skeleton" key={n} />)}</div> : null}
      {overview.error ? <ErrorPanel message={overview.error.message} onRetry={overview.reload} /> : null}
      {overview.data ? (
        <>
          <div className="metric-grid">
            <MetricCard label="Eligible batter profiles" value={overview.data.eligible_batter_player_format_rows.toLocaleString()} note="Eligible player-format records" accent="pink" />
            <MetricCard label="Distinct eligible batters" value={overview.data.eligible_batter_distinct_players == null ? "Not available" : overview.data.eligible_batter_distinct_players.toLocaleString()} note="Stable player IDs across IPL and T20I" accent="blue" />
            <MetricCard label="Competition-ready bowlers" value={overview.data.bowling.competition_ready.toLocaleString()} note={`${overview.data.bowling.exploratory.toLocaleString()} exploratory profiles; not recommendations`} accent="neutral" />
            <MetricCard label="Registered batter targets" value={availability.error || targets.error ? "Unavailable" : targets.loading ? "Loading" : targets.data?.overlay_present ? targets.data.count.toLocaleString() : "No overlay"} note={availability.data?.overlay_present ? `Availability evidence as of ${availability.data.as_of ?? "date unavailable"}` : "Only official registration can qualify"} accent="blue" />
          </div>
          <div className="dashboard-grid">
            <Panel title="Competition coverage" description={`${overview.data.matches_analyzed.toLocaleString()} matches and ${overview.data.deliveries_analyzed.toLocaleString()} deliveries across confirmed scope.`} action={<DataSource>{overview.data.availability_snapshot ? `Availability verified ${overview.data.availability_snapshot}` : "Availability date unavailable"}</DataSource>}>
              <CoverageChart rows={overview.data.formats} />
              <div className="format-coverage-grid">{overview.data.formats.map((format) => <div className="format-coverage-item" key={format.format}><span>{format.format} coverage</span><strong>{format.matches.toLocaleString()} <small>matches</small></strong><strong>{format.deliveries.toLocaleString()} <small>deliveries</small></strong><em>{format.seasons}</em></div>)}</div>
            </Panel>
            <Panel title="Bowling readiness" description="The current source data do not support a validated bowling recommendation list.">
              <div className="bowling-status-card"><span className="readiness-ring">0</span><div><strong>Competition-ready candidates</strong><span>Exploratory profiles: {overview.data.bowling.exploratory.toLocaleString()}</span></div></div>
              <p className="panel-footnote">Conceded-run attribution and legal-ball denominators remain incomplete. Exploratory profiles are not recommendations.</p>
              <Link className="link-button" to="/bowling">Review bowling evidence <span aria-hidden="true">-&gt;</span></Link>
            </Panel>
          </div>
          <Panel title="Phase 5G featured batters" description="Exact stored overall order. Contextual wicket/phase evidence is not verified scoreboard pressure or psychological pressure." action={<Link className="link-button" to="/rankings">View Top 10 <span aria-hidden="true">-&gt;</span></Link>} className="top-list-panel">
            {ranking.loading ? <LoadingPanel label="Loading the Phase 5G list" /> : null}
            {ranking.error ? <ErrorPanel message={ranking.error.message} onRetry={ranking.reload} /> : null}
            {ranking.data?.records?.length ? <div className="featured-player-grid">{ranking.data.records.slice(0, 3).map((player) => <PlayerEvidenceCard key={player.player_id} row={player} score={player.mean_within_format_percentile} scoreLabel="Mean within-format percentile" formatLabel={player.formats} compact />)}</div> : null}
            {ranking.data && !ranking.data.records.length ? <EmptyPanel title="No overall ranking rows returned">The API returned no Phase 5G records.</EmptyPanel> : null}
          </Panel>
          <div className="notice notice-blue">Auction status remains independent of performance. {availability.data?.overlay_present ? `${availability.data.count.toLocaleString()} batter availability records are present; ${targets.data?.count ?? "Not available"} currently meet the registered or final-register gate.` : availability.loading ? "Checking the dated availability overlay." : availability.error ? "Availability status could not be loaded." : "The local availability overlay is not present."}</div>
        </>
      ) : null}
    </div>
  );
}
