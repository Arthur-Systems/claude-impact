"use client";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import AddressMap from "@/components/AddressMap";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { estimate, toWeeks } from "@/lib/timeline";

export default function Overview() {
  const { missingPriority, readyCount, isReady, prepDays } = useProject();
  const total = REQUIRED_DOCS.length;
  const allGood = missingPriority.length === 0;
  const best = estimate(0);
  const withMissing = estimate(prepDays);

  return (
    <>
      <PageHeader
        title="Overview"
        status={`Your Irvine detached ADU project. ${readyCount} of ${total} documents are ready${
          allGood ? "." : `, and ${missingPriority.length} are blocking submission.`
        }`}
        next={allGood ? "review your documents and submit to the city." : `add the ${missingPriority.length} priority documents before you submit.`}
        action={
          <Link className="btn" href="/documents">
            Go to Documents
          </Link>
        }
      />

      {!allGood && (
        <div className="alert" role="alert">
          <b>{missingPriority.length} priority items</b> are blocking submission:{" "}
          {missingPriority.map((d) => d.label).join(", ")}. <Link href="/documents">Fix in Documents</Link>
        </div>
      )}

      <div className="grid">
        <section className="card">
          <h2>Project location</h2>
          <AddressMap />
          <p>Project: Detached ADU. City: Irvine.</p>
        </section>

        <section className="card">
          <h2>Document readiness</h2>
          <div className="bar" aria-hidden="true">
            <i style={{ width: `${(readyCount / total) * 100}%` }} />
          </div>
          <p className="muted">
            {readyCount} of {total} ready
          </p>
          {REQUIRED_DOCS.map((d) => (
            <div className="row" key={d.id}>
              <span>{d.label}</span>
              {isReady(d.id) ? (
                <span className="chip ok">Ready</span>
              ) : d.priority ? (
                <span className="chip pri">Priority: missing</span>
              ) : (
                <span className="chip todo">Not started</span>
              )}
            </div>
          ))}
        </section>

        <section className="card span-all">
          <h2>Approval estimate</h2>
          <div className="two-col">
            <div>
              <b>If everything is submitted</b>
              <br />
              Up to about {toWeeks(best.total)} weeks
            </div>
            <div>
              <b>If documents stay missing</b>
              <br />
              Up to about {toWeeks(withMissing.total)} weeks
            </div>
          </div>
          <p className="muted">
            These are legal limits, not predictions. <Link href="/timeline">See how we estimate</Link>
          </p>
        </section>
      </div>
    </>
  );
}
