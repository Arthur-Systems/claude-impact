"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { askNavigator, Source } from "@/lib/api";
import { IRVINE_PORTAL } from "@/lib/knowledge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";

type Msg = { role: "user" | "ai"; text: string; sources?: Source[]; mock?: boolean };

const PROMPTS = ["What do I still need before I submit?", "How long will approval take?", "What are the fees?", "Where do I apply?"];

export default function Navigator() {
  const { files, missingPriority, unmatched, place, readyCount } = useProject();
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "ai", text: "Hi, I can help with your Irvine ADU permit. Ask what documents you still need, how long approval takes, where to apply, or what it costs." },
  ]);
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

  const steps = [
    { label: "Confirm your project address", done: !!place, href: "/" },
    { label: `Upload required documents (${readyCount} of ${REQUIRED_DOCS.length} ready)`, done: missingPriority.length === 0, href: "/documents" },
    { label: "Resolve flagged files", done: files.length > 0 && unmatched.length === 0, href: "/documents" },
    { label: "Submit through the IrvineReady portal", done: false, href: IRVINE_PORTAL, external: true },
  ];
  const nextIdx = steps.findIndex((s) => !s.done);
  const started = msgs.length > 1;

  return (
    <>
      <PageHeader title="Navigator" subtitle="Ask about permits, forms, or fees. Answers cite sources." />

      <div className="grid">
        <section className="card chat col-8">
          <h2 className="sr-only">Chat with the Navigator</h2>
          <div className="log" ref={logRef} role="log" aria-live="polite" aria-label="Conversation">
            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.role === "user" ? "u" : "a"}`}>
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div className="src">
                    {m.sources.map((s) => (
                      <a key={s.url + s.label} href={s.url} target="_blank" rel="noopener noreferrer">
                        Source: {s.label}
                      </a>
                    ))}
                  </div>
                )}
                {m.role === "ai" && i > 0 && (
                  <div className="note">{m.mock ? "Demo answer, backend not connected. " : ""}AI can make mistakes. Check the source or ask the city.</div>
                )}
              </div>
            ))}
            {busy && (
              <div className="bubble a" aria-label="Navigator is typing">
                <span className="typing" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="sr-only">Navigator is typing</span>
              </div>
            )}
          </div>
          {!started && (
            <div className="chips" aria-label="Suggested questions">
              {PROMPTS.map((p) => (
                <button key={p} className="btn btn-secondary chip" onClick={() => send(p)} disabled={busy}>
                  {p}
                </button>
              ))}
            </div>
          )}
          <form onSubmit={onSubmit} className="inline-form composer">
            <div className="grow">
              <label htmlFor="q" className="sr-only">
                Your question
              </label>
              <input id="q" className="input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about permits, forms, fees" />
            </div>
            <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
              Send
            </button>
          </form>
        </section>

        <section className="card col-4 guide">
          <h2>Step by step</h2>
          <ol className="steps">
            {steps.map((s, i) => (
              <li key={s.label}>
                <span>
                  {i === nextIdx ? (
                    s.external ? (
                      <a className="btn btn-ghost" href={s.href} target="_blank" rel="noopener noreferrer">
                        {s.label}
                      </a>
                    ) : (
                      <Link className="btn btn-ghost" href={s.href}>
                        {s.label}
                      </Link>
                    )
                  ) : (
                    s.label
                  )}
                </span>
                {s.done ? <span className="badge badge-done">Done</span> : i === nextIdx ? <span className="badge badge-next">Do this next</span> : <span className="badge">To do</span>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </>
  );
}
