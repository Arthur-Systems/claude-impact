"use client";
import { useRef, useState } from "react";
import { FileQuestion, FileText, Upload, X } from "lucide-react";
import StatusBadge from "@/components/StatusBadge";
import { DocId, REQUIRED_DOCS, useProject } from "@/lib/project-context";
import { useNewlyReady } from "@/lib/use-newly-ready";

const SHORT: Record<DocId, string> = {
  site: "Site plan",
  floor: "Floor plans",
  ownership: "Ownership",
  structural: "Structural",
  energy: "Energy report",
  elevations: "Elevations",
};

export default function DocumentsCard() {
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
    <div className="docs">
      <input
        ref={inputRef}
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
      <button
        type="button"
        className="dz"
        data-drag={drag ? "true" : undefined}
        onClick={() => inputRef.current?.click()}
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
        <Upload size={18} strokeWidth={1.75} aria-hidden="true" />
        <span>{drag ? "Drop to upload" : <>Drop files or <u>browse</u></>}</span>
      </button>
      <p role="status" className="sr-only">{message}</p>

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
