"use client";
import { useEffect, useState } from "react";
import s from "./charts.module.css";

export default function ReadinessRing({ ready, total, size = 64 }: { ready: number; total: number; size?: number }) {
  const stroke = Math.max(4, Math.round(size / 10));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const frac = total > 0 ? Math.min(1, Math.max(0, ready / total)) : 0;
  const [shown, setShown] = useState(0);
  useEffect(() => {
    const id = requestAnimationFrame(() => setShown(frac));
    return () => cancelAnimationFrame(id);
  }, [frac]);
  return (
    <div className={s.ring} role="img" aria-label={`${ready} of ${total} documents ready`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        {frac > 0 && (
          <circle
            className={s.ringArc}
            cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--teal)" strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - shown)}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        )}
      </svg>
      <span className={`${s.ringLabel} num`} style={{ fontSize: Math.max(10, size * 0.22) }}>
        {ready}/{total}
      </span>
    </div>
  );
}
