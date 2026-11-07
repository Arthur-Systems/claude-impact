# ClearPath Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend that imports sourced permit datasets and lets a team manage multiple independent housing projects, starting with Irvine ADU guidance and retaining multifamily cases as drafts until their rules are added.

**Architecture:** One FastAPI application, PostgreSQL, and an operator CLI share the same domain services. Dataset releases are immutable; activating a project pins its matching release. Ingestion, lookup, and timeline work are tasks in one plan because their contracts share release, citation, and project identities.

**Tech Stack:** Python 3.12; FastAPI; Pydantic 2; SQLAlchemy 2; Alembic; psycopg 3; HTTPX; Shapely; PostgreSQL 17 with pgvector; pytest; Docker Compose.

**Spec:** [ClearPath backend design](../specs/2026-11-07-clearpath-backend-design.md).

**Status:** Ready for user review before implementation. Confirmed sequence: Irvine ADU first; affordable multifamily rule coverage next; multiple projects from the start.

## Global Constraints

- Scope: Lane 2 — Clear it. Backend only.
- The shared workspace supports many projects from the first release.
- Affordable-housing intent is user-declared; `affordability_verification=not_assessed`.
- No frontend, chat, embeddings/search, user uploads/OCR, actual application submission, or messaging in this slice.
- All timestamps are timezone-aware UTC. City civil dates use `America/Los_Angeles`.
- Source-dependent requirements need reviewed immutable citations. Unknowns, source conflicts, assumptions, and unavailable rule coverage stay explicit.
- Protect non-health application routes with `X-API-Key`, configured from `CLEARPATH_API_KEY`; use loopback bindings and disabled-by-default CORS.
- Import and API services do not accept actual applicant/resident/owner information or generic filled-form values.
- Lock exact compatible dependencies and the database image digest. Do not use `latest` image tags or SQLite as an integration-test substitute.
- Keep synthetic and reviewed-public datasets in separate database/Compose profiles. Public mode never silently falls back to fixtures.
- Preserve `clear_path_checklist_build/` unchanged. Its packet schema is demo metadata, not a reviewed permit rule bundle.
- Existing starter `timeline.json` is assumed background, not an Irvine ADU duration dataset. Statutory due-date arithmetic remains disabled.
- Execute each task's failing-test, implementation, passing-test, and named-file commit cycle. Do not create product files while this plan awaits review.

## Review Focus

1. Two projects sharing a release and identical requirement keys must remain independent — Task 4 tests A13 and conflicting writes.
2. Address-table coordinates with an unknown CRS or several BIN/address matches must never be treated as a unique Irvine parcel — Task 3 adapter tests.
3. Garbled extracts, null starter fields, or changed source hashes must not become silently trusted rules — Task 2 import/publication tests.
4. Unknown stage durations and reopened dependencies must not produce false finish dates or impossible correction cycles — Task 5 graph/state tests.
5. Synthetic releases, packet `required` flags, and personally identifying form fields must not leak into public guidance — Tasks 2 and 6 mode/privacy contract tests.

## Repository and file ownership

Current inputs are `lanes/2-clear-it/data/oc-cities.json`, `timeline.json`,
`scenarios.json`, and `DATA-SOURCES.md`; their limitations are in spec section 3.
`clear_path_checklist_build/{README.md,packet_spec.py,build_packet.py,clearpath_adu_packet_schema.json,clearpath_adu_packet_blank.pdf}`
already exist and must not be regenerated or modified by backend setup.

All `backend/` paths below are new. Root `compose.yaml`, `Makefile`, and
`.env.example` are also new. Before execution, fetch current remote work and use
an isolated worktree through Superpowers' worktree workflow if needed. Integrate
new teammate files without overwriting them.

