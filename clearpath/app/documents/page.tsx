"use client";
import { useEffect, useRef, useState } from "react";
import PageHeader from "@/components/PageHeader";
import { DataBanner, SourceChip } from "@/components/LiveData";
import {
  PermitLookup,
  backendConfigured,
  clearStoredProjectId,
  ensureProject,
  markRequirementReady,
  permitLookup,
  readStoredProjectId,
} from "@/lib/backend";
import { DocId, REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { listZipEntries } from "@/lib/zip";
import { matchRequirement } from "@/lib/docmatch";
import { clearReceipts, loadReceipts, saveReceipts, type Receipts } from "@/lib/receipts";
const STEP_MS = 350;
const SAMPLE_ZIPS = [
  { href: "/demo/clearpath-demo-1-application.zip", label: "1. Application forms (3 files)" },
  { href: "/demo/clearpath-demo-2-plans-and-forms.zip", label: "2. Plans and agency forms (4 files plus site photos)" },
  { href: "/demo/clearpath-demo-3-final.zip", label: "3. Final forms and affidavit (3 files)" },
  { href: "/demo/clearpath-demo-all.zip", label: "All sample documents in one ZIP" },
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

// Expands .zip uploads to their entry names; other files keep their own name.
async function expandNames(list: File[]): Promise<string[]> {
  const out: string[] = [];
  for (const f of list) {
    if (f.name.toLowerCase().endsWith(".zip")) {
      out.push(...listZipEntries(await f.arrayBuffer()));
    } else out.push(f.name);
  }
  return out;
}

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
  const [received, setReceived] = useState<Record<string, string>>({});
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [localOnly, setLocalOnly] = useState(false);
  const projectRef = useRef<{ id: string; revision: number } | null>(null);
  const scopeRef = useRef<string | null>(null);
  const receiptsRef = useRef<Receipts>({ files: {}, unsaved: [] });
  const busyRef = useRef(false);

  function showReceipts(scope: string, value: Receipts) {
    scopeRef.current = scope;
    receiptsRef.current = value;
    saveReceipts(scope, value);
    setReceived(value.files);
    setLocalOnly(value.unsaved.length > 0);
  }

  useEffect(() => {
    if (!backendConfigured()) return;
    let active = true;
    Promise.all([permitLookup(), ensureProject()]).then(([lookup, project]) => {
      if (!active) return;
      setLive(lookup?.requirements?.length ? lookup : null);
      // A failed lookup (or unavailable coverage) cannot invalidate local receipts.
      if (!lookup?.requirements?.length) {
        setLoading(false);
        return;
      }
      const scope = project?.id ?? readStoredProjectId() ?? "browser-only";
      const stored = loadReceipts(scope);
      const allowed = new Set(lookup?.requirements.map((r) => r.key) ?? []);
      const files = Object.fromEntries(Object.entries(stored.files).filter(([key]) => allowed.has(key)));
      const unsaved = new Set(stored.unsaved.filter((key) => allowed.has(key)));
      for (const item of project?.checklist ?? []) {
        if (item.status === "ready" && allowed.has(item.key)) {
          files[item.key] ||= "saved earlier";
          unsaved.delete(item.key);
        }
      }
      projectRef.current = project ? { id: project.id, revision: project.revision } : null;
      showReceipts(scope, { files, unsaved: [...unsaved] });
      if (!project && Object.keys(files).length) setLocalOnly(true);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);
  const matched = files.filter((f) => f.matchedTo !== null);

  async function handleFiles(list: FileList | null) {
    if (!list?.length || busyRef.current || loading) return;
    busyRef.current = true;
    setBusy(true);
    try {
      const names = await expandNames(Array.from(list));
      if (!names.length) throw new Error("No files found in that upload.");
      setMessage(`${names.length} file${names.length > 1 ? "s" : ""} added. Filename matching only.`);
      if (!live) { addFiles(names); return; }
      if (!projectRef.current) {
        const project = await ensureProject();
        if (project) {
          projectRef.current = { id: project.id, revision: project.revision };
          if (scopeRef.current !== project.id) showReceipts(project.id, loadReceipts(project.id));
        }
      }
      const scope = scopeRef.current ?? readStoredProjectId() ?? "browser-only";
      const reqs = live.requirements.map((r) => ({ key: r.key, title: r.title }));
      for (const name of names) {
        const key = matchRequirement(name, reqs);
        if (!key) {
          setLog((lines) => [...lines, `? ${name}: unmatched, kept aside`]);
        } else {
          const previous = receiptsRef.current;
          const value = { files: { ...previous.files, [key]: name }, unsaved: [...new Set([...previous.unsaved, key])] };
          showReceipts(scope, value);
          setLog((lines) => [...lines, `✓ ${name}: ${reqs.find((r) => r.key === key)?.title} received (filename only)`]);
          const project = projectRef.current;
          const updated = project ? await markRequirementReady(project.id, key, project.revision) : null;
          if (updated) {
            projectRef.current = { id: updated.id, revision: updated.revision };
            showReceipts(scope, { ...value, unsaved: value.unsaved.filter((item) => item !== key) });
          }
        }
        await sleep(STEP_MS);
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not read that upload. Choose a standard ZIP or individual PDF.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  function resetDemo() {
    if (busyRef.current || loading) return;
    if (scopeRef.current) clearReceipts(scopeRef.current);
    receiptsRef.current = { files: {}, unsaved: [] };
    scopeRef.current = null;
    setReceived({});
    for (const file of files) removeFile(file.id);
    setLog([]);
    setLocalOnly(false);
    setMessage("Demo reset. A new project will be created next time. Old project history is unchanged.");
    projectRef.current = null;
    clearStoredProjectId();
  }

  const liveTotal = live ? live.requirements.length : 0;
  const liveDone = live ? live.requirements.filter((r) => received[r.key]).length : 0;

  const labelFor = (id: DocId | null) => REQUIRED_DOCS.find((d) => d.id === id)?.label ?? "";

  return (
    <>
      <PageHeader
        title="Documents"
        status={live ? `${liveDone} of ${liveTotal} documents received by filename. Contents are not validated.` : "Demo upload: filenames are matched to a mock checklist."}
        next={
          loading ? "wait for the current checklist."
          : live ? (liveDone < liveTotal ? `add the remaining ${liveTotal - liveDone} checklist documents.` : "review source conflicts and Unknown items with a professional. Receipt is not city acceptance.")
          : missingPriority.length > 0
            ? `upload your files, then add the ${missingPriority.length} priority documents.`
            : "review the mock matches. No document contents have been validated."
        }
        action={
          <button className="btn" disabled={busy || loading} onClick={() => inputRef.current?.click()}>
            Upload files
          </button>
        }
      />

      <DataBanner live={live !== null} loading={loading} />

      <section className="card block">
        <h2>Upload documents</h2>
        <p className="muted">PDF, JPG, PNG, or a standard ZIP. Use fictional sample documents only.</p>
        <p className="muted">
          <b>Demo feature:</b> Received means filename-matched, not valid, complete, or city accepted. ZIP directory names are read locally; document contents are not inspected or uploaded. Only checklist receipt status is sent to the API.
        </p>
        <input
          ref={inputRef}
          id="file-input"
          type="file"
          multiple
          accept=".zip,.pdf,.jpg,.jpeg,.png"
          className="sr-only"
          disabled={busy || loading}
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = "";
          }}
        />
        <button
          className="btn2 dropzone"
          disabled={busy || loading}
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
        {live && (
          <>
            <p>
              <b>
                {liveDone} of {liveTotal} documents received
              </b>
              {busy ? " (processing...)" : ""}
            </p>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={liveTotal}
              aria-valuenow={liveDone}
              style={{ height: 8, borderRadius: 4, background: "rgba(127,127,127,0.25)", overflow: "hidden" }}
            >
              <div style={{ width: `${liveTotal ? (liveDone / liveTotal) * 100 : 0}%`, height: "100%", background: "currentColor", transition: "width 0.3s" }} />
            </div>
            {localOnly && <p className="muted">Saved in this browser only. The ClearPath API could not be updated.</p>}
            {log.length > 0 && (
              <div aria-live="polite" id="activity-log">
                <h2>Activity</h2>
                {log.map((line, i) => (
                  <p className="muted" key={i} style={{ margin: "2px 0" }}>
                    {line}
                  </p>
                ))}
              </div>
            )}
          </>
        )}
        <h2>Sample documents (fictional)</h2>
        <p className="muted">One-page made-up PDFs for trying the upload. Download a ZIP, then upload it above.</p>
        <ul>
          {SAMPLE_ZIPS.map((z) => (
            <li key={z.href}>
              <a href={z.href} download>
                {z.label}
              </a>
            </li>
          ))}
        </ul>
        <button className="btn2" onClick={resetDemo} disabled={busy || loading}>
          Reset demo
        </button>
        <p className="muted">Prototype. Not legal advice.</p>
      </section>

      <div className="grid">
        {!live && !loading && <>
        <section className="card">
          <h2>Matched automatically (mock checklist)</h2>
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
        </>}

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
                <span className="actions">
                  {received[req.key] ? (
                    <span className="chip ok" title={received[req.key]}>
                      Received: {received[req.key]}
                    </span>
                  ) : (
                    <span className="chip miss">Missing</span>
                  )}
                  {req.status === "needs_information" && <StatusChip status={req.status} />}
                </span>
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

        {!live && !loading && <section className="card span-all">
          <h2>Required checklist (mock)</h2>
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
        </section>}
      </div>
    </>
  );
}
