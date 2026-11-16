import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "../api/client";
import type { ApiEnvelope, AuctionRecord, OverallBatter } from "../api/types";
import { displayValue } from "../api/types";
import { DataSource, EmptyPanel, ErrorPanel, LoadingPanel, MetricCard, PageIntro, Panel } from "../components/ui";

type AuctionResponse = { overlay_present: boolean; as_of: string | null; count: number; records: AuctionRecord[]; source?: string; reason?: string };
type TargetsResponse = { overlay_present: boolean; as_of: string | null; count: number; targets: AuctionRecord[]; source?: string; empty_reason?: string; reason?: string };
type BowlingSummary = { competition_ready: number; exploratory_profiles: number };
const statusLabel: Record<string, string> = {
  retained_by_another_franchise: "Retained by another franchise · unavailable", retained_by_rr: "Retained by RR · already contracted",
  released_by_another_franchise_pending_registration: "Released · registration pending", released_by_rr_pending_registration: "Released by RR · registration pending",
  traded_to_other_franchise: "Traded · not available through auction", officially_registered_for_auction: "Officially registered for auction",
  included_in_final_auction_register: "Included in final auction register", unknown_unverified: "Unknown / unverified",
};
const confirmedStatuses = new Set(["officially_registered_for_auction", "included_in_final_auction_register"]);
const unconfirmedStatuses = new Set(["unknown_unverified", "released_by_another_franchise_pending_registration", "released_by_rr_pending_registration"]);
const unavailableStatuses = new Set(["retained_by_another_franchise", "retained_by_rr", "traded_to_other_franchise"]);

