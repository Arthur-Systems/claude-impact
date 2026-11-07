"use client";
import { KeyboardEvent, useEffect, useId, useMemo, useRef, useState } from "react";
import { Search, Scale, FileText, X } from "lucide-react";
import { searchEntries } from "@/lib/knowledge";
import { REQUIRED_DOCS, useProject } from "@/lib/project-context";
import s from "./panels.module.css";

type Filter = "all" | "rules" | "mine";
const EXAMPLES = ["How long does approval take?", "What forms does Irvine require?", "Where do I submit?", "Fees"];
const TABS: [Filter, string][] = [["all", "All"], ["rules", "Regulations"], ["mine", "My documents"]];
type Row = { id: string; kind: "rule" | "mine"; title: string; badge: string; url: string | null };

export default function CommandSearch() {
  const { files } = useProject();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const lid = useId();

  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        // Only the first visible instance responds, in case two are mounted.
        const first = Array.from(document.querySelectorAll<HTMLElement>("[data-cmdsearch]")).find((n) => n.offsetParent !== null);
        if (first && first !== wrapRef.current) return;
        e.preventDefault();
        setExpanded(true);
        setOpen(true);
        setTimeout(() => inputRef.current?.focus(), 0);
      }
    };
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
        setExpanded(false);
      }
    };
    window.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, []);

  const asked = q.trim();
  const rows: Row[] = useMemo(() => {
    if (!asked) return [];
    const rules: Row[] = searchEntries(asked).map((e) => ({ id: e.id, kind: "rule", title: e.title, badge: e.source, url: e.url }));
    const tokens = asked.toLowerCase().split(/[^a-z0-9]+/).filter((t) => t.length > 2);
    const mine: Row[] = files
      .filter((f) => {
        const label = REQUIRED_DOCS.find((d) => d.id === f.matchedTo)?.label ?? "";
        return tokens.some((t) => `${f.name} ${label}`.toLowerCase().includes(t));
      })
      .map((f) => ({ id: f.id, kind: "mine", title: f.name, badge: REQUIRED_DOCS.find((d) => d.id === f.matchedTo)?.label ?? "Unmatched", url: null }));
    return [...(filter !== "mine" ? rules : []), ...(filter !== "rules" ? mine : [])].slice(0, 8);
  }, [asked, files, filter]);

  useEffect(() => setActive(0), [asked, filter]);

  function openRow(r: Row | undefined) {
    if (r?.url) window.open(r.url, "_blank", "noopener,noreferrer");
  }
  function focusField() {
    setExpanded(true);
    setOpen(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }
  function onKey(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      setQ("");
      setOpen(false);
      setExpanded(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      if (rows.length) setActive((a) => (a + 1) % rows.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (rows.length) setActive((a) => (a + rows.length - 1) % rows.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      openRow(rows[active]);
    }
  }

  const optId = (i: number) => `${lid}-o${i}`;

  return (
    <div ref={wrapRef} data-cmdsearch="" className={`${s.search} ${expanded ? s.searchOpen : ""}`}>
      <button type="button" className={s.searchToggle} aria-label="Search" onClick={focusField}>
        <Search size={18} strokeWidth={2} aria-hidden="true" />
      </button>
      <div className={s.field} role="search">
        <Search size={16} strokeWidth={2} className={s.fieldIcon} aria-hidden="true" />
        <input
          ref={inputRef}
          className={s.searchInput}
          type="text"
          role="combobox"
          aria-label="Search rules and documents"
          aria-expanded={open}
          aria-controls={lid}
          aria-autocomplete="list"
          aria-activedescendant={open && rows.length ? optId(active) : undefined}
          placeholder="Search rules, docs"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKey}
          autoComplete="off"
        />
        {q ? (
          <button type="button" className={s.clear} aria-label="Clear search" onClick={() => { setQ(""); inputRef.current?.focus(); }}>
            <X size={14} strokeWidth={2} aria-hidden="true" />
          </button>
        ) : (
          <kbd className={s.kbd}>⌘K</kbd>
        )}
      </div>
      {open && (
        <div className={s.pop}>
          <div className={s.seg} role="radiogroup" aria-label="Filter results">
            {TABS.map(([id, label]) => (
              <button key={id} type="button" role="radio" aria-checked={filter === id} onMouseDown={(e) => e.preventDefault()} onClick={() => setFilter(id)}>
                {label}
              </button>
            ))}
          </div>
          {!asked ? (
            <div className={s.examples} aria-label="Example searches">
              {EXAMPLES.map((x) => (
                <button key={x} type="button" className={s.chip} onMouseDown={(e) => e.preventDefault()} onClick={() => setQ(x)}>
                  {x}
                </button>
              ))}
            </div>
          ) : rows.length === 0 ? (
            <p className={s.empty}>No results. Try other words or ask the city.</p>
          ) : null}
          <ul id={lid} role="listbox" aria-label="Search results" className={s.list}>
            {rows.map((r, i) => {
              const Icon = r.kind === "rule" ? Scale : FileText;
              return (
                <li
                  key={r.id}
                  id={optId(i)}
                  role="option"
                  aria-selected={i === active}
                  className={s.opt}
                  onMouseEnter={() => setActive(i)}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => openRow(r)}
                >
                  <Icon size={16} strokeWidth={1.75} aria-hidden="true" className={s.optIcon} />
                  <span className={s.optTitle}>{r.title}</span>
                  <span className={r.kind === "mine" ? (r.badge === "Unmatched" ? "badge badge-next" : "badge badge-done") : "badge"}>{r.badge}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
