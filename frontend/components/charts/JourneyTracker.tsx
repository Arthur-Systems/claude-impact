"use client";
import { CircleCheck, ClipboardCheck, FileText, Landmark, MapPin, Send, type LucideIcon } from "lucide-react";
import { useProject, REQUIRED_DOCS } from "@/lib/project-context";
import { COMPLETENESS_CHECK_DAYS, DECISION_DAYS } from "@/lib/timeline";
import { IRVINE_PORTAL } from "@/lib/knowledge";
import s from "./charts.module.css";

type State = "done" | "current" | "upcoming";
type Step = { key: string; label: string; Icon: LucideIcon; state: State; sub?: React.ReactNode; href?: string };

export default function JourneyTracker() {
  const { place, readyCount } = useProject();
  const total = REQUIRED_DOCS.length;
  const docsDone = readyCount >= total;
  const placeDone = !!place;

  const raw: Omit<Step, "state">[] = [
    { key: "addr", label: "Address", Icon: MapPin },
    { key: "docs", label: "Documents", Icon: FileText, sub: <span className="num">{readyCount}/{total}</span> },
    { key: "submit", label: "Submit", Icon: Send, sub: "IrvineReady", href: IRVINE_PORTAL },
    { key: "check", label: "Check", Icon: ClipboardCheck, sub: <>about {COMPLETENESS_CHECK_DAYS} days <span className={s.tag}>ASSUMPTION</span></> },
    { key: "decide", label: "Decision", Icon: Landmark, sub: <>within {DECISION_DAYS} days, <span className={s.legal}>legal limit</span></> },
  ];
  const doneFlags = [placeDone, docsDone, false, false, false];
  const currentIdx = doneFlags.findIndex((d) => !d);
  const steps: Step[] = raw.map((r, i) => ({ ...r, state: doneFlags[i] ? "done" : i === currentIdx ? "current" : "upcoming" }));
  const fill = steps.length > 1 ? Math.max(0, currentIdx) / (steps.length - 1) : 0;

  return (
    <ol className={s.journey} aria-label="Permit journey">
      <span className={s.jLine} aria-hidden="true">
        <span className={s.jFill} style={{ ["--fill" as string]: fill } as React.CSSProperties} />
      </span>
      {steps.map(({ key, label, Icon, state, sub, href }) => (
        <li key={key} className={`${s.jStep} ${s[state]}`} aria-current={state === "current" ? "step" : undefined}>
          <span className={s.jDot}>
            {state === "done" ? <CircleCheck size={20} strokeWidth={2} aria-hidden="true" /> : <Icon size={18} strokeWidth={1.75} aria-hidden="true" />}
          </span>
          <span className={s.jText}>
            <span className={s.jLabel}>
              {href ? <a href={href} target="_blank" rel="noreferrer">{label}</a> : label}
              <span className="sr-only"> ({state})</span>
            </span>
            {sub && <span className={s.jSub}>{sub}</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}