| Owner | Paths / responsibility |
|---|---|
| Task 1 | `backend/pyproject.toml`, `backend/uv.lock`, `backend/Dockerfile`, `backend/alembic.ini`, `backend/migrations/`, `backend/src/clearpath/core/`, `domain/`, `db/`, `api/app.py`, `api/dependencies.py`, root infrastructure |
| Task 2 | `backend/src/clearpath/ingestion/`, `backend/src/clearpath/cli.py`, `backend/data/irvine_adu/`, `backend/tests/fixtures/irvine_adu_synthetic/` |
| Task 3 | `backend/src/clearpath/locations/`, `backend/src/clearpath/permits/`, `api/routes/locations.py`, `permits.py`, `catalog.py` |
| Task 4 | `backend/src/clearpath/projects/`, `api/routes/projects.py` |
| Task 5 | `backend/src/clearpath/timelines/`, `api/routes/timelines.py` |
| Task 6 | Cross-service contract tests, demo runner, user/developer documentation, CI |

Each service owns focused `schemas.py`, `service.py`, and supporting files where
listed. Empty `__init__.py` files belong to their containing package owner. Later
tasks add their route registrations to `api/app.py` and their Makefile targets;
these small integration edits are sequential, not concurrent shared-file writes.

## Shared interfaces and decisions

Task 1 defines the shared request vocabulary in `domain/schemas.py`:

- `ProjectScope`: `project_type` (`adu/duplex/multifamily/other_housing`), optional
  `subtype` and `jurisdiction_id`, optional positive `proposed_unit_count`,
  `affordability_goal` (`affordable_housing/mixed_income/unspecified`), and optional
  nonnegative `affordable_unit_count_goal` not exceeding a supplied total.
- `LocationInput`: discriminated `address`, `point`, `area`, or `fixture` mode.
  Address uses the structured components in spec section 7; point uses finite
  WGS84 longitude/latitude; area uses a registry jurisdiction ID. Fixture IDs are
  accepted only in explicit synthetic mode. No invented real address is needed.
- `RuleFacts`: manifest-validated scalar fact mapping. In a draft without matching
  coverage it must be empty; common project metadata remains valid independently.
- `DomainError(code: str, message: str, details: dict, http_status: int)` in
  `domain/errors.py`, translated to the spec's error envelope.

Task 1 supplies `get_session() -> Iterator[Session]`, `get_settings() -> Settings`,
and `require_api_key() -> None`. Use synchronous SQLAlchemy service interfaces;
the API route/CLI owns the transaction and commit. Services receive `Session`
and do not commit or begin nested transactions. A state mutation locks its
project row and appends its event inside the same outer transaction.

Schema versions start at 1. The first profile key is
`irvine-adu-detached-existing-dwelling`; it belongs to `irvine-ca`, type `adu`,
subtype `detached`, with the scope fact `existing_dwelling=true`. This is a data
profile key, not a global project-type condition. A lookup can request a profile
key explicitly. When omitted, select only a unique compatible profile; several
possible profiles produce `needs_information` with missing key `profile_key`.

Settings contain database URL, shared API key, `public/synthetic` mode,
bundle/cache roots, approved source hosts, and an explicit CORS allowlist.
Use secret-aware settings and omit input values from validation/error logs.

---

### Task 1: Migratable database and authenticated service foundation

**Files:** Create root `compose.yaml`, `Makefile`, `.env.example`, backend package,
lock, Dockerfile, Alembic environment/initial migration, `core/config.py`,
`domain/schemas.py`, `domain/errors.py`, `db/models.py`, `db/session.py`,
`api/app.py`, `api/dependencies.py`; tests
`backend/tests/integration/test_foundation.py` and `backend/tests/conftest.py`.

**Interfaces:** Produce the shared contracts above, ORM models for every table
in spec section 5, `create_app(settings: Settings) -> FastAPI`, and the session
dependency. The model set includes constrained citation associations, immutable
release contents, nullable draft bindings, and project-scoped child identities.

- [ ] **Write failing foundation tests.** `test_migration_and_empty_readiness`
  asserts a fresh PG17 database has extension `vector`, every required table,
  `/health/live` returns 200, and ready reports a healthy schema with dataset
  availability false. `test_shared_key_and_input_shape` asserts protected
  routes return 401 without the key, unknown fields are rejected, and health
  output exposes no configuration. Use a minimal protected test route until
  business routes arrive.
