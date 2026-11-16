import { useMemo, useState } from "react";
import { useApi } from "../api/client";
import { displayValue } from "../api/types";
import { DataSource, EmptyPanel, ErrorPanel, LoadingPanel, MetricCard, PageIntro, Panel } from "../components/ui";

type BowlingEvidence = {
  competition_ready: number; exploratory_profiles: number; ranked_recommendations_supported: boolean;
  metric_audit: Array<Record<string, unknown>>; eligibility: Array<Record<string, unknown>>;
  metric_audit_source: string; eligibility_source: string; limitations_report?: string;
};
const descriptiveMetrics = [
  "recognized bowler-credited wickets", "recognized credited wickets per observed delivery event",
  "ordinary dot rate", "ordinary batter runs per ordinary delivery event", "ordinary boundary-event rate",
];
const blockedMetrics = ["bowler-conceded runs", "legal deliveries and overs bowled", "economy rate", "conventional bowling strike rate"];

export default function BowlingPage() {
  const { data, loading, error, reload } = useApi<BowlingEvidence>("/bowling/evidence");
  const [format, setFormat] = useState("IPL");
  const audit = useMemo(() => data?.metric_audit.filter((row) => row.format === format) ?? [], [data, format]);
  const eligibility = useMemo(() => data?.eligibility.filter((row) => row.format === format) ?? [], [data, format]);
  const metric = (name: string) => audit.find((row) => row.metric === name);
  return <div>
    <PageIntro eyebrow="Bowling evidence · Phase 5H" title="Bowling Intelligence" description="A transparent audit of what the source data can and cannot support. No exploratory profile is displayed as a validated target or ranking." />
    {loading ? <LoadingPanel label="Loading bowling evidence audit" /> : null}
    {error ? <ErrorPanel message={error.message} onRetry={reload} /> : null}
    {data ? <>
      <div className="bowling-status-grid">
        <MetricCard label="Competition-ready candidates" value={data.competition_ready.toLocaleString()} note="Validated role and exposure thresholds" accent="pink" />
        <MetricCard label="Exploratory profiles" value={data.exploratory_profiles.toLocaleString()} note="Exploratory only; not recommendations" accent="blue" />
        <MetricCard label="Ranked target list" value={data.ranked_recommendations_supported ? "Supported" : "Not supported"} note="No bowling Top 10 is published" accent="neutral" />
      </div>
      <div className="notice notice-pink">The validated decision remains 0 competition-ready and 414 exploratory profiles. Exploratory scores are not used as competition recommendations.</div>
      <Panel title="Evidence by format" description="Each value and limitation comes from the Phase 5H metric audit. IPL and T20I remain separate." action={<div className="format-switch" role="group" aria-label="Bowling evidence format"><button className={format === "IPL" ? "format-switch-active" : ""} onClick={() => setFormat("IPL")}>IPL</button><button className={format === "T20I" ? "format-switch-active" : ""} onClick={() => setFormat("T20I")}>T20I</button></div>}>
        <div className="bowling-metric-columns">
          <section><div className="bowling-section-head"><div><span>CALCULABLE, WITH SCOPE LIMITS</span><h3>Descriptive evidence</h3></div><DataSource>{data.metric_audit_source}</DataSource></div>{descriptiveMetrics.map((name) => { const row = metric(name); return <article className="bowling-evidence-row" key={name}><div><strong>{name}</strong><span>{displayValue(row?.under_pressure_or_general ?? "No metric audit record for this format.")}</span></div><div className="bowling-evidence-values"><small>Coverage</small><strong>{displayValue(row?.scope_row_coverage_pct)}{row?.scope_row_coverage_pct !== null && row?.scope_row_coverage_pct !== undefined ? "%" : ""}</strong></div><div className="bowling-evidence-values"><small>Verified-chase cohort</small><strong>{displayValue(row?.verified_pressure_metric_value)}</strong></div></article>; })}</section>
          <section><div className="bowling-section-head"><div><span>SOURCE SEMANTICS INCOMPLETE</span><h3>Blocked conventional metrics</h3></div><span className="status-pill status-unknown">Unavailable</span></div>{blockedMetrics.map((name) => { const row = metric(name); return <article className="bowling-blocked-row" key={name}><strong>{name}</strong><span>{displayValue(row?.under_pressure_or_general ?? "Not supported by validated source semantics.")}</span></article>; })}</section>
        </div>
      </Panel>
      <Panel title="Verified chase evidence" description="A verified chase state is an observable challenge definition, not psychological pressure." action={<DataSource>{data.eligibility_source}</DataSource>}>
        <div className="chase-summary-grid">{["verified chase pressure exposure", "wicket/phase contextual proxy"].map((name) => { const row = metric(name); return <article key={name} className="chase-summary-card"><span>{name}</span><strong>{displayValue(row?.metric_numerator_or_observed_value)} / {displayValue(row?.metric_denominator)}</strong><small>{format} observed rows · {displayValue(row?.scope_row_coverage_pct)}% coverage</small><p>{displayValue(row?.under_pressure_or_general ?? "No evidence row available.")}</p></article>; })}</div>
        <div className="eligibility-summary">{eligibility.map((row, index) => <div key={`${String(row.metric)}-${index}`}><span>{displayValue(row.metric)}</span><strong>{displayValue(row.players_meeting_both_sides)} profiles meet both existing floors</strong></div>)}</div>
        <p className="panel-footnote">Chase coverage is 31 of 42,085 IPL rows and 261 of 49,849 T20I rows in the audited scope. Pairing is powerplay-only; the audit found no competition-ready bowler in either format.</p>
      </Panel>
      <Panel title="What is needed to unlock a bowling ranking" description="Exact source gaps identified by the independent Phase 5H audit.">
        <ul className="limitation-list"><li>Complete bowler-conceded runs, or typed extras with validated attribution.</li><li>Provider-explicit legal-delivery status for every delivery.</li><li>Validated wicket-credit and no-ball rules.</li><li>Broader paired verified challenge states and sufficient exposure in both conditions.</li></ul>
        <div className="notice notice-blue">Ordinary-row runs are batter runs, not bowler-conceded runs. Recognized wicket yield per observed event is not conventional bowling strike rate. A wicket/phase proxy describes batting-resource depletion and is not a verified bowling-pressure measure.</div>
      </Panel>
      {data.metric_audit.length === 0 ? <EmptyPanel title="No audited bowling metrics returned">The Phase 5H audit artifact is unavailable or empty.</EmptyPanel> : null}
    </> : null}
  </div>;
}
