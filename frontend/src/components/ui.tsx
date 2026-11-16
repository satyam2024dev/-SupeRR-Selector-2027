import type { ReactNode } from "react";
import { AlertCircle, ArrowUpRight, RefreshCw } from "lucide-react";

export function PageIntro({ eyebrow, title, description, aside }: {
  eyebrow: string;
  title: string;
  description: string;
  aside?: ReactNode;
}) {
  return (
    <div className="page-intro">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {aside ? <div className="page-intro-aside">{aside}</div> : null}
    </div>
  );
}

export function MetricCard({ label, value, note, accent = "pink" }: {
  label: string;
  value: string | number;
  note?: string;
  accent?: "pink" | "blue" | "neutral";
}) {
  return (
    <article className={`metric-card metric-${accent}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      {note ? <div className="metric-note">{note}</div> : null}
    </article>
  );
}

export function Panel({ title, description, action, children, className = "" }: {
  title: string;
  description?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

export function LoadingPanel({ label = "Loading verified project data" }: { label?: string }) {
  return (
    <div className="state-panel" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <div><strong>{label}</strong><p>Reading the local API and validated project artifacts.</p></div>
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state-panel state-error" role="alert">
      <span className="state-icon"><AlertCircle size={19} /></span>
      <div className="state-copy"><strong>Live project data is not connected</strong><p>{message}</p></div>
      <button className="button button-quiet" onClick={onRetry} type="button"><RefreshCw size={15} /> Retry</button>
    </div>
  );
}

export function EmptyPanel({ title, children }: { title: string; children: ReactNode }) {
  return <div className="empty-panel"><div className="empty-mark"><ArrowUpRight size={18} /></div><strong>{title}</strong><div>{children}</div></div>;
}

export function DataSource({ children }: { children: ReactNode }) {
  return <span className="source-label"><span className="source-dot" />{children}</span>;
}

export function Table({ headers, children }: { headers: string[]; children: ReactNode }) {
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}