- [ ] **Run the failing tests** with
  `uv run --project backend pytest backend/tests/integration/test_foundation.py -q`;
  first establish the pinned test environment, then verify missing service/schema
  behavior produces real failures rather than treating collection errors as proof.
- [ ] **Implement infrastructure and the initial migration.** Enforce the active
  release uniqueness tuple `(jurisdiction_id, project_type, profile_key)`, draft
  bindings null/active bindings nonnull, stable release-local keys, and project
  event revision uniqueness. Reject invalid unit-count goals. Add separate public,
  synthetic, and disposable-test DB profiles and loopback ports. Create
  `make backend-up`, `make backend-migrate`, and `make test-backend` targets.
- [ ] **Run foundation verification** on an empty DB, migration upgrade, tests,
  and a second upgrade. Expect all tests to pass, no second-upgrade schema change,
  and failure when two active releases with the same full scope are inserted.
- [ ] **Commit named task files** as `feat: establish ClearPath database and API foundation`.

### Task 2: Repeatable dataset importer and isolated seed bundles

**Files:** Create `ingestion/{schemas.py,validation.py,fetcher.py,service.py}`,
`cli.py`, the two new dataset/fixture directories, and tests
`unit/test_manifest_validation.py`, `unit/test_fetch_policy.py`,
`integration/test_ingestion.py`. Extend Makefile seed targets and ignore only
backend runtime cache files in `.gitignore`.

**Interfaces:** Consume Task 1 models/contracts. Produce
`validate_bundle(path: Path, settings: Settings) -> ValidatedBundle`,
`import_bundle(session: Session, bundle: ValidatedBundle) -> ImportResult`,
`publish_release(session: Session, release_id: UUID, reviewed: bool) -> DatasetRelease`,
and `activate_release(session: Session, release_id: UUID) -> DatasetRelease`.
`ValidatedBundle` contains normalized scope/fact schema, source snapshots/passages,
pathways/requirements, acyclic milestones, and content hash. `ImportResult`
includes release ID, created/reused counts, and whether this was a no-op.

- [ ] **Write failing validation/fetch tests.** Assert rejection of hash mismatch,
  malformed/unknown predicates, untyped facts, missing cited passages, dangling
  references, cyclic graphs, path traversal, garbled unreviewed extracts, and
  nonpublic/redirected source URLs. Assert `.env` values and offending personal
  input never appear in errors. A dry-run must make zero network/DB/file writes.
- [ ] **Write failing integration tests.** `test_reimport_is_noop` imports the
  same bundle twice and asserts identical release ID and row counts;
  `test_publish_and_rollback_are_atomic` uses two connections to assert at most
  one active release and existing project pins unchanged;
  `test_public_mode_rejects_synthetic_release` prevents cross-profile publication.
- [ ] **Implement the importer/CLI** with the five command forms in spec section
  6. Fetch snapshots before DB publication, validate redirects and resolved IPs,
  apply 1 request/second/host, 10-second timeout, one transient retry, and 10 MiB
  cap. Resolve only bundle/cache-contained paths. Lock the jurisdiction row for
  publication/rollback. Retain old working snapshots on fetch failure.
- [ ] **Author fixtures and the first reviewed-public bundle.** Import the 34-city
  registry while preserving null metadata. Keep source-list verification labels
  as inherited leads, and the starter timeline as background only. Use C01 as
  narrative, not a person/permit row. Curate the source corpus cited in the spec
  into small reviewed passages with original URL/hash/locator/check dates and
  reuse notes. Only publish requirements actually supported by those passages;
  missing/garbled source content stays a visible gap. Include typed rules and
  the first profile's graph. Do not import packet flags, filled form fields,
  fabricated fees, a plan-vendor catalog, statutory arithmetic, or APR rows.
  Supply a separately labeled synthetic graph/geometry with calendar-day
  assumptions for deterministic testing.
- [ ] **Verify** with
  `uv run --project backend pytest backend/tests/unit/test_manifest_validation.py backend/tests/unit/test_fetch_policy.py backend/tests/integration/test_ingestion.py -q`,
  then both `make seed-demo` and `make seed-irvine` in their separate profiles.
  Expect repeat imports to add no rows and invalid bundles to publish nothing.
