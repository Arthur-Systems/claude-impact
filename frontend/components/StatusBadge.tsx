// Status as text plus a dot. Keyed by status so a change re-plays the pop.
export type Status = "ready" | "missing" | "todo";

export default function StatusBadge({ status }: { status: Status }) {
  if (status === "ready")
    return (
      <span key="ready" className="badge badge-done">
        Ready
      </span>
    );
  if (status === "missing")
    return (
      <span key="missing" className="badge badge-missing">
        Missing
      </span>
    );
  return (
    <span key="todo" className="badge">
      Not started
    </span>
  );
}
