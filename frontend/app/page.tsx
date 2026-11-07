"use client";
import { ArrowRight, CalendarClock, CircleCheck, Compass, FileText, FileWarning, Files, MapPin, MessageCircle, Send, Upload, Route } from "lucide-react";
import type { ReactNode } from "react";
import ReadinessRing from "@/components/charts/ReadinessRing";
import JourneyTracker from "@/components/charts/JourneyTracker";
import PathTimeline from "@/components/charts/PathTimeline";
import MapCard from "@/components/map/MapCard";
import NavigatorCard from "@/components/panels/NavigatorCard";
import DocumentsCard from "@/components/DocumentsCard";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { estimate, toWeeks } from "@/lib/timeline";
import { IRVINE_PORTAL } from "@/lib/knowledge";

const I = { size: 18, strokeWidth: 1.75, "aria-hidden": true } as const;

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function CardHead({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="dash-head">
      <span className="dash-icon">{icon}</span>
      <h2>{title}</h2>
      {children && <span className="dash-head-end">{children}</span>}
    </div>
  );
}

export default function Dashboard() {
  const { missingPriority, readyCount, prepDays, place } = useProject();
  const total = REQUIRED_DOCS.length;
  const missing = missingPriority.length;
  const best = toWeeks(estimate(0).total);
  const worst = toWeeks(estimate(missing === 0 ? 0 : prepDays).total);

  let next: ReactNode;
  if (missing > 0) {
    next = (
      <button className="btn btn-primary tile-btn" onClick={() => scrollToId("documents")}>
        <Upload {...I} /> Upload {missingPriority[0].label.toLowerCase()}
      </button>
    );
  } else if (!place) {
    next = (
      <button
        className="btn btn-primary tile-btn"
        onClick={() => {
          const el = document.getElementById("map-search") as HTMLInputElement | null;
          el?.scrollIntoView({ behavior: "smooth", block: "center" });
          el?.focus({ preventScroll: true });
        }}
      >
        <MapPin {...I} /> Add address
      </button>
    );
  } else {
    next = (
      <a className="btn btn-primary tile-btn" href={IRVINE_PORTAL} target="_blank" rel="noreferrer">
        <Send {...I} /> Submit on IrvineReady
      </a>
    );
  }

  return (
    <div className="dash">
      <h1 className="sr-only">ClearPath dashboard</h1>
      <section className="card tile enter" style={{ ["--i" as string]: 0 }} aria-label="Document readiness">
        <div className="tile-label"><Files {...I} /> Documents</div>
        <div className="tile-body">
          <ReadinessRing ready={readyCount} total={total} size={56} />
          <span className="tile-value num">{readyCount}/{total}</span>
        </div>
      </section>

      <button className="card tile tile-click enter" style={{ ["--i" as string]: 1 }} onClick={() => scrollToId("documents")} aria-label={`${missing} missing documents, go to documents`}>
        <span className="tile-label">
          {missing > 0 ? <FileWarning {...I} /> : <CircleCheck {...I} />} Missing
        </span>
        <span className="tile-body">
          <span className={`tile-badge ${missing > 0 ? "is-bad" : "is-good"}`}>
            {missing > 0 ? <FileWarning size={20} strokeWidth={2} aria-hidden="true" /> : <CircleCheck size={20} strokeWidth={2} aria-hidden="true" />}
          </span>
          <span className="tile-value num">{missing}</span>
        </span>
      </button>

      <section className="card tile enter" style={{ ["--i" as string]: 2 }} aria-label="Approval estimate">
        <div className="tile-label"><CalendarClock {...I} /> Approval</div>
        <div className="tile-body tile-stack">
          <span className="tile-value num">{best === worst ? `${best}` : `${best} to ${worst}`} <small>wks</small></span>
          <span className="tile-caption">Estimated total</span>
        </div>
      </section>

      <section className="card tile enter" style={{ ["--i" as string]: 3 }} aria-label="Next step">
        <div className="tile-label"><ArrowRight {...I} /> Next step</div>
        <div className="tile-body">{next}</div>
      </section>

      <section className="card span-12" aria-label="Journey">
        <CardHead icon={<Route {...I} />} title="Journey" />
        <JourneyTracker />
      </section>

      <div className="span-7 cell-map">
        <MapCard />
      </div>

      <section className="card span-5 cell-docs" id="documents" aria-label="Documents">
        <CardHead icon={<FileText {...I} />} title="Documents">
          <span className="num">{readyCount}/{total} ready</span>
        </CardHead>
        <DocumentsCard />
      </section>

      <section className="card span-7" id="timeline" aria-label="Timeline">
        <CardHead icon={<Compass {...I} />} title="Timeline" />
        <PathTimeline />
      </section>

      <section className="card span-5 cell-nav" id="navigator" aria-label="Navigator">
        <CardHead icon={<MessageCircle {...I} />} title="Navigator" />
        <div className="cell-nav-body">
          <NavigatorCard />
        </div>
      </section>
    </div>
  );
}