- [ ] **Commit named task files** as `feat: import versioned permit datasets and demo seeds`.

### Task 3: Conservative location resolution and sourced permit lookup

**Files:** Create `locations/{schemas.py,adapters.py,service.py}`,
`permits/{schemas.py,predicates.py,service.py}`,
`api/routes/{locations.py,permits.py,catalog.py}`; tests
`unit/test_location_resolution.py`, `unit/test_predicates.py`, and
`integration/test_permit_lookup.py`. Register the routes in `api/app.py`.

**Interfaces:** Produce
`resolve_location(location: LocationInput, adapter: LocationAdapter) -> LocationResolution`,
`evaluate_predicate(predicate: dict, facts: dict) -> PredicateResult`, and
`lookup_permits(session: Session, request: PermitLookupInput, resolver: LocationResolver) -> PermitLookupResult`.
`PredicateResult` has `true/false/unknown` and missing keys. Lookup input contains
location, scope, rule facts, and optional profile key. Results contain status,
location resolution, nullable release, candidate pathways, requirement
applicability, citations, coverage gaps, missing keys, and warnings.

- [ ] **Write failing truth-table tests** for every operator and true/false/unknown
  combination pinned in spec section 7. Missing/conflicted evidence must never
  become `not_applicable`. Unknown fact keys/types are rejected without eval or
  SQL expression execution.
- [ ] **Write failing adapter tests** for one address, several address rows,
  multiple BIN building matches, capped results, boundary/cross-boundary geometry,
  no-match, provider timeout, bad input coordinates, and undocumented X/Y CRS.
  Assert escaped exact queries select only technical fields and request EPSG:4326
  geometry. `ADU=1` cannot establish permission. Use synthetic geometry and fake
  HTTP responses; no real address fixture or live network in tests.
- [ ] **Implement the adapter and services.** Use only the official table/layer
  endpoints and fields documented in the spec; never infer city membership from
  ZIP/postal text. Explicit area selection bypasses address resolution and stays
  qualified as area guidance. Load immutable release evidence and evaluate only
  matching profiles. No profile for multifamily returns
  `rule_coverage_unavailable` with empty generated guidance; a configured but
  unavailable dataset returns 503. Profile ambiguity asks for `profile_key`.
- [ ] **Verify catalog/lookup API contracts** with
  `uv run --project backend pytest backend/tests/unit/test_location_resolution.py backend/tests/unit/test_predicates.py backend/tests/integration/test_permit_lookup.py -q`.
  Assert registry membership does not imply coverage, every sourced requirement
  resolves to a passage, synthetic mode is explicit, and ambiguity produces no
  property-specific checklist. Complete the source-provenance endpoint.
- [ ] **Commit named task files** as `feat: resolve Irvine locations and return sourced permit guidance`.

### Task 4: Project portfolio, editable drafts, and explicit guidance activation

**Files:** Create `projects/{schemas.py,service.py}`, `api/routes/projects.py`;
tests `integration/test_projects.py`, `integration/test_project_isolation.py`.
Register project routes in `api/app.py`.

**Interfaces:** Consume Task 3 `lookup_permits`. Produce
`create_draft(session: Session, request: ProjectCreateInput) -> ProjectDetail`,
`update_draft(session: Session, project_id: UUID, request: ProjectUpdateInput) -> ProjectDetail`,
`activate_project(session: Session, project_id: UUID, request: ProjectActivationInput, resolver: LocationResolver) -> ProjectDetail`,
`list_projects(session: Session, query: ProjectListQuery) -> ProjectPage`, and
`get_project(session: Session, project_id: UUID) -> ProjectDetail`.
Every update input has `expected_revision`; activation also has pathway and
optional profile key. Creation starts at revision 1 with a creation event; each
successful mutation increments by one with one event. Read operations never do.

