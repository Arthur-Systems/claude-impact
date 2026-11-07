"use client";
import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { DataBanner, SourceChip } from "@/components/LiveData";
import { PermitLookup, backendConfigured, permitLookup } from "@/lib/backend";
import { DocId, REQUIRED_DOCS, useProject } from "@/lib/project-context";

function StatusChip({ status }: { status: string }) {
  if (status === "applies") return <span className="chip ok">Applies</span>;
  if (status === "not_applicable") return <span className="chip todo">Not applicable</span>;
  return <span className="chip miss">Unknown (needs information)</span>;
}

export default function Documents() {
  const { files, addFiles, reassign, removeFile, isReady, missingPriority, unmatched } = useProject();
  const inputRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState("");
  const [live, setLive] = useState<PermitLookup | null>(null);
  const [loading, setLoading] = useState(backendConfigured());
  useEffect(() => {
    if (!backendConfigured()) return;
    permitLookup().then((r) => {
      setLive(r && r.requirements?.length ? r : null);
      setLoading(false);
    });
  }, []);
  const matched = files.filter((f) => f.matchedTo !== null);

  function handleFiles(list: FileList | null) {
    if (!list || list.length === 0) return;
    const names = Array.from(list).map((f) => f.name);
    addFiles(names);
    setMessage(`${names.length} file${names.length > 1 ? "s" : ""} added.`);
  }

  const labelFor = (id: DocId | null) => REQUIRED_DOCS.find((d) => d.id === id)?.label ?? "";

  return (
    <>
      <PageHeader
        title="Documents"
        status="Upload anything you have. We match each file to a required document and flag what does not fit."
        next={
          missingPriority.length > 0
            ? `upload your files, then add the ${missingPriority.length} priority documents.`
            : "all required documents are in. Review any matches you are unsure about."
        }
        action={
          <button className="btn" onClick={() => inputRef.current?.click()}>
            Upload files
          </button>
        }
      />

      <DataBanner live={live !== null} loading={loading} />

      <section className="card block">
        <h2>Upload documents</h2>
        <p className="muted">PDF, JPG, or PNG. Scanned files are fine.</p>
        <p className="muted">
          <b>Demo feature:</b> file matching below uses the file name only (mock). Files are not read or sent anywhere.
        </p>
        <input
          ref={inputRef}
          id="file-input"
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png"
          className="sr-only"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          className="btn2 dropzone"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            handleFiles(e.dataTransfer.files);
          }}
        >
          Choose files or drag them here
        </button>
        <p role="status" className="muted">
          {message}
        </p>
      </section>

      <div className="grid">
        <section className="card">
          <h2>Matched automatically</h2>
          <p className="muted">Check each match. You can change it.</p>
          {matched.length === 0 && <p>No files yet. Upload a file to see it matched here.</p>}
          {matched.map((f) => (
            <div className="row" key={f.id}>
              <span>
                {f.name}
                <br />
                <span className="muted">Matched to {labelFor(f.matchedTo)}</span>
              </span>
              <span className="actions">
                <span className="chip ok">High match</span>
                <label className="sr-only" htmlFor={`m-${f.id}`}>
                  Change match for {f.name}
                </label>
                <select id={`m-${f.id}`} className="in small" value={f.matchedTo ?? ""} onChange={(e) => reassign(f.id, (e.target.value || null) as DocId | null)}>
                  {REQUIRED_DOCS.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                  <option value="">Not a required document</option>
                </select>
              </span>
            </div>
          ))}
        </section>

        <section className={`card ${unmatched.length ? "warn" : ""}`}>
          <h2>Needs your attention</h2>
          {unmatched.length === 0 && <p>Nothing to fix. Files we cannot match will show up here.</p>}
          {unmatched.map((f) => (
            <div className="row" key={f.id}>
              <span>
                <b>{f.name}</b>
                <br />
                <span className="muted">Does not match any required document.</span>
              </span>
              <span className="actions">
                <span className="chip miss">Unmatched</span>
                <label className="sr-only" htmlFor={`u-${f.id}`}>
                  Assign {f.name} to a document
                </label>
                <select id={`u-${f.id}`} className="in small" value="" onChange={(e) => e.target.value && reassign(f.id, e.target.value as DocId)}>
                  <option value="">Assign to...</option>
                  {REQUIRED_DOCS.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.label}
                    </option>
                  ))}
                </select>
                <button className="btn2" onClick={() => removeFile(f.id)}>
                  Remove file
                </button>
              </span>
            </div>
          ))}
        </section>

        {live && (
          <section className="card span-all">
            <h2>Irvine checklist from the ClearPath API</h2>
            <p className="muted">
              Detached ADU on a lot with an existing house, City of Irvine (selected area, no specific property checked). {live.notice}
            </p>
            {live.requirements.map((req) => (
              <div className="row" key={req.key}>
                <span>
                  <b>{req.title}</b> <span className="muted">({req.kind})</span>
                  <br />
                  <span className="muted">{req.description}</span>
                  {req.status === "needs_information" && (
                    <>
                      <br />
                      <span className="muted">
                        Unknown:{" "}
                        {req.missing_fact_keys.length
                          ? `missing ${req.missing_fact_keys.join(", ")}`
                          : req.conflict_ids.length
                          ? "official sources disagree"
                          : "more information needed"}
                        .
                      </span>
                    </>
                  )}
                  {req.citations.map((c, i) => (
                    <SourceChip key={i} c={c} />
                  ))}
                </span>
                <StatusChip status={req.status} />
              </div>
            ))}
            {live.conflicts?.length > 0 && (
              <>
                <h2>Source conflicts</h2>
                {live.conflicts.map((c) => (
                  <p className="muted" key={c.id}>
                    {c.summary} <b>{c.effect}</b>
                  </p>
                ))}
              </>
            )}
          </section>
        )}

        <section className="card span-all">
          <h2>{live ? "Upload checklist (demo, matched by file name)" : "Required checklist"}</h2>
          {REQUIRED_DOCS.map((d) => (
            <div className="row" key={d.id}>
              <span>{d.label}</span>
              {isReady(d.id) ? (
                <span className="chip ok">Ready</span>
              ) : d.priority ? (
                <span className="chip pri">Priority: missing</span>
              ) : (
                <span className="chip todo">Not started</span>
              )}
            </div>
          ))}
        </section>
      </div>
    </>
  );
}
