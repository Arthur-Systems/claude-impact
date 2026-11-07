"use client";
import { FormEvent, useRef, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { IRVINE_ADU_PAGE } from "@/lib/knowledge";
import { useProject } from "@/lib/project-context";

const TOPICS = ["Missing or unclear documents", "Fees", "Timeline", "Something else"];
const CITY_EMAIL = "planning@cityofirvine.org";

export default function Questions() {
  const { threads, addThread, markAnswered, unmatched, place } = useProject();
  const [topic, setTopic] = useState(TOPICS[0]);
  const [message, setMessage] = useState("");
  const [attach, setAttach] = useState(true);
  const [error, setError] = useState("");
  const msgRef = useRef<HTMLTextAreaElement>(null);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const text = message.trim();
    if (text.length < 10) {
      setError("Write at least a sentence so the city can help you.");
      msgRef.current?.focus();
      return;
    }
    setError("");
    const flagged = attach && unmatched.length > 0 ? `\n\nFiles I am unsure about (I will attach them):\n${unmatched.map((f) => `- ${f.name}`).join("\n")}` : "";
    const where = place ? `\n\nProject address: ${place.label}` : "";
    const body = `${text}${where}${flagged}\n\nSent from ClearPath`;
    addThread({ topic, message: text });
    setMessage("");
    window.location.href = `mailto:${CITY_EMAIL}?subject=${encodeURIComponent(`ADU question: ${topic}`)}&body=${encodeURIComponent(body)}`;
  }

  return (
    <>
      <PageHeader title="Ask the City" subtitle="Send a question to the City of Irvine Planning Team and track it here.">
        <div className="notice" style={{ marginTop: "var(--space-5)", marginBottom: 0 }}>
          <p>Try the Navigator first.</p>
          <Link className="btn btn-secondary" href="/navigator">
            Open Navigator
          </Link>
        </div>
      </PageHeader>

      <div className="grid">
        <section className="card col-7">
          <h2>New question</h2>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="t">Topic</label>
              <select id="t" className="select" value={topic} onChange={(e) => setTopic(e.target.value)}>
                {TOPICS.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="m">Your question</label>
              <textarea
                id="m"
                ref={msgRef}
                className="textarea"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe what you need help with"
                aria-invalid={error ? true : undefined}
                aria-describedby={error ? "m-error" : undefined}
              />
              {error && (
                <p id="m-error" role="alert" className="error">
                  {error}
                </p>
              )}
            </div>
            <label className="ck">
              <input type="checkbox" checked={attach} disabled={unmatched.length === 0} onChange={(e) => setAttach(e.target.checked)} />
              List my flagged files in the email ({unmatched.length})
            </label>
            <button className="btn btn-primary" type="submit">
              Email the Planning Team
            </button>
            <p className="hint" style={{ marginTop: "var(--space-2)" }}>
              Opens your email app. Replies go to your inbox.
            </p>
          </form>
        </section>

        <section className="card col-5">
          <h2>City contact</h2>
          <dl className="contact" style={{ margin: 0 }}>
            <dt>Planning Team</dt>
            <dd>
              <a href={`mailto:${CITY_EMAIL}`}>{CITY_EMAIL}</a>
            </dd>
            <dt>Phone</dt>
            <dd>
              <a href="tel:9497246308">949-724-6308</a>
            </dd>
            <dt>Hours</dt>
            <dd>Mon to Thu 7:30 a.m. to 5:30 p.m., Fri 8 a.m. to 5 p.m.</dd>
          </dl>
          <p className="muted" style={{ margin: "var(--space-4) 0 0" }}>
            Source:{" "}
            <a href={IRVINE_ADU_PAGE} target="_blank" rel="noopener noreferrer">
              City of Irvine ADU page
            </a>
          </p>
        </section>

        <section className="card-flat col-12">
          <h2 className="section-title">Your questions</h2>
          {threads.length === 0 ? (
            <div className="empty">
              <p>No questions yet. Ask one and it will be tracked here.</p>
            </div>
          ) : (
            <div className="list">
              {threads.map((t) => (
                <div className="row enter" key={t.id}>
                  <span className="row-main">
                    <span>{t.message}</span>
                    <span className="row-sub">
                      {t.topic}, {t.sentAt}
                    </span>
                  </span>
                  <span className="row-end">
                    <span key={t.status} className={t.status === "answered" ? "badge badge-done" : "badge badge-next"}>
                      {t.status === "answered" ? "Answered" : "Email opened"}
                    </span>
                    {t.status !== "answered" && (
                      <button className="btn btn-secondary" onClick={() => markAnswered(t.id)}>
                        Mark as answered
                      </button>
                    )}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </>
  );
}
