"use client";
import { useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import StatusBadge from "@/components/StatusBadge";
import { DocId, REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { useNewlyReady } from "@/lib/use-newly-ready";

export default function Documents() {
  const { files, addFiles, reassign, removeFile, isReady, unmatched } = useProject();
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [drag, setDrag] = useState(false);
  const fresh = useNewlyReady(REQUIRED_DOCS.filter((d) => isReady(d.id)).map((d) => d.id));

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    const names = Array.from(list).map((f) => f.name);
    addFiles(names);
    setMessage(`${names.length} file${names.length > 1 ? "s" : ""} added.`);
  }

  return (
    <>
      <PageHeader title="Documents" subtitle="Upload what you have. We match each file." />

      <input
        ref={inputRef}
        id="file-input"
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png"
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <div
        className="dropzone"
        data-drag={drag ? "true" : undefined}
        onDragEnter={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setDrag(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <p>{drag ? "Drop to upload" : "Drag files here, or"}</p>
        <button className="btn btn-primary" onClick={() => inputRef.current?.click()}>
          Choose files
        </button>
        <p className="hint">PDF, JPG, or PNG. Scanned files are fine.</p>
        <p role="status" className="hint">
          {message}
        </p>
      </div>

      {unmatched.length > 0 && (
        <>
          <div className="notice notice-error" role="status">
            <p>
              <b className="num">{unmatched.length}</b> file{unmatched.length > 1 ? "s" : ""} did not match a required document.
            </p>
          </div>
          <section className="card" style={{ marginBottom: "var(--space-5)" }}>
            <h2>Needs your attention</h2>
            <div className="list">
              {unmatched.map((f, i) => (
                <div className="row enter" style={{ ["--i" as string]: Math.min(i, 4) }} key={f.id}>
                  <span className="row-main">
                    <b>{f.name}</b>
                    <span className="row-sub">Does not match any required document.</span>
                  </span>
                  <span className="row-end">
                    <label className="sr-only" htmlFor={`u-${f.id}`}>
                      Assign {f.name} to a document
                    </label>
                    <select id={`u-${f.id}`} className="select select-compact" value="" onChange={(e) => e.target.value && reassign(f.id, e.target.value as DocId)}>
                      <option value="">Assign to...</option>
                      {REQUIRED_DOCS.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                    <button className="btn btn-secondary" onClick={() => removeFile(f.id)}>
                      Remove file
                    </button>
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Required checklist</h2>
          <span className="muted">Matched files appear in their row. You can change a match.</span>
        </div>
        <div className="list">
          {REQUIRED_DOCS.map((d) => {
            const matched = files.filter((f) => f.matchedTo === d.id);
            return (
              <div className={`row${fresh.includes(d.id) ? " flash" : ""}`} key={d.id}>
                <span className="row-main">
                  <span>{d.label}</span>
                  {matched.map((f) => (
                    <span className="row-sub file-tag enter" key={f.id}>
                      {f.name}
                      <label className="sr-only" htmlFor={`m-${f.id}`}>
                        Change match for {f.name}
                      </label>
                      <select id={`m-${f.id}`} className="select select-compact" value={f.matchedTo ?? ""} onChange={(e) => reassign(f.id, (e.target.value || null) as DocId | null)}>
                        {REQUIRED_DOCS.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.label}
                          </option>
                        ))}
                        <option value="">Not a required document</option>
                      </select>
                    </span>
                  ))}
                </span>
                <StatusBadge status={isReady(d.id) ? "ready" : d.priority ? "missing" : "todo"} />
              </div>
            );
          })}
        </div>
      </section>
    </>
  );
}
