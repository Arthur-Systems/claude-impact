"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { DataBanner, SourceChip } from "@/components/LiveData";
import { Milestone, Timeline as LiveTimeline, TimingValue, backendConfigured, loadDemoTimeline } from "@/lib/backend";
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
        <span>about {e.check} days (ASSUMPTION)</span>
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

const STATE_LABEL: Record<string, string> = {
  completed: "Done",
  in_progress: "In progress",
  not_started: "Not started",
  blocked: "Blocked",
  ready: "Ready to start",
};

function timingText(kind: string, t: TimingValue) {
  if (!t || (t.min_days == null && t.max_days == null)) return null;
  const range = t.min_days === t.max_days || t.max_days == null ? `${t.min_days}` : `${t.min_days ?? 0} to ${t.max_days}`;
  return `${kind === "assumption" ? "ASSUMPTION" : kind.replace(/_/g, " ")}: ${range} days${t.rationale ? ` (${t.rationale})` : ""}`;
}

function LiveMilestone({ m, index, data }: { m: Milestone; index: number; data: LiveTimeline }) {
  const durations = (["city_service_target", "statutory_clock", "observed", "assumption"] as const)
    .map((k) => timingText(k, m.timing?.[k] ?? null))
    .filter(Boolean);
  const cites = data.citations.filter((c) => m.citation_ids.includes(c.id));
  const tone = m.state === "completed" ? "ok" : m.availability === "blocked" ? "todo" : "miss";
  return (
    <div className="row">
      <span>
        <b>
          {index + 1}. {m.title}
        </b>
        {m.blocked_by.length > 0 && (
          <>
            <br />
            <span className="muted">Waiting on: {m.blocked_by.map((b) => b.key).join(", ")}</span>
          </>
        )}
        <br />
        <span className="muted">
          {durations.length ? durations.join("; ") : "Duration: no estimate from the API (none shown)."}
          {m.forecast_finish && ` Forecast finish ${m.forecast_finish.earliest} to ${m.forecast_finish.latest} (${m.forecast_finish.label}).`}
        </span>
        {cites.map((c) => (
          <SourceChip key={c.id} c={c} />
        ))}
      </span>
      <span className={`chip ${tone}`}>{STATE_LABEL[m.availability] ?? STATE_LABEL[m.state] ?? m.availability}</span>
    </div>
  );
}

function LiveView({ data }: { data: LiveTimeline }) {
  return (
    <>
      <PageHeader
        title="Timeline"
        status={`${data.pathway?.title ?? "Irvine ADU"}: ${data.progress?.completed ?? 0} of ${data.progress?.total ?? data.milestones.length} steps done.`}
        next={data.next_actions[0]?.title ?? data.bottlenecks[0]?.message ?? "prepare the documents on the checklist."}
        action={
          <Link className="btn" href="/documents">
            See the checklist
          </Link>
        }
      />
      <DataBanner live />
      <div className="grid">
        <section className="card span-all">
          <h2>Steps to approval (as of {data.as_of})</h2>
          {data.milestones.map((m, i) => (
            <LiveMilestone key={m.key} m={m} index={i} data={data} />
          ))}
          {data.forecast && (
            <p className="muted">
              <b>{data.forecast.label}:</b>{" "}
              {data.forecast.finish_range ? `finish ${data.forecast.finish_range.earliest} to ${data.forecast.finish_range.latest}. ` : ""}
              {data.forecast.disclaimer}
            </p>
          )}
        </section>
        <section className="card">
          <h2>Next actions</h2>
          {data.next_actions.length === 0 && <p>No next action from the API yet. Start with the documents that are not ready.</p>}
          {data.next_actions.map((a, i) => (
            <div className="row" key={i}>
              <span>{a.title}</span>
            </div>
          ))}
          {data.document_readiness && (
            <p className="muted">
              Documents ready: {data.document_readiness.ready} of {data.document_readiness.denominator}
              {data.document_readiness.needs_information ? `, ${data.document_readiness.needs_information} unknown` : ""}.
            </p>
          )}
        </section>
        <section className="card warn">
          <h2>Possible bottlenecks</h2>
          {data.bottlenecks.length === 0 && <p>No bottlenecks reported.</p>}
          {data.bottlenecks.map((b, i) => (
            <div className="row" key={i}>
              <span>{b.message}</span>
              <span className="chip pri">{b.code.replace(/_/g, " ")}</span>
            </div>
          ))}
        </section>
        <section className="card span-all">
          <h2>Notes</h2>
          <ul className="plain">
            {data.warnings.map((w) => (
              <li key={w.code}>{w.message}</li>
            ))}
          </ul>
        </section>
      </div>
    </>
  );
}

export default function Timeline() {
  const { missingPriority, prepDays, setPrepDays } = useProject();
  const hasMissing = missingPriority.length > 0;
  const [live, setLive] = useState<LiveTimeline | null>(null);
  const [loading, setLoading] = useState(backendConfigured());
  useEffect(() => {
    if (!backendConfigured()) return;
    loadDemoTimeline(new Date().toISOString().slice(0, 10)).then((t) => {
      setLive(t && t.milestones?.length ? t : null);
      setLoading(false);
    });
  }, []);

  if (live) return <LiveView data={live} />;

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

      <DataBanner live={false} loading={loading} />

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
