"use client";
import { FormEvent, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { Entry, searchEntries } from "@/lib/knowledge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";

type Filter = "all" | "rules" | "mine";
const EXAMPLES = ["How long does approval take?", "What forms does Irvine require?", "Where do I submit?"];

export default function Search() {
  const { files } = useProject();
  const [query, setQuery] = useState("");
  const [asked, setAsked] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  function run(q: string) {
    setQuery(q);
    setAsked(q.trim());
  }
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    run(query);
  };

  const rules: Entry[] = asked ? searchEntries(asked) : [];
  const tokens = asked.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 2);
  const mine = asked
    ? files.filter((f) => {
        const label = REQUIRED_DOCS.find((d) => d.id === f.matchedTo)?.label ?? "";
        const hay = `${f.name} ${label}`.toLowerCase();
        return tokens.some((t) => hay.includes(t));
      })
    : [];
  const showRules = filter !== "mine";
  const showMine = filter !== "rules";
  const nothing = asked && (!showRules || rules.length === 0) && (!showMine || mine.length === 0);
  const top = rules[0];

  const tabs: [Filter, string][] = [["all", "All"], ["rules", "Regulations"], ["mine", "My documents"]];

  return (
    <>
      <PageHeader
        title="Search"
        status="Search city and state rules plus your own documents in plain language."
        next="type a question, like how long does approval take."
      />

      <form onSubmit={onSubmit} className="addr-form block">
        <div className="grow">
          <label htmlFor="s">Search question</label>
          <input id="s" className="in full" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Example: What forms does Irvine require?" />
        </div>
        <button className="btn" type="submit" disabled={!query.trim()}>
          Search
        </button>
      </form>

      <div className="actions block" role="group" aria-label="Filter results">
        {tabs.map(([id, label]) => (
          <button key={id} className={filter === id ? "btn" : "btn2"} aria-pressed={filter === id} onClick={() => setFilter(id)}>
            {label}
          </button>
        ))}
      </div>

      {!asked && (
        <section className="card">
          <h2>Try a question</h2>
          <div className="actions">
            {EXAMPLES.map((x) => (
              <button key={x} className="btn2" onClick={() => run(x)}>
                {x}
              </button>
            ))}
          </div>
        </section>
      )}

      {nothing && (
        <section className="card">
          <h2>No results</h2>
          <p>Try different words, or ask the city directly for a specific answer.</p>
          <Link className="btn2" href="/questions">
            Ask the City
          </Link>
        </section>
      )}

      {asked && !nothing && (
        <div className="grid" role="region" aria-label="Search results" aria-live="polite">
          {showRules && top && (
            <section className="card span-all">
              <h2>Best match</h2>
              <p>{top.text}</p>
              <p className="muted">Summary from sample sourced entries. Confirm details in the original source. The AI backend will write answers here.</p>
            </section>
          )}
          {showRules && rules.length > 0 && (
            <section className="card">
              <h2>Regulations and guidance</h2>
              {rules.map((r) => (
                <div className="row" key={r.id}>
                  <span>
                    {r.title}
                    <br />
                    <span className="muted">{r.source}</span>
                  </span>
                  <a href={r.url} target="_blank" rel="noopener noreferrer">
                    Open original
                  </a>
                </div>
              ))}
            </section>
          )}
          {showMine && (
            <section className="card">
              <h2>My documents</h2>
              {mine.length === 0 && <p>No uploaded file names match. Searching inside document text arrives with the OCR backend.</p>}
              {mine.map((f) => (
                <div className="row" key={f.id}>
                  <span>{f.name}</span>
                  <span className={f.matchedTo ? "chip ok" : "chip miss"}>{f.matchedTo ? REQUIRED_DOCS.find((d) => d.id === f.matchedTo)?.label : "Unmatched"}</span>
                </div>
              ))}
            </section>
          )}
        </div>
      )}
    </>
  );
}
