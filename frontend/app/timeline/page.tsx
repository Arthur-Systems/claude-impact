"use client";
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

function Path({ title, e, current, tone }: { title: string; e: Estimate; current: boolean; tone: "ok" | "warn" }) {
  const max = estimate(60).total;
  const pct = (d: number) => `${(d / max) * 100}%`;
  return (
    <section className={`card ${tone === "warn" ? "warn" : ""}`}>
      <h2>
        {title} {current && <span className="chip ok">Your current path</span>}
      </h2>
      <div className="tl" aria-hidden="true">
        {e.prep > 0 && <i style={{ width: pct(e.prep), background: "var(--amber)" }} />}
        <i style={{ width: pct(e.check), background: "#8d9692" }} />
        <i style={{ width: pct(e.decide), background: "var(--teal)" }} />
      </div>
      {e.prep > 0 && (
        <div className="row">
          <span>Get the missing documents (your estimate)</span>
          <span>{e.prep} days</span>
        </div>
      )}
      <div className="row">
        <span>City checks your application is complete</span>
        <span>about {e.check} days</span>
      </div>
      <div className="row">
        <span>City approves or denies</span>
        <span>up to {e.decide} days</span>
      </div>
      <p>
        <b>
          Total: up to about {toWeeks(e.total)} weeks ({e.total} days)
        </b>
      </p>
    </section>
  );
}

export default function Timeline() {
  const { missingPriority, prepDays, setPrepDays } = useProject();
  const hasMissing = missingPriority.length > 0;

  return (
    <>
      <PageHeader
        title="Timeline"
        status={
          hasMissing
            ? `Two possible paths to approval. You are on the slower one because ${missingPriority.length} priority documents are missing.`
            : "You have every priority document, so you are on the faster path."
        }
        next={hasMissing ? "upload the missing documents to move to the faster path." : "review your documents and submit to the city."}
        action={
          <Link className="btn" href={hasMissing ? "/documents" : "/questions"}>
            {hasMissing ? "Fix missing documents" : "Ask the City"}
          </Link>
        }
      />

      <section className="card block">
        <label htmlFor="prep">How long to get the missing documents?</label>
        <select id="prep" className="in" value={prepDays} onChange={(e) => setPrepDays(Number(e.target.value))}>
          {PREP_OPTIONS.map((o) => (
            <option key={o.days} value={o.days}>
              {o.label}
            </option>
          ))}
        </select>
        <p className="muted">This is your own estimate. It changes the slower path below.</p>
      </section>

      <div className="grid">
        <Path title="All documents submitted" e={estimate(0)} current={!hasMissing} tone="ok" />
        <Path title="With missing documents" e={estimate(prepDays)} current={hasMissing} tone="warn" />

        <section className="card">
          <h2>Possible bottlenecks</h2>
          {missingPriority.length === 0 && <p>No missing priority documents.</p>}
          {missingPriority.map((d) => (
            <div className="row" key={d.id}>
              <span>{d.label}</span>
              <span className="chip pri">Priority: missing</span>
            </div>
          ))}
          <p className="muted">If the city finds more gaps, you fix them and the completeness check starts again.</p>
        </section>

        <section className="card">
          <h2>How we estimate</h2>
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
            <li>These are maximums, not predictions. Real timing can differ.</li>
          </ul>
        </section>
      </div>
    </>
  );
}
