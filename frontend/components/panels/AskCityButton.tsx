"use client";
import { FormEvent, useRef, useState } from "react";
import { Mail, X, Phone, Clock, CircleCheck } from "lucide-react";
import { IRVINE_ADU_PAGE } from "@/lib/knowledge";
import { useProject } from "@/lib/project-context";
import s from "./panels.module.css";

const TOPICS = ["Missing or unclear documents", "Fees", "Timeline", "Something else"];
const CITY_EMAIL = "planning@cityofirvine.org";

export default function AskCityButton() {
  const { threads, addThread, markAnswered, unmatched, place } = useProject();
  const [topic, setTopic] = useState(TOPICS[0]);
  const [message, setMessage] = useState("");
  const [attach, setAttach] = useState(true);
  const [error, setError] = useState("");
  const dlgRef = useRef<HTMLDialogElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const msgRef = useRef<HTMLTextAreaElement>(null);

  const close = () => dlgRef.current?.close();

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
      <button ref={btnRef} type="button" className={`btn btn-secondary ${s.askBtn}`} aria-label="Ask the City" onClick={() => dlgRef.current?.showModal()}>
        <Mail size={18} strokeWidth={1.75} aria-hidden="true" />
        <span className={s.askLabel}>Ask the City</span>
      </button>
      <dialog
        ref={dlgRef}
        className={s.dialog}
        aria-labelledby="ask-title"
        onClose={() => btnRef.current?.focus()}
        onClick={(e) => {
          if (e.target === dlgRef.current) close();
        }}
      >
        <div className={s.dlgHead}>
          <h2 id="ask-title">
            <Mail size={18} strokeWidth={1.75} aria-hidden="true" /> Ask the City
          </h2>
          <button type="button" className={s.closeBtn} aria-label="Close" onClick={close}>
            <X size={18} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>
        <form onSubmit={onSubmit} className={s.dlgForm}>
          <label htmlFor="ask-t">Topic</label>
          <select id="ask-t" className="select" value={topic} onChange={(e) => setTopic(e.target.value)}>
            {TOPICS.map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <label htmlFor="ask-m">Your question</label>
          <textarea
            id="ask-m"
            ref={msgRef}
            className={`textarea ${s.ta}`}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Describe what you need help with"
            aria-invalid={error ? true : undefined}
            aria-describedby={error ? "ask-err" : undefined}
          />
          {error && (
            <p id="ask-err" role="alert" className={s.err}>
              {error}
            </p>
          )}
          <label className={s.ck}>
            <input type="checkbox" checked={attach} disabled={unmatched.length === 0} onChange={(e) => setAttach(e.target.checked)} />
            List my flagged files in the email ({unmatched.length})
          </label>
          <button className="btn btn-primary" type="submit">
            <Mail size={18} strokeWidth={2} aria-hidden="true" /> Email the Planning Team
          </button>
          <p className="hint">Opens your email app. Replies go to your inbox.</p>
        </form>

        <dl className={s.contact}>
          <div>
            <dt><Mail size={14} aria-hidden="true" /> Planning Team</dt>
            <dd><a href={`mailto:${CITY_EMAIL}`}>{CITY_EMAIL}</a></dd>
          </div>
          <div>
            <dt><Phone size={14} aria-hidden="true" /> Phone</dt>
            <dd><a href="tel:9497246308">949-724-6308</a></dd>
          </div>
          <div>
            <dt><Clock size={14} aria-hidden="true" /> Hours</dt>
            <dd>Mon to Thu 7:30 a.m. to 5:30 p.m., Fri 8 a.m. to 5 p.m.</dd>
          </div>
        </dl>
        <p className={s.srcLine}>
          Source:{" "}
          <a href={IRVINE_ADU_PAGE} target="_blank" rel="noopener noreferrer">
            City of Irvine ADU page
          </a>
        </p>

        <h3 className={s.h3}>Your questions</h3>
        {threads.length === 0 ? (
          <p className="hint">No questions yet.</p>
        ) : (
          <ul className={s.threads}>
            {threads.map((t) => (
              <li key={t.id}>
                <span className={s.tMain}>
                  <span>{t.message}</span>
                  <span className={s.tSub}>
                    {t.topic}, {t.sentAt}
                  </span>
                </span>
                <span className={t.status === "answered" ? "badge badge-done" : "badge badge-next"}>{t.status === "answered" ? "Answered" : "Email opened"}</span>
                {t.status !== "answered" && (
                  <button type="button" className={s.closeBtn} aria-label="Mark as answered" title="Mark as answered" onClick={() => markAnswered(t.id)}>
                    <CircleCheck size={18} strokeWidth={1.75} aria-hidden="true" />
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </dialog>
    </>
  );
}
