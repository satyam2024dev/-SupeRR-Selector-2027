import { useApi } from "../api/client";
import { ErrorPanel, LoadingPanel, PageIntro, Panel } from "../components/ui";

type MethodologyResponse = { source: string; bowling_limitations_source: string; report: string; bowling_limitations: string };

export default function MethodologyPage() {
  const { data, loading, error, reload } = useApi<MethodologyResponse>("/methodology");
  return (
    <div>
      <PageIntro eyebrow="Definitions and caveats" title="Methodology" description="Read the current approved methodology and evidence limitations. Historical phase development is not exposed as product navigation." />
      <div className="method-grid">
        <Panel title="Performance ranking" description="What the overall batter list represents."><p className="method-copy">The overall list preserves the Phase 5G mean within-format percentile ordering of validated Phase 5C scores. Format scores are not pooled. Existing exposure shrinkage and match-consistency adjustments remain embedded in those scores.</p></Panel>
        <Panel title="Pressure interpretation" description="A clear distinction between context and psychological pressure."><p className="method-copy">The validated batter method uses the documented wicket/phase contextual proxy. It is not evidence of psychological pressure. Descriptive profiles retain their observed cohort and format labels.</p></Panel>
        <Panel title="Bowling evidence" description="Why there is no validated Bowler Top 10."><p className="method-copy">The project has zero competition-ready bowling candidates and 414 exploratory profiles. Complete bowler-conceded runs and legal-ball denominators are unavailable; conventional economy and strike rate remain blocked.</p></Panel>
        <Panel title="Availability" description="A separate, dated decision input."><p className="method-copy">A performance result does not establish contract status or auction registration. The availability overlay retains announcement references and verification dates. Unknown, traded, released-pending-registration, and registered states are distinct.</p></Panel>
      </div>
      {loading ? <LoadingPanel label="Loading the consolidated Phase 5H methodology source" /> : null}
      {error ? <ErrorPanel message={error.message} onRetry={reload} /> : null}
      {data ? <Panel title="Current consolidated methodology report" description={data.source}><details className="accordion"><summary>Open the source report</summary><pre className="report-text">{data.report}</pre></details><details className="accordion"><summary>Bowling limitation audit</summary><pre className="report-text">{data.bowling_limitations}</pre><div className="subtle-note">Source: {data.bowling_limitations_source}</div></details></Panel> : null}
    </div>
  );
}
