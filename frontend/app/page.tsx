"use client";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import AddressMap from "@/components/AddressMap";
import StatusBadge from "@/components/StatusBadge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { estimate, toWeeks } from "@/lib/timeline";

export default function Overview() {
  const { missingPriority, readyCount, isReady, prepDays } = useProject();
  const total = REQUIRED_DOCS.length;
  const blocking = missingPriority.length;
  const best = estimate(0);
  const withMissing = estimate(prepDays);

  return (
    <>
      <PageHeader title="Overview" subtitle="Detached ADU in Irvine.">
        {blocking > 0 ? (
          <div className="notice notice-warn" role="status" style={{ marginTop: "var(--space-5)", marginBottom: 0 }}>
            <p>
              <b className="num">{blocking}</b> documents block submission.
            </p>
            <Link className="btn btn-primary" href="/documents">
              Add documents
            </Link>
          </div>
        ) : (
          <div className="notice" role="status" style={{ marginTop: "var(--space-5)", marginBottom: 0 }}>
            <p>All required documents are in. Review them, then submit to the city.</p>
            <Link className="btn btn-primary" href="/documents">
              Review documents
            </Link>
          </div>
        )}
      </PageHeader>

      <div className="grid">
        <section className="card col-7">
          <div className="card-head">
            <h2>Document readiness</h2>
            <span className="muted num">
              {readyCount} of {total} ready
            </span>
          </div>
          <div className="progress" role="progressbar" aria-label="Documents ready" aria-valuemin={0} aria-valuemax={total} aria-valuenow={readyCount}>
            <span style={{ transform: `scaleX(${readyCount / total})` }} />
          </div>
          <div className="list">
            {REQUIRED_DOCS.map((d) => (
              <div className="row" key={d.id}>
                <span>{d.label}</span>
                <StatusBadge status={isReady(d.id) ? "ready" : d.priority ? "missing" : "todo"} />
              </div>
            ))}
          </div>
        </section>

        <section className="card col-5">
          <h2>Project location</h2>
          <AddressMap />
        </section>

        <section className="card col-12">
          <div className="estimate">
            <h2>Approval estimate</h2>
            <div className="stat">
              <span className="k">If everything is submitted</span>
              <span className="v">Up to about {toWeeks(best.total)} weeks</span>
            </div>
            <div className="stat">
              <span className="k">If documents stay missing</span>
              <span className="v">Up to about {toWeeks(withMissing.total)} weeks</span>
            </div>
            <p className="muted">
              These are legal limits, not predictions. <Link href="/timeline">See how we estimate</Link>
            </p>
          </div>
        </section>
      </div>
    </>
  );
}
