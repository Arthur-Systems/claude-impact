"use client";
import { FormEvent, useRef, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { IRVINE_ADU_PAGE } from "@/lib/knowledge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";

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
      <PageHeader
        title="Ask the City"
        status="Send a question to the City of Irvine Planning Team and keep track of it here."
        next="try the Navigator first, then ask the city if you need a specific answer."
        action={
          <Link className="btn" href="/navigator">
            Open the Navigator
          </Link>
        }
      />

      <div className="grid">
        <section className="card">
          <h2>New question</h2>
          <form onSubmit={onSubmit}>
            <div className="field">
              <label htmlFor="t">Topic</label>
              <select id="t" className="in full" value={topic} onChange={(e) => setTopic(e.target.value)}>
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
                className="in full area"
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
            <button className="btn" type="submit">
              Email the Planning Team
            </button>
            <p className="muted">This opens your email app with your question filled in. Replies come to your inbox, not here. Attach any files in your email app.</p>
          </form>
        </section>

        <section className="card">
          <h2>City contact</h2>
          <p>
            Planning Team:{" "}
            <a href={`mailto:${CITY_EMAIL}`}>{CITY_EMAIL}</a>
            <br />
            Phone: <a href="tel:9497246308">949-724-6308</a>
            <br />
            Hours: Mon to Thu 7:30 a.m. to 5:30 p.m., Fri 8 a.m. to 5 p.m.
          </p>
          <p className="muted">
            Source: <a href={IRVINE_ADU_PAGE} target="_blank" rel="noopener noreferrer">City of Irvine ADU page</a>
          </p>
        </section>

        <section className="card span-all">
          <h2>Your questions</h2>
          {threads.length === 0 && <p>No questions yet. Ask one and it will be tracked here.</p>}
          {threads.map((t) => (
            <div className="row" key={t.id}>
              <span>
                {t.message}
                <br />
                <span className="muted">
                  {t.topic}, {t.sentAt}
                </span>
              </span>
              <span className="actions">
                <span className={t.status === "answered" ? "chip ok" : "chip miss"}>{t.status === "answered" ? "Answered" : "Email opened"}</span>
                {t.status !== "answered" && (
                  <button className="btn2" onClick={() => markAnswered(t.id)}>
                    Mark as answered
                  </button>
                )}
              </span>
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