- [ ] **Write failing draft/portfolio tests.** Save an ADU and an affordable
  multifamily draft without requiring an active release. Assert empty generated
  state, null progress, `not_assessed` affordability verification, typed counts,
  bounded nonpersonal labels, and rejection of arbitrary filled-form maps.
  Filter by city/type/state/coverage and traverse stable `(created_at, id)`
  cursors with default 50/max 100, including tied timestamps without duplicates.
- [ ] **Write failing activation/isolation tests.** Activate two projects on the
  same release and keys. Assert separate child rows, revisions, and events;
  publishing another release cannot rewrite either. A nonexistent/foreign-release
  pathway or insufficient scope leaves draft state/revision unchanged and no
  partial child rows. An active-scope edit returns 409. A stale competing update
  writes no state/event. Test real concurrent PG connections, not mocked locks.
- [ ] **Implement services/routes** for create/get/list/patch/activate. Lock before
  checking revisions and bind pathway/children to the exact pinned release.
  Revalidate server-side location/scope; never accept the client's resolved
  boundary or applicability as proof. Draft coverage reasons are locally derived;
  creating/listing drafts must not call a live geocoder. Missing multifamily
  rules cannot borrow ADU guidance. Active scope remains immutable in this slice.
- [ ] **Verify** with
  `uv run --project backend pytest backend/tests/integration/test_projects.py backend/tests/integration/test_project_isolation.py -q`.
  Expect two isolated supported projects, one retained unsupported draft, and
  no cross-project state/revision/event changes.
- [ ] **Commit named task files** as `feat: manage multiple housing projects and activate sourced guidance`.

### Task 5: Checklist state, correction cycles, and timeline calculation

**Files:** Create `timelines/{schemas.py,graph.py,service.py}`,
`api/routes/timelines.py`; extend `projects/service.py` with checklist mutation;
tests `unit/test_timeline_forecasts.py`, `integration/test_project_timeline.py`.
Register routes in `api/app.py`.

**Interfaces:** Produce
`set_requirement_status(session: Session, project_id: UUID, key: str, request: RequirementUpdateInput) -> ProjectDetail`,
`record_milestone_event(session: Session, project_id: UUID, request: MilestoneEventInput) -> MilestoneEventResult`,
and `get_timeline(session: Session, project_id: UUID, as_of: date) -> ProjectTimeline`.
Mutation inputs carry `expected_revision`. Event input contains milestone key,
`start/complete/reopen`, occurrence timestamp, and optional structured correction
reason. `MilestoneEventResult` contains project ID, new revision, event ID, and
updated milestone state/dates; it does not infer a forecast date from the wall clock.
Timeline output is current state evaluated at an explicit `as_of`, with
counts/readiness, next actions, bottlenecks, evidence, and nullable finish range.

- [ ] **Write failing state tests.** Missing preparation/predecessors block start
  or completion; stale revisions and foreign-project/release keys change nothing.
  Complete requires an existing start. Future timestamps or completion before
  start are rejected. Reopen started/completed dependents in reverse topological
  order, then the prerequisite; reopen resets current timestamps/state while
  audit events retain prior cycles. Demoting ready preparation requires reopening
  its dependent milestones first. Draft mutation returns `project_not_active`.
- [ ] **Write failing forecast tests.** Assert completed/total and one-decimal
  progress, unknown requirements pending in readiness, empty/null draft timing,
  maximum predecessor finish on parallel paths, unknown-duration propagation,
  elapsed in-progress bounds clamped to zero, and `as_of` before actual events
  rejected. Use small synthetic calendar-day assumptions; verify no holiday or
  statutory due-date calculation is invoked and the starter timeline is unused.
- [ ] **Implement graph/state services** using the spec's transition table and
  project-scoped locked transactions. The ADU's six milestones live in its
  dataset, not global application code. Emit next actions and the five bottleneck
  reason codes from the spec; an assumed overrun cannot become a legal violation.
  `get_timeline` for a draft returns 200 `timeline_unconfigured`, empty generated
  milestones, null metrics/forecast, and its coverage reason.
- [ ] **Verify** with
  `uv run --project backend pytest backend/tests/unit/test_timeline_forecasts.py backend/tests/integration/test_project_timeline.py backend/tests/integration/test_project_isolation.py -q`.
  Update project A's checklist/milestones and assert B's progress, forecast,
  revision, and events remain unchanged. Supply event cursor pagination.
