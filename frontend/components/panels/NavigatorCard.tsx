"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import { ExternalLink, ListChecks, Timer, Receipt, Globe, Send } from "lucide-react";
import { askNavigator, Source } from "@/lib/api";
import { useProject } from "@/lib/project-context";
import s from "./panels.module.css";

type Msg = { role: "user" | "ai"; text: string; sources?: Source[]; mock?: boolean };

const PROMPTS = [
  { label: "What's missing?", q: "What do I still need before I submit?", Icon: ListChecks },
  { label: "How long?", q: "How long will approval take?", Icon: Timer },
  { label: "Fees", q: "What are the fees?", Icon: Receipt },
  { label: "Where to apply", q: "Where do I apply?", Icon: Globe },
];

export default function NavigatorCard() {
  const { missingPriority, unmatched, place } = useProject();
  const [msgs, setMsgs] = useState<Msg[]>([{ role: "ai", text: "Ask me about your Irvine ADU permit." }]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = logRef.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduce ? "auto" : "smooth" });
  }, [msgs, busy]);

  async function send(question: string) {
    const q = question.trim();
    if (!q || busy) return;
    setMsgs((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setBusy(true);
    const reply = await askNavigator(q, {
      missing: missingPriority.map((d) => d.label),
      flagged: unmatched.length,
      address: place?.label ?? null,
    });
    setMsgs((m) => [...m, { role: "ai", text: reply.answer, sources: reply.sources, mock: reply.mock }]);
    setBusy(false);
  }
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send(input);
  };
  const started = msgs.length > 1;

  return (
    <div className={s.nav}>
      <div className={s.log} ref={logRef} role="log" aria-live="polite" aria-label="Conversation">
        {msgs.map((m, i) => (
          <div key={i} className={`${s.bubble} ${m.role === "user" ? s.u : s.a}`}>
            {m.text}
            {m.sources && m.sources.length > 0 && (
              <div className={s.srcs}>
                {m.sources.map((x) => (
                  <a key={x.url + x.label} className={s.srcChip} href={x.url} target="_blank" rel="noopener noreferrer" title={x.label}>
                    <ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
                    <span>{x.label}</span>
                  </a>
                ))}
              </div>
            )}
            {m.role === "ai" && i > 0 && (
              <div className={s.note}>{m.mock ? "Demo answer, backend not connected. " : ""}AI can make mistakes. Check the source.</div>
            )}
          </div>
        ))}
        {busy && (
          <div className={`${s.bubble} ${s.a}`}>
            <span className={s.typing} aria-hidden="true"><i /><i /><i /></span>
            <span className="sr-only">Navigator is typing</span>
          </div>
        )}
      </div>
      {!started && (
        <div className={s.chips} aria-label="Suggested questions">
          {PROMPTS.map(({ label, q, Icon }) => (
            <button key={label} type="button" className={s.chip} onClick={() => send(q)} disabled={busy}>
              <Icon size={16} strokeWidth={1.75} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      )}
      <form onSubmit={onSubmit} className={s.composer}>
        <label htmlFor="nav-q" className="sr-only">Your question</label>
        <input id="nav-q" className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about permits, fees" autoComplete="off" />
        <button className={`btn btn-primary ${s.iconBtn}`} type="submit" aria-label="Send" disabled={busy || !input.trim()}>
          <Send size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
