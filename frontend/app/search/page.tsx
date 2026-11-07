"use client";
import { FormEvent, KeyboardEvent, useState } from "react";
import Link from "next/link";
import PageHeader from "@/components/PageHeader";
import { Entry, searchEntries } from "@/lib/knowledge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";

type Filter = "all" | "rules" | "mine";
const EXAMPLES = ["How long does approval take?", "What forms does Irvine require?", "Where do I submit?"];
const TABS: [Filter, string][] = [["all", "All"], ["rules", "Regulations"], ["mine", "My documents"]];

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
  function onRadioKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = TABS.findIndex(([id]) => id === filter);
    let n = i;
    if (e.key === "ArrowRight" || e.key === "ArrowDown") n = (i + 1) % TABS.length;
    else if (e.key === "ArrowLeft" || e.key === "ArrowUp") n = (i + TABS.length - 1) % TABS.length;
    else return;
    e.preventDefault();
    setFilter(TABS[n][0]);
    (e.currentTarget.querySelectorAll("button")[n] as HTMLButtonElement | undefined)?.focus();
  }

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
  const both = showRules && rules.length > 0 && showMine;

  return (
    <>
      <PageHeader title="Search" subtitle="Search city and state rules and your own documents in plain language." />

      <form onSubmit={onSubmit} className="inline-form search-hero" role="search">
        <div className="grow">
          <label htmlFor="s" className="sr-only">
            Search question
          </label>
          <input id="s" className="input" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="What forms does Irvine require?" />
        </div>
        <button className="btn btn-primary" type="submit" disabled={!query.trim()}>
          Search
        </button>
      </form>

      <div className="segmented" role="radiogroup" aria-label="Filter results" onKeyDown={onRadioKey}>
        {TABS.map(([id, label]) => (
          <button key={id} type="button" role="radio" aria-checked={filter === id} tabIndex={filter === id ? 0 : -1} onClick={() => setFilter(id)}>
            {label}
          </button>
        ))}
      </div>

      {!asked && (
        <div className="chips" aria-label="Example questions">
          {EXAMPLES.map((x) => (
            <button key={x} className="btn btn-secondary chip" onClick={() => run(x)}>
              {x}
            </button>
          ))}
        </div>
      )}

      {nothing && (
        <div className="empty">
          <p>No results. Try different words, or ask the city for a specific answer.</p>
          <Link className="btn btn-secondary" href="/questions">
            Ask the City
          </Link>
        </div>
      )}

      {asked && !nothing && (
        <div className="grid grid-top" role="region" aria-label="Search results" aria-live="polite">
          {showRules && top && (
            <section className="card col-12 enter">
              <h2>Best match</h2>
              <p>{top.text}</p>
              <p className="muted" style={{ margin: 0 }}>
                Summary from sample sourced entries. Confirm details in the original source. The AI backend will write answers here.
              </p>
            </section>
          )}
          {showRules && rules.length > 0 && (
            <section className={`card enter ${both ? "col-7" : "col-12"}`} style={{ ["--i" as string]: 1 }}>
              <h2>Regulations and guidance</h2>
              <div className="list">
                {rules.map((r) => (
                  <div className="row" key={r.id}>
                    <span className="row-main">
                      <span>{r.title}</span>
                      <span className="row-sub">{r.source}</span>
                    </span>
                    <a href={r.url} target="_blank" rel="noopener noreferrer">
                      Open original
                    </a>
                  </div>
                ))}
              </div>
            </section>
          )}
          {showMine && (
            <section className={`card enter ${both ? "col-5" : "col-12"}`} style={{ ["--i" as string]: 2 }}>
              <h2>My documents</h2>
              {mine.length === 0 && <p className="muted" style={{ margin: 0 }}>No uploaded file names match. Searching inside document text arrives with the OCR backend.</p>}
              <div className="list">
                {mine.map((f) => (
                  <div className="row" key={f.id}>
                    <span className="row-main">{f.name}</span>
                    <span className={f.matchedTo ? "badge badge-done" : "badge badge-next"}>{f.matchedTo ? REQUIRED_DOCS.find((d) => d.id === f.matchedTo)?.label : "Unmatched"}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      )}
    </>
  );
}