- [ ] **Commit named task files** as `feat: track checklist progress and project review timelines`.

### Task 6: Reproducible backend demonstration and contract verification

**Files:** Create `backend/tests/contracts/test_demo_workflow.py`,
`backend/tests/contracts/test_openapi.py`, `backend/scripts/demo.py`,
`backend/README.md`, and `.github/workflows/backend.yml`; modify root README,
Makefile, and CLAUDE.md with actual commands/status. Do not edit packet files.

**Interfaces:** Consume the completed HTTP API. The demo script calls those public
routes rather than reaching into ORM state. Produce runnable seed/demo examples
and a small opt-in live source/address metadata smoke command.

- [ ] **Write failing end-to-end contract tests.** Through authenticated HTTP:
  create two ADU drafts, activate both, save an affordable multifamily draft,
  list/filter them, update A's readiness/milestones, reject premature completion,
  then demonstrate corrections and an assumed finish range. Assert B is unchanged,
  the multifamily draft has unavailable guidance, every source reference resolves,
  and all three retain declared affordability status without qualification claims.
  Cover auth, strict request fields, public/synthetic separation, and sanitized
  error/OpenAPI responses, including no secrets/private cache paths.
- [ ] **Implement the demo runner and operational documentation.** Document fresh
  checkout prerequisites and exact `uv`, Compose, migration, seed, test, and demo
  commands. `.env.example` contains names and harmless placeholders only. Root
  status must distinguish implemented features, synthetic calculations, reviewed
  sources, and multifamily coverage still to add. The backend does not require
  the packet builder's reportlab/pypdf dependencies or a Claude API key.
- [ ] **Implement bounded CI and opt-in checks.** CI starts PG17+pgvector and runs
  migrations, unit/integration/contracts, lint/type checks actually configured in
  `pyproject.toml`, and no network-dependent city tests. Opt-in live checks confirm
  metadata/allowed-source availability only; no filled forms or real applicant
  records. Record the spec's local 100-request/p95 target separately from live
  network timing; do not assert an unmeasured performance result.
- [ ] **Run final verification** with `make test-backend`, a fresh-profile migration
  and both separate seed/demo flows. Inspect OpenAPI for every spec section 9
  route. Expect all configured checks to pass, repeat seeding to add no rows,
  drafts to survive unavailable data, and packet files unchanged. Fix failures
  before release work; perform a whole-change review with the installed gstack
  review workflow and follow the repository's release workflow for publishing.
- [ ] **Commit named task files** as `test: demonstrate and verify ClearPath backend workflows`.

## Spec coverage and execution order

| Acceptance criteria | Owning task |
|---|---|
| A1, health/auth foundation | 1, 6 |
| A2–A4, repeatable validated imports/publication | 2 |
| A5–A6, geographic uncertainty and sourced predicates | 3 |
| A7, A13, A14, A15, project portfolio/activation/isolation/declared goals | 4, 6 |
| A8–A10, checklist state, corrections, timing limits | 5 |
| A11–A12, reproducible demo and API/privacy contracts | 2, 3, 6 |

Run Task 1 first, then 2, 3, 4, 5, and 6. Source-curation inspection may run in
parallel with foundation work, but shared models and route integration remain
sequential. Each task is independently reviewable through its API/database tests;
do not split foundational schema edits across concurrently writing agents.

## Self-review

Spec coverage, cross-task signatures, exact scope values, failure tests, and plan
size were checked against the design. The five Review Focus cases each have
named tests in their owning task. The plan defines interfaces and assertions,
without copying implementation bodies. No backend files, dependencies, or
runtime services were created while writing this plan.

## Next dataset

Affordable multifamily is the next rule bundle after the first backend works.
Its city, housing subtype, authoritative forms, approval pathways, and timing
evidence require their own curation. Adding that bundle must use the same
manifest/importer/project contracts and keep existing ADU projects pinned to
their own releases; this plan does not claim multifamily guidance is implemented.