function SourceLink({ href, label }: { href: unknown; label: string }) {
  if (typeof href !== "string" || !/^https?:\/\//i.test(href)) return <span className="source-unavailable">Source link not recorded</span>;
  return <a className="auction-source-link" href={href} target="_blank" rel="noreferrer">{label}</a>;
}

function PlayerAvailabilityCard({ row, performance }: { row: AuctionRecord; performance?: OverallBatter }) {
  const status = String(row.ipl_2027_status ?? "unknown_unverified");
  const pillClass = confirmedStatuses.has(status) ? "status-confirmed" : status === "traded_to_other_franchise" ? "status-traded" : "status-unknown";
  return <article className="auction-player-card"><div className="auction-player-top"><div><span className="auction-player-role">{row.candidate_role}</span><h3>{row.player_name}</h3><small>ID {row.player_id}</small></div><span className={`status-pill ${pillClass}`}><i className="status-dot" />{statusLabel[status] ?? status}</span></div>
    <div className="auction-detail-grid"><div><span>Previous franchise</span><strong>{displayValue(row.previous_franchise)}</strong></div><div><span>IPL 2027 status confidence</span><strong>{displayValue(row.confidence_status)}</strong></div><div><span>Phase 5G rank</span><strong>{displayValue(performance?.rank ?? row.performance_rank_ipl)}</strong></div><div><span>Stored score</span><strong>{displayValue(performance?.mean_within_format_percentile ?? row.performance_score_ipl)}</strong></div><div><span>Pressure exposure</span><strong>{displayValue(row.pressure_events)} events · {displayValue(row.pressure_matches)} matches</strong></div><div><span>Baseline exposure</span><strong>{displayValue(row.baseline_events)} events · {displayValue(row.baseline_matches)} matches</strong></div><div><span>Contextual cohort SR (pressure / baseline)</span><strong>{displayValue(row.pressure_sr_contextual)} / {displayValue(row.baseline_sr_contextual)}</strong></div><div><span>Contextual SR delta</span><strong>{displayValue(row.delta_sr_contextual)}</strong></div><div><span>Match consistency</span><strong>{displayValue(row.match_consistency_index)} · reliability {displayValue(row.consistency_reliability_factor)}</strong></div><div><span>Ranking stability note</span><strong>{displayValue(row.rank_stability_note)}</strong></div><div><span>Verified on</span><strong>{displayValue(row.verification_date)}</strong></div></div>
    <p className="auction-explanation">{displayValue(row.explanation)}</p>
    <div className="auction-assessment"><strong>Analytical squad contribution</strong><p>{performance ? `Potential batter-contribution assessment: frozen Phase 5G Top 10 at rank ${performance.rank} with stored score ${displayValue(performance.mean_within_format_percentile)}. This is a performance signal only; role fit and squad need are unassessed.` : row.candidate_role === "bowler" ? "Availability evidence only. The current bowling audit supports no validated target or contribution recommendation." : row.performance_eligible ? "Potential batter-contribution assessment: the existing IPL profile is performance-eligible. Availability is separate; squad fit remains unassessed." : "Availability evidence only; no eligible IPL batter ranking is recorded for this profile."} Contextual cohort rates are not verified scoreboard-pressure measures.</p></div>
    <div className="auction-sources"><span>Evidence sources</span><SourceLink href={row.source_url} label="Availability source"/><SourceLink href={row.status_reference_url} label="Status reference"/><SourceLink href={row.process_timeline_source_url} label="Timeline reference"/><small>Publication: {displayValue(row.source_publication_date)} · Verified: {displayValue(row.verification_date)}</small></div>
    <Link className="auction-profile-link" to={`/discovery/${row.player_id}`}>Open available player evidence</Link>
  </article>;
}

function AvailabilityCardGrid({ rows, frozenIds, emptyTitle, emptyBody }: { rows: AuctionRecord[]; frozenIds: Map<string, OverallBatter>; emptyTitle: string; emptyBody: string }) {
  const [showAll, setShowAll] = useState(false);
  if (!rows.length) return <EmptyPanel title={emptyTitle}>{emptyBody}</EmptyPanel>;
  const visible = showAll ? rows : rows.slice(0, 6);
  return <><div className="auction-card-grid">{visible.map((row) => <PlayerAvailabilityCard key={`${row.player_id}-${row.candidate_role}`} row={row} performance={frozenIds.get(String(row.player_id))}/>)}</div>{rows.length > 6 ? <button className="button button-quiet auction-more-button" onClick={() => setShowAll((current) => !current)}>{showAll ? "Show fewer records" : `Show all ${rows.length.toLocaleString()} records`}</button> : null}</>;
}

export default function AuctionPage() {
  const performance = useApi<ApiEnvelope<OverallBatter>>("/rankings/batters/overall");
  const targets = useApi<TargetsResponse>("/auction/targets");
  const availability = useApi<AuctionResponse>("/auction/availability");
  const bowling = useApi<BowlingSummary>("/bowling/evidence");
  const [role, setRole] = useState("all");
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const records = availability.data?.records ?? [];
  const searchMatches = (row: AuctionRecord) => !query.trim() || `${row.player_name} ${row.player_id} ${row.previous_franchise ?? ""}`.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase());
  const filtered = useMemo(() => records.filter((row) => (role === "all" || row.candidate_role === role) && (status === "all" || row.ipl_2027_status === status) && searchMatches(row)), [records, role, status, query]);
  const targetRows = (targets.data?.targets ?? []).filter(searchMatches);
  const overall = performance.data?.records ?? [];
  const frozenIds = new Map(overall.map((row) => [String(row.player_id), row]));
  const eligibleBatters = records.filter((row) => row.candidate_role === "batter" && row.performance_eligible === true);
  const confirmedBatters = filtered.filter((row) => row.candidate_role === "batter" && confirmedStatuses.has(row.ipl_2027_status));
  const unconfirmed = filtered.filter((row) => unconfirmedStatuses.has(row.ipl_2027_status) || (!confirmedStatuses.has(row.ipl_2027_status) && !unavailableStatuses.has(row.ipl_2027_status)));
  const unavailable = filtered.filter((row) => unavailableStatuses.has(row.ipl_2027_status));
  const statusOptions = Array.from(new Set(records.map((row) => row.ipl_2027_status))).sort();
  const visibleBowling = filtered.filter((row) => row.candidate_role === "bowler");
  return <div>
    <PageIntro eyebrow="Performance and availability are independent" title="RR Auction Targets" description="The Phase 5G performance Top 10 remains frozen. Auction-pool targets qualify only through the recorded official registration or final-register status; the current source snapshot is provisional." />
    {targets.loading || availability.loading || performance.loading || bowling.loading ? <LoadingPanel label="Loading validated ranking and dated availability evidence" /> : null}
    {targets.error ? <ErrorPanel message={targets.error.message} onRetry={targets.reload} /> : null}
    {availability.error ? <ErrorPanel message={availability.error.message} onRetry={availability.reload} /> : null}
    {performance.error ? <ErrorPanel message={performance.error.message} onRetry={performance.reload} /> : null}
    {bowling.error ? <ErrorPanel message={bowling.error.message} onRetry={bowling.reload} /> : null}
    {targets.data && availability.data && performance.data ? <>
      <div className="auction-status-grid"><MetricCard label="Performance Top 10" value={overall.length.toLocaleString()} note="Phase 5G frozen order" accent="pink"/><MetricCard label="Eligible IPL batter profiles" value={eligibleBatters.length.toLocaleString()} note="Existing eligibility field" accent="blue"/><MetricCard label="Confirmed RR targets" value={targets.data.count.toLocaleString()} note="Registration/final register + batter eligibility" accent="neutral"/><MetricCard label="Snapshot verified" value={availability.data.as_of ?? "Unavailable"} note="Dated records; not live status" accent="blue"/></div>
      {!availability.data.overlay_present ? <EmptyPanel title="Availability overlay is not available">{availability.data.reason ?? "No source-backed status records are available."} No replacement availability data has been generated.</EmptyPanel> : <>
        <div className="notice">A release is not auction registration. Previous franchise mapping is not proof of an IPL 2027 contract. Each candidate card retains the recorded confidence, source URL, publication date and verification date.</div>
        <Panel title="Two separate lists" description="Performance rank is unchanged by the availability overlay." action={<DataSource>{targets.data.source ?? "Availability overlay"}</DataSource>}>
          <div className="two-list-grid"><section className="list-card list-card-performance"><span className="list-index">LIST 01</span><h3>Performance Top 10</h3><p>Exact Phase 5G order and stored score.</p><ol className="auction-top-list">{overall.map((player) => <li key={player.player_id}><span>{player.rank}</span><Link to={`/discovery/${player.player_id}`}><strong>{player.player_name}</strong></Link><small>ID {player.player_id} · {displayValue(player.mean_within_format_percentile)}</small></li>)}</ol></section><section className="list-card list-card-auction"><span className="list-index">LIST 02</span><h3>Confirmed auction-pool candidates</h3><p>{targets.data.overlay_present ? targets.data.empty_reason ?? `${targets.data.count} qualifying candidates in this snapshot.` : targets.data.reason}</p><span className="status-pill status-confirmed"><i className="status-dot"/>Official status gate</span>{targetRows.length ? <div className="target-list">{targetRows.map((row) => <PlayerAvailabilityCard key={row.player_id} row={row} performance={frozenIds.get(String(row.player_id))}/>)}</div> : null}</section></div>
        </Panel>
        <Panel title="Filter availability records" description="Search all analyzed batter and bowler profiles with an availability row. Filtering does not change performance eligibility." className="auction-filter-panel">
          <div className="toolbar"><div className="field"><label htmlFor="auction-role">Candidate role</label><select id="auction-role" className="select" value={role} onChange={(event) => setRole(event.target.value)}><option value="all">All roles</option><option value="batter">Batters</option><option value="bowler">Bowlers</option></select></div><div className="field"><label htmlFor="auction-status">Recorded status</label><select id="auction-status" className="select" value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option>{statusOptions.map((value) => <option key={value} value={value}>{statusLabel[value] ?? value}</option>)}</select></div><div className="field search-field"><label htmlFor="auction-search">Search player, ID or previous franchise</label><input id="auction-search" className="input" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search availability records"/></div><DataSource>{availability.data.source ?? "Availability overlay"} · {availability.data.as_of ?? "undated"}</DataSource></div>
          <div className="results-heading"><strong>{filtered.length.toLocaleString()} matching records</strong><span>Source records are not predictions of future retention or registration.</span></div>
        </Panel>
        <Panel title="Available batter targets" description="Only API-qualified Phase 5C eligible batters with recorded registration or final-register status qualify."><AvailabilityCardGrid rows={confirmedBatters} frozenIds={frozenIds} emptyTitle="No confirmed batter target matches these filters" emptyBody="There are no registered/final-register eligible batter records in the current snapshot."/></Panel>
        <Panel title="Availability unconfirmed" description="Unknown and release-pending profiles require official player-specific registration evidence before they can be treated as auction candidates."><AvailabilityCardGrid rows={unconfirmed} frozenIds={frozenIds} emptyTitle="No unconfirmed records match these filters" emptyBody="Change the role, status or search filters to review other records."/></Panel>
        <Panel title="Unavailable or already contracted" description="Recorded retention and trade statuses do not qualify through the auction. A trade may change only after a subsequent verified release and registration."><AvailabilityCardGrid rows={unavailable} frozenIds={frozenIds} emptyTitle="No unavailable records match these filters" emptyBody="Change the role, status or search filters to review other records."/></Panel>
        <Panel title="Bowling availability evidence" description="This section shows availability status only; it does not turn exploratory bowling profiles into performance recommendations."><div className="bowling-availability-summary"><MetricCard label="Availability records matching filters" value={visibleBowling.length.toLocaleString()} note="Availability status only" accent="blue"/><MetricCard label="Competition-ready bowlers" value={displayValue(bowling.data?.competition_ready)} note="Phase 5H validated status" accent="pink"/><MetricCard label="Exploratory profiles" value={displayValue(bowling.data?.exploratory_profiles)} note="No ranked bowling shortlist" accent="neutral"/></div><AvailabilityCardGrid rows={visibleBowling} frozenIds={frozenIds} emptyTitle="No bowler availability records match these filters" emptyBody="Availability is separate from the validated competition-ready and exploratory bowling evidence."/></Panel>
        <details className="accordion"><summary>Availability method and update policy</summary><div className="auction-method"><p>Current overlay verification date: {availability.data.as_of ?? "not available"}. Status is based on the player-level record, not rumours or predicted retention lists. “Previous franchise” records historical project mapping and does not establish a current contract.</p><p>The final auction register is not present in this project snapshot; current auction targets therefore remain provisional and require official player-specific registration/final-register confirmation.</p><p>Candidate contribution text is an analytical assessment based only on existing role, performance and exposure fields. It does not infer price, biography, age, auction demand or Rajasthan Royals squad needs.</p></div></details>
      </>}
    </> : null}
  </div>;
}
