"use client";
import { useRef, useState } from "react";
import { FileQuestion, FileText, Upload, X } from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import { DocId, REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { useNewlyReady } from "@/lib/use-newly-ready";
import { expandUpload, guessMatch, uniqueNames } from "@/lib/document-files";

const SHORT: Record<DocId, string> = {
  site: "Site plan",
  floor: "Floor plans",
  ownership: "Ownership",
  structural: "Structural",
  energy: "Energy report",
  elevations: "Elevations",
};

export default function DocumentsCard() {
  const { files, addFiles, reassign, removeFile, isReady, unmatched, readyCount } = useProject();
  const inputRef = useRef<HTMLInputElement>(null);
  const busyRef = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [drag, setDrag] = useState(false);
  const fresh = useNewlyReady(REQUIRED_DOCS.filter((d) => isReady(d.id)).map((d) => d.id));

  async function handleFiles(list: FileList | null) {
    if (busyRef.current || !list || list.length === 0) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    const selected = Array.from(list);
    try {
      setMessage("Reading filenames locally...");
      const expanded: string[] = [];
      for (const file of selected) expanded.push(...await expandUpload(file));
      const names = uniqueNames(files.map(f => f.name), expanded);
      if (!names.length) setMessage("No new filenames. Duplicates skipped.");
      for (const name of names) {
        addFiles([name]);
        const match = guessMatch(name).matchedTo;
        setMessage(`${name}: ${match ? SHORT[match] : "unmatched"}`);
        await new Promise(resolve => setTimeout(resolve, 300));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to read ZIP filenames.");
      setMessage("Processing stopped. Choose a valid ZIP or PDF/image files.");
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return (
    <div className="docs">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.jpg,.jpeg,.png,.zip"
        disabled={busy}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <button
        type="button"
        className="dz"
        disabled={busy}
        data-drag={drag ? "true" : undefined}
        onClick={() => inputRef.current?.click()}
        onDragEnter={(e) => {
          e.preventDefault();
          if (!busyRef.current) setDrag(true);
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => {
          if (!e.currentTarget.contains(e.relatedTarget as Node)) setDrag(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busyRef.current) void handleFiles(e.dataTransfer.files);
        }}
      >
        <Upload size={18} strokeWidth={1.75} aria-hidden="true" />
        <span>{drag ? "Drop to upload" : <>Drop files or <u>browse</u></>}</span>
      </button>
      <p role="status" aria-live="polite">{readyCount} of 6 documents received. {message}</p>
      {error && <p role="alert">{error}</p>}
      <p>Filename-only demo. No contents uploaded or validated. Matches do not mean city acceptance. Prototype, not legal advice. Consult a professional for decisions.</p>
      <p>Dashboard samples: <a href="/demo/clearpath-dashboard-1-plans.zip" download>First pack: 2 of 6</a>{" · "}
        <a href="/demo/clearpath-dashboard-2-supporting.zip" download>Second pack: 4 of 6 after first</a>{" · "}
        <a href="/demo/clearpath-dashboard-3-final.zip" download>Final pack: 6 of 6 after second</a>{" · "}
        <a href="/demo/clearpath-dashboard-all.zip" download>All six categories + one unmatched</a></p>
      <button type="button" className="select" disabled={busy} onClick={() => {
        if (busyRef.current) return;
        files.forEach(file => removeFile(file.id));
        setMessage("Demo documents reset.");
        setError("");
      }}>Reset demo documents</button>

      {unmatched.length > 0 && (
        <div className="docs-attn" role="status">
          <div className="docs-attn-title num">
            <FileQuestion size={16} strokeWidth={2} aria-hidden="true" /> {unmatched.length} unmatched
          </div>
          {unmatched.map((f) => (
            <div className="doc-row enter" key={f.id}>
              <span className="doc-name" title={f.name}>{f.name}</span>
              <label className="sr-only" htmlFor={`u-${f.id}`}>Assign {f.name} to a document</label>
              <select id={`u-${f.id}`} className="select select-compact doc-select" value="" onChange={(e) => e.target.value && reassign(f.id, e.target.value as DocId)}>
                <option value="">Assign to...</option>
                {REQUIRED_DOCS.map((d) => (
                  <option key={d.id} value={d.id}>{d.label}</option>
                ))}
              </select>
              <button className="icon-btn" aria-label={`Remove ${f.name}`} onClick={() => removeFile(f.id)}>
                <X size={16} strokeWidth={2} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}

      <ul className="doc-list">
        {REQUIRED_DOCS.map((d) => {
          const matched = files.filter((f) => f.matchedTo === d.id);
          const ready = isReady(d.id);
          return (
            <li className={`doc-row${fresh.includes(d.id) ? " flash" : ""}`} key={d.id}>
              <span className={`doc-icon${ready ? " is-ready" : ""}`}>
                <FileText size={18} strokeWidth={1.75} aria-hidden="true" />
              </span>
              <span className="doc-main">
                <span className="doc-label">{SHORT[d.id]}</span>
                {matched.map((f) => (
                  <span className="doc-file" key={f.id}>
                    <span className="doc-name" title={f.name}>{f.name}</span>
                    <label className="sr-only" htmlFor={`m-${f.id}`}>Change match for {f.name}</label>
                    <select id={`m-${f.id}`} className="select-ghost doc-ghost" value={f.matchedTo ?? ""} onChange={(e) => reassign(f.id, (e.target.value || null) as DocId | null)}>
                      {REQUIRED_DOCS.map((o) => (
                        <option key={o.id} value={o.id}>{o.label}</option>
                      ))}
                      <option value="">Not required</option>
                    </select>
                  </span>
                ))}
              </span>
              <StatusBadge status={ready ? "ready" : d.priority ? "missing" : "todo"} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
