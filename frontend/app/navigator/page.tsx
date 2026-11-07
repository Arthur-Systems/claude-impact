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
  const { missingPriority, unmatched, place, readyCount } = useProject();
  const [msgs, setMsgs] = useState<Msg[]>([
    { role: "ai", text: "Hi, I can help with your Irvine ADU permit. Ask what documents you still need, how long approval takes, where to apply, or what it costs." },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
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
    { label: "Resolve flagged files", done: unmatched.length === 0, href: "/documents" },
    { label: "Submit through the IrvineReady portal", done: false, href: IRVINE_PORTAL, external: true },
  ];
  const nextIdx = steps.findIndex((s) => !s.done);

  return (
    <>
      <PageHeader
        title="Navigator"
        status="Ask anything about permits, forms, or fees. Answers link to their sources."
        next={nextIdx >= 0 ? `${steps[nextIdx].label.toLowerCase()}.` : "you are ready to submit."}
      />

      <div className="grid">
        <section className="card chat">
          <h2>Chat with the Navigator</h2>
          <div className="log" role="log" aria-live="polite" aria-label="Conversation">
            {msgs.map((m, i) => (
              <div key={i} className={m.role === "user" ? "u" : "a"}>
                {m.text}
                {m.sources && m.sources.length > 0 && (
                  <div className="src">
                    {m.sources.map((s) => (
                      <div key={s.url + s.label}>
                        <a href={s.url} target="_blank" rel="noopener noreferrer">
                          Source: {s.label}
                        </a>
                      </div>
                    ))}
                  </div>
                )}
                {m.role === "ai" && i > 0 && (
                  <div className="muted">{m.mock ? "Demo answer, backend not connected. " : ""}AI can make mistakes. Check the source or ask the city.</div>
                )}
              </div>
            ))}
            {busy && <div className="a muted">Thinking...</div>}
            <div ref={endRef} />
          </div>
          <div className="actions">
            {PROMPTS.map((p) => (
              <button key={p} className="btn2" onClick={() => send(p)} disabled={busy}>
                {p}
              </button>
            ))}
          </div>
          <form onSubmit={onSubmit} className="addr-form">
            <div className="grow">
              <label htmlFor="q">Your question</label>
              <input id="q" className="in full" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about permits, forms, fees" />
            </div>
            <button className="btn" type="submit" disabled={busy || !input.trim()}>
              Send
            </button>
          </form>
        </section>

        <section className="card">
          <h2>Your step by step guide</h2>
          <ol className="steps">
            {steps.map((s, i) => (
              <li key={s.label}>
                <span>
                  {s.external ? (
                    <a href={s.href} target="_blank" rel="noopener noreferrer">
                      {s.label}
                    </a>
                  ) : (
                    <Link href={s.href}>{s.label}</Link>
                  )}
                </span>
                {s.done ? <span className="chip ok">Done</span> : i === nextIdx ? <span className="chip miss">Do this next</span> : <span className="chip todo">To do</span>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </>
  );
}
