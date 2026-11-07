import { Citation } from "@/lib/backend";

export function DataBanner({ live, loading }: { live: boolean; loading?: boolean }) {
  if (loading) return <p className="notice" role="status">Checking for the ClearPath API...</p>;
  return live ? (
    <p className="notice live" role="status">
      Live data from ClearPath API (reviewed Irvine sources, checked 2026-11-07)
    </p>
  ) : (
    <p className="notice" role="status">
      Demo data (backend not connected)
    </p>
  );
}

export function SourceChip({ c }: { c: Citation }) {
  return (
    <details className="source">
      <summary>
        <span className="chip todo">Source: {c.title}</span>
      </summary>
      <p className="muted">
        <a href={c.url} target="_blank" rel="noreferrer">
          {c.url}
        </a>
        {c.locator ? ` (${c.locator})` : ""}
      </p>
      <blockquote>&ldquo;{c.excerpt}&rdquo;</blockquote>
      <p className="muted">Checked {c.checked_at}</p>
    </details>
  );
}
