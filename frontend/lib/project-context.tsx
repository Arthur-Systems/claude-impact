"use client";
// Shared project state. Every page reads from here, so uploading a file on
// the Documents page instantly updates the Overview and the nav badge.
import { createContext, useContext, useMemo, useState, ReactNode } from "react";
import type { Place } from "./geocode";
import { guessMatch, uniqueNames } from "./document-files";

export type DocId = "site" | "floor" | "ownership" | "structural" | "energy" | "elevations";

export type RequiredDoc = { id: DocId; label: string; priority: boolean };

// The checklist for a detached ADU. Later this comes from the backend.
export const REQUIRED_DOCS: RequiredDoc[] = [
  { id: "site", label: "Site plan", priority: true },
  { id: "floor", label: "Floor plans", priority: true },
  { id: "ownership", label: "Proof of ownership", priority: true },
  { id: "structural", label: "Structural calculations", priority: true },
  { id: "energy", label: "Energy compliance report", priority: true },
  { id: "elevations", label: "Elevations", priority: false },
];

export type UploadedFile = {
  id: string;
  name: string;
  matchedTo: DocId | null; // null = unmatched, user must act
  confidence: "high" | "low" | "none";
};

export type Thread = {
  id: string;
  topic: string;
  message: string;
  status: "emailed" | "answered";
  sentAt: string;
};

type Ctx = {
  files: UploadedFile[];
  addFiles: (names: string[]) => void;
  reassign: (fileId: string, docId: DocId | null) => void;
  removeFile: (fileId: string) => void;
  isReady: (id: DocId) => boolean;
  missingPriority: RequiredDoc[];
  readyCount: number;
  unmatched: UploadedFile[];
  place: Place | null;
  setPlace: (p: Place | null) => void;
  prepDays: number;
  setPrepDays: (d: number) => void;
  threads: Thread[];
  addThread: (t: Omit<Thread, "id" | "sentAt" | "status">) => void;
  markAnswered: (id: string) => void;
};

const ProjectContext = createContext<Ctx | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [place, setPlace] = useState<Place | null>(null);
  const [prepDays, setPrepDays] = useState(14);
  const [threads, setThreads] = useState<Thread[]>([]);

  const value = useMemo<Ctx>(() => {
    const isReady = (id: DocId) => files.some((f) => f.matchedTo === id);
    return {
      files,
      addFiles: (names) =>
        setFiles((prev) => [
          ...prev,
          ...uniqueNames(prev.map(f => f.name), names).map((name) => ({ id: crypto.randomUUID(), name, ...guessMatch(name) })),
        ]),
      reassign: (fileId, docId) =>
        setFiles((prev) =>
          prev.map((f) =>
            f.id === fileId ? { ...f, matchedTo: docId, confidence: docId ? "high" : "none" } : f
          )
        ),
      removeFile: (fileId) => setFiles((prev) => prev.filter((f) => f.id !== fileId)),
      isReady,
      missingPriority: REQUIRED_DOCS.filter((d) => d.priority && !isReady(d.id)),
      readyCount: REQUIRED_DOCS.filter((d) => isReady(d.id)).length,
      unmatched: files.filter((f) => f.matchedTo === null),
      place,
      setPlace,
      prepDays,
      setPrepDays,
      threads,
      addThread: (t) =>
        setThreads((prev) => [
          { ...t, id: crypto.randomUUID(), status: "emailed", sentAt: new Date().toLocaleDateString() },
          ...prev,
        ]),
      markAnswered: (id) => setThreads((prev) => prev.map((t) => (t.id === id ? { ...t, status: "answered" } : t))),
    };
  }, [files, place, prepDays, threads]);

  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject() {
  const ctx = useContext(ProjectContext);
  if (!ctx) throw new Error("useProject must be used inside ProjectProvider");
  return ctx;
}
