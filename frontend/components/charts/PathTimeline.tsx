"use client";
import { CircleCheck, Clock, ClipboardCheck, Landmark } from "lucide-react";
import { useProject, REQUIRED_DOCS } from "@/lib/project-context";
import { estimate, PREP_OPTIONS, toWeeks } from "@/lib/timeline";
import s from "./charts.module.css";

type Seg = { key: string; days: number; cls: string; label: string };

export default function PathTimeline() {
  const { prepDays, setPrepDays, readyCount } = useProject();
  const missing = REQUIRED_DOCS.length - readyCount;
  const e = estimate(prepDays);
  const ready = estimate(0);
  const maxDays = missing > 0 ? e.total : ready.total;
  const weeks = toWeeks(maxDays);
  const span = weeks * 7;
  const pct = (d: number) => `${(d / span) * 100}%`;

  const rows: { name: string; segs: Seg[]; total: number }[] = [
    {
      name: "All ready",
      total: ready.total,
      segs: [
        { key: "check", days: ready.check, cls: s.segCheck, label: "Check" },
        { key: "decide", days: ready.decide, cls: s.segDecide, label: "Decision" },
      ],
    },
  ];
  if (missing > 0) {
    rows.push({
      name: "Your path",
      total: e.total,
      segs: [
        { key: "prep", days: e.prep, cls: s.segPrep, label: "Prep" },
        { key: "check", days: e.check, cls: s.segCheck, label: "Check" },
        { key: "decide", days: e.decide, cls: s.segDecide, label: "Decision" },
      ],
    });
  }
  const tickStep = weeks > 8 ? 2 : 1;
  const ticks = Array.from({ length: Math.floor(weeks / tickStep) + 1 }, (_, i) => i * tickStep);

  return (
    <div className={s.tl}>
      <div className={s.tlTop}>
        {missing === 0 ? (
          <span className={s.allReady}><CircleCheck size={18} strokeWidth={2} aria-hidden="true" /> All docs ready</span>
        ) : (
          <label className={s.prepLabel}>
            <Clock size={16} strokeWidth={2} aria-hidden="true" /> Missing docs take
            <select className={`select ${s.prepSelect}`} value={prepDays} onChange={(ev) => setPrepDays(Number(ev.target.value))}>
              {PREP_OPTIONS.map((o) => <option key={o.days} value={o.days}>{o.label}</option>)}
            </select>
          </label>
        )}
      </div>

      <div className={s.gantt} role="img" aria-label={rows.map((r) => `${r.name}: up to about ${toWeeks(r.total)} weeks`).join(". ")}>
        {rows.map((r) => (
          <div className={s.row} key={r.name}>
            <span className={s.rowName}>{r.name}</span>
            <div className={s.track}>
              {ticks.map((t) => <span key={t} className={s.grid} style={{ left: pct(t * 7) }} />)}
              <div className={s.bars} key={`${r.name}-${prepDays}`}>
                {r.segs.map((g) => (
                  <span key={g.key} className={`${s.seg} ${g.cls}`} style={{ width: pct(g.days) }} title={`${g.label}: ${g.days} days`} />
                ))}
              </div>
            </div>
            <span className={`${s.rowTotal} num`}>up to about {toWeeks(r.total)} weeks</span>
          </div>
        ))}
        <div className={s.row} aria-hidden="true">
          <span className={s.rowName} />
          <div className={s.axis}>
            {ticks.map((t) => <span key={t} className={`${s.tick} num ${t % 4 !== 0 && t !== weeks ? s.minor : ""}`} style={{ left: pct(t * 7) }}>{t}w</span>)}
          </div>
          <span className={s.rowTotal} />
        </div>
      </div>

      <ul className={s.legend}>
        {missing > 0 && (
          <li><span className={`${s.swatch} ${s.segPrep}`} /><Clock size={16} strokeWidth={2} aria-hidden="true" /> Prep <span className="num">{e.prep}d</span></li>
        )}
        <li><span className={`${s.swatch} ${s.segCheck}`} /><ClipboardCheck size={16} strokeWidth={2} aria-hidden="true" /> Check <span className="num">{e.check}d</span> <span className={s.tag}>ASSUMPTION</span></li>
        <li><span className={`${s.swatch} ${s.segDecide}`} /><Landmark size={16} strokeWidth={2} aria-hidden="true" /> Decision <span className="num">{e.decide}d</span> <span className={s.legal}>legal limit, Gov. Code 66317</span></li>
      </ul>
    </div>
  );
}
