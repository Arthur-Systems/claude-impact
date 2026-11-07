"use client";
import { ReactNode } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { useProject } from "@/lib/project-context";
import {
  COMPLETENESS_CHECK_DAYS,
  COMPLETENESS_LIMIT_BUSINESS_DAYS,
  DECISION_DAYS,
  PREP_OPTIONS,
  Estimate,
  estimate,
  toWeeks,
} from "@/lib/timeline";

const CHECK_COLOR = "#8d9692"; // neutral between muted and line

function Path({ title, e, current, control, footer }: { title: string; e: Estimate; current: boolean; control?: ReactNode; footer?: ReactNode }) {
  const max = estimate(60).total;
  const pct = (d: number) => `${(d / max) * 100}%`;
  return (
    <section className={`card col-6${current ? " is-current" : ""}`}>
      <div className="card-head">
        <h2>{title}</h2>
        {current && <span className="badge badge-next">Your path</span>}
      </div>
      {control}
      <div className="tl" aria-hidden="true" key={`${e.prep}-${e.check}-${e.decide}`}>
        {e.prep > 0 && <i style={{ width: pct(e.prep), background: "var(--amber)" }} />}
        <i style={{ width: pct(e.check), background: CHECK_COLOR }} />
        <i style={{ width: pct(e.decide), background: "var(--teal)" }} />
      </div>
      <div className="list">
        {e.prep > 0 && (
          <div className="row">
            <span>Get the missing documents (your estimate)</span>
            <span className="num">{e.prep} days</span>
          </div>
        )}
        <div className="row">
          <span>City checks your application is complete</span>
          <span className="num">about {e.check} days</span>
        </div>
        <div className="row">
          <span>City approves or denies</span>
          <span className="num">up to {e.decide} days</span>
        </div>
      </div>
      <p className="total num">
        Total: up to about {toWeeks(e.total)} weeks ({e.total} days)
      </p>
      {footer}
    </section>
  );
}

export default function Timeline() {
  const { missingPriority, prepDays, setPrepDays } = useProject();
  const missing = missingPriority.length;
  const hasMissing = missing > 0;

  return (
    <>
      <PageHeader
        title="Timeline"
        subtitle={hasMissing ? `You are on the slower path because ${missing} required documents are missing.` : "You have every required document, so you are on the faster path."}
      >
        <div className={`notice${hasMissing ? " notice-warn" : ""}`} style={{ marginTop: "var(--space-5)", marginBottom: 0 }}>
          <p>{hasMissing ? "Upload the missing documents to move to the faster path." : "Review your documents and submit to the city."}</p>
          <Link className="btn btn-primary" href={hasMissing ? "/documents" : "/questions"}>
            {hasMissing ? "Fix missing documents" : "Ask the City"}
          </Link>
        </div>
      </PageHeader>

      <div className="legend" aria-hidden="true">
        <span>
          <i style={{ background: "var(--amber)" }} /> Your estimate
        </span>
        <span>
          <i style={{ background: CHECK_COLOR }} /> Completeness check
        </span>
        <span>
          <i style={{ background: "var(--teal)" }} /> Decision
        </span>
      </div>

      <div className="grid">
        <Path title="All documents submitted" e={estimate(0)} current={!hasMissing} />
        <Path
          title="With missing documents"
          e={estimate(prepDays)}
          current={hasMissing}
          control={
            <div className="field" style={{ marginBottom: "var(--space-2)" }}>
              <label htmlFor="prep">How long to get the missing documents?</label>
              <select id="prep" className="select" value={prepDays} onChange={(e) => setPrepDays(Number(e.target.value))}>
                {PREP_OPTIONS.map((o) => (
                  <option key={o.days} value={o.days}>
                    {o.label}
                  </option>
                ))}
              </select>
              <p className="hint">Your own estimate. It changes this path.</p>
            </div>
          }
          footer={
            hasMissing ? (
              <p className="blocked">
                Blocked by {missing} missing documents. <Link href="/documents">View</Link>
              </p>
            ) : null
          }
        />
      </div>

      <details className="disclosure">
        <summary>How we estimate</summary>
        <div className="body">
          <ul className="plain">
            <li>
              <b>Legal limit:</b> once your application is complete, the city must approve or deny within {DECISION_DAYS} days, or it is deemed approved (California Gov. Code 66317).
            </li>
            <li>
              <b>Legal limit:</b> the city must tell you in writing whether it is complete within {COMPLETENESS_LIMIT_BUSINESS_DAYS} business days.
            </li>
            <li>
              <b>Assumption:</b> Irvine says it checks completeness in about two business days, so we use {COMPLETENESS_CHECK_DAYS} days.
            </li>
            <li>If the city finds more gaps, you fix them and the completeness check starts again.</li>
            <li>These are maximums, not predictions. Real timing can differ.</li>
          </ul>
        </div>
      </details>
    </>
  );
}
