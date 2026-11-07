// Typed client for the ClearPath FastAPI backend (/api/v1).
// Reads NEXT_PUBLIC_API_URL and NEXT_PUBLIC_API_KEY. Every request sends X-API-Key.
// Any failure (env unset, network, non-2xx) returns null so pages fall back to mock data.

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? "";

export const backendConfigured = () => API_URL !== "" && API_KEY !== "";

export type Citation = {
  source_key: string;
  url: string;
  title: string;
  locator?: string | null;
  checked_at: string;
  excerpt: string;
  publisher?: string | null;
};

export type ReqStatus = "applies" | "needs_information" | "not_applicable" | string;

export type Requirement = {
  key: string;
  kind: string;
  title: string;
  description: string;
  status: ReqStatus;
  status_reason: string | null;
  missing_fact_keys: string[];
  conflict_ids: string[];
  required_for_preparation: boolean;
  citations: Citation[];
};

export type Conflict = { id: string; summary: string; effect: string; source_keys: string[] };

export type PermitLookup = {
  dataset_mode: string;
  status: string;
  notice: string;
  profile_key: string | null;
  pathways: { key: string; title: string; status: string; citations: Citation[] }[];
  requirements: Requirement[];
  conflicts: Conflict[];
  warnings: { code: string; message: string }[];
};

export type Facts = Record<string, string | number | boolean>;

export type TimingValue = { min_days?: number | null; max_days?: number | null; label?: string; rationale?: string } | null;

export type Milestone = {
  key: string;
  title: string;
  predecessor_keys: string[];
  requirement_keys: string[];
  state: string;
  availability: string;
  started_at: string | null;
  completed_at: string | null;
  blocked_by: { kind: string; key: string }[];
  timing: {
    city_service_target: TimingValue;
    statutory_clock: TimingValue;
    observed: TimingValue;
    assumption: TimingValue;
  };
  forecast_finish: { earliest: string; latest: string; label: string } | null;
  citation_ids: string[];
};

export type TimelineCitation = Citation & { id: string };

export type Timeline = {
  project_id: string;
  status: string;
  as_of: string;
  pathway: { key: string; title: string; citation_ids: string[] } | null;
  progress: { completed: number; total: number; percent: number } | null;
  document_readiness: { ready: number; applicable: number; needs_information: number; denominator: number; percent: number } | null;
  next_actions: { milestone_key: string; event_kind: string; title: string; citation_ids: string[] }[];
  bottlenecks: { code: string; milestone_key: string | null; requirement_keys: string[]; message: string; since: string | null }[];
  milestones: Milestone[];
  forecast: { label: string; status: string; finish_range: { earliest: string; latest: string } | null; disclaimer: string } | null;
  citations: TimelineCitation[];
  warnings: { code: string; message: string }[];
};

async function request<T>(method: string, path: string, body?: unknown, onError?: (status: number) => void): Promise<T | null> {
  if (!backendConfigured()) return null;
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method,
      headers: {
        "X-API-Key": API_KEY,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    if (!res.ok) { onError?.(res.status); return null; }
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

// Demo case C01: detached ADU on a lot with an existing house, Irvine selected area.
export const DEMO_FACTS: Facts = { adu_form: "detached", existing_dwelling: true };
export const DEMO_PROFILE_KEY = "irvine-adu-detached-existing-dwelling";

export function permitLookup(facts: Facts = DEMO_FACTS): Promise<PermitLookup | null> {
  return request<PermitLookup>("POST", "/api/v1/permit-lookups", {
    location: { selected_area: { jurisdiction: "irvine-ca" } },
    project_type: "adu",
    profile_key: DEMO_PROFILE_KEY,
    facts,
  });
}

export async function createAndActivateProject(facts: Facts = DEMO_FACTS, label = "Backyard ADU demo"): Promise<string | null> {
  const created = await request<{ id: string; revision: number }>("POST", "/api/v1/projects", {
    project_label: label,
    project_type: "adu",
    subtype: "detached_adu_existing_dwelling",
    jurisdiction: "irvine-ca",
    declared_location: { mode: "selected_area", area_key: "irvine-ca-citywide" },
    proposed_unit_count: 1,
    affordability_goal: "unspecified",
    rule_facts: facts,
  });
  if (!created) return null;
  const activated = await request<{ id: string }>("POST", `/api/v1/projects/${created.id}/activate`, {
    pathway_key: "irvine_adu_standard",
    expected_revision: created.revision,
  });
  return activated ? created.id : null;
}

export function getTimeline(id: string, asOf?: string): Promise<Timeline | null> {
  const q = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return request<Timeline>("GET", `/api/v1/projects/${encodeURIComponent(id)}/timeline${q}`);
}

export const PROJECT_KEY = "clearpath.projectId";

export type ProjectChecklistItem = { key: string; title: string; status: string; applicability?: string };
export type Project = { id: string; revision: number; state: string; checklist: ProjectChecklistItem[] };

export function getProject(id: string): Promise<Project | null> {
  return request<Project>("GET", `/api/v1/projects/${encodeURIComponent(id)}`);
}

export function readStoredProjectId(): string | null {
  try {
    return window.localStorage.getItem(PROJECT_KEY);
  } catch {
    return null;
  }
}

let projectGeneration = 0;
let projectPending: Promise<Project | null> | null = null;
let activeProjectId: string | null = null;

export function clearStoredProjectId() {
  projectGeneration++;
  projectPending = null;
  activeProjectId = null;
  try { window.localStorage.removeItem(PROJECT_KEY); } catch {}
}

// Single flight across StrictMode effects and Documents/Timeline. Never replace an
// existing identity merely because the API is temporarily unavailable.
export function ensureProject(): Promise<Project | null> {
  if (!backendConfigured()) return Promise.resolve(null);
  if (projectPending) return projectPending;
  const generation = projectGeneration;
  const pending = (async () => {
    const stored = readStoredProjectId() ?? activeProjectId;
    if (stored) {
      const project = await getProject(stored);
      return generation === projectGeneration ? project : null;
    }
    const id = await createAndActivateProject();
    if (!id || generation !== projectGeneration) return null;
    activeProjectId = id;
    try { window.localStorage.setItem(PROJECT_KEY, id); } catch {}
    const project = await getProject(id);
    return generation === projectGeneration ? project : null;
  })();
  projectPending = pending;
  void pending.finally(() => { if (projectPending === pending) projectPending = null; });
  return pending;
}

// Retry exactly once, only for optimistic revision conflicts.
export async function markRequirementReady(id: string, key: string, revision: number): Promise<Project | null> {
  const path = `/api/v1/projects/${encodeURIComponent(id)}/requirements/${encodeURIComponent(key)}`;
  let status = 0;
  const first = await request<{ project: Project }>("PATCH", path, { status: "ready", expected_revision: revision }, (s) => { status = s; });
  if (first?.project) return first.project;
  if (status !== 409) return null;
  const latest = await getProject(id);
  if (!latest) return null;
  if (latest.checklist?.some((c) => c.key === key && c.status === "ready")) return latest;
  const second = await request<{ project: Project }>("PATCH", path, { status: "ready", expected_revision: latest.revision });
  return second?.project ?? null;
}

export async function loadDemoTimeline(asOf?: string): Promise<Timeline | null> {
  const project = await ensureProject();
  return project ? getTimeline(project.id, asOf) : null;
}
