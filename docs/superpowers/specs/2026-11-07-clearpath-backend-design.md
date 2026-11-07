# ClearPath backend design

Date: November 7, 2026

Status: Proposed design; awaiting user approval before implementation.

Scope: Lane 2 — Clear it. Backend only.

Confirmed demo: Irvine, California; accessory dwelling unit (ADU).

## 1. Outcome

Help a first-time ADU applicant find the relevant Irvine process, understand the
documents and missing project facts, and track preparation and review milestones.
The first release supplies three working backend capabilities:

1. A PostgreSQL database and repeatable dataset importer for curated public sources.
2. Address or area lookup returning sourced, conditional permit checklists.
3. A project timeline with progress, next actions, and explicitly qualified timing.

Success is a reproducible API demonstration: seed a database, look up an Irvine
ADU case, create a project, update its checklist and milestones, and retrieve its
progress. The demo must work from a checked-in public fixture bundle without
Claude credentials, a paid geocoder, or a live municipal website. Live address
resolution is a separate, honestly reported integration capability.

## 2. Decisions and boundaries

**User decisions:** ClearPath; FastAPI/Python; PostgreSQL with pgvector; Irvine +
ADU first; frontend later; begin with ingestion, lookup, and timelines.

**Proposed engineering defaults:** a single FastAPI application with separate
modules, synchronous operator-run ingestion, one shared demo workspace, and
deterministic checklist evaluation. These defaults are recommendations for this
spec, rather than additional user requirements.

The initial backend excludes frontend code, a chat assistant, embedding generation,
vector search, user PDF uploads, OCR, accounts, multiple workspaces, live permit
status scraping, application submission, and messaging. It does not decide legal
eligibility or guarantee approval. Claude-based explanations and document search
can consume the same source references in a later slice; core results cannot
depend on generated prose. Enabling pgvector is included; building a vector index
without an embedding model and retrieval task is deferred.

The first project subtype is a **proposed detached ADU on a lot with an existing
dwelling**, proposed as the narrow demo default. Other ADU forms return the general
Irvine guide with `needs_information` or `unsupported_subtype`, rather than a
fabricated project-specific determination. Completing this backend must not
require implementing other cities, other lanes, fees calculated from incomplete
schedules, financing, construction scheduling, or parcel/zoning eligibility.

## 3. Existing evidence and source limitations

The current repository contains event materials, without application code or a
database. Three starter files need distinct handling:

| File | Actual contents | Import behavior |
|---|---|---|
| `lanes/2-clear-it/data/oc-cities.json` | 34 city names; every permit URL, checklist URL, fee URL, and checked date is null | Import Irvine as the supported jurisdiction; keep other names only as unsupported reference metadata if needed. Null stays unknown. |
| `lanes/2-clear-it/data/timeline.json` | Rounded, explicitly assumed whole-project phases | Preserve as background provenance; never seed these numbers as Irvine ADU review durations. |
| `lanes/2-clear-it/scenarios.json` | Fictional C01–C03 user scenarios | Use C01 as a demonstration narrative; never import these as actual permit records. |

Organizer `VERIFIED` labels record earlier checks, sometimes only page availability.
They must not become importer verification or reviewed regulatory rules by default.

The initial public corpus was checked on November 7, 2026:

| ID | Primary source | Intended use / important limit |
|---|---|---|
| IRV-ADU | [Irvine ADU construction guide](https://cityofirvine.gov/building-permits-and-inspections/project-constructing-accessory-dwelling-unit-adu) | City workflow and document links. Some forms are obtained from Planning. Its approximate initial completeness-review target is a city service target, not an overall approval forecast. |
| IRV-APP | [Irvine ADU application package](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-34716-adu-application-package_updated-2025.pdf) | Blank application package. Extracted text has garbled characters; derived requirements need a reviewed extract with page locations. |
| IRV-CHECK | [Irvine development standards checklist](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35890-67-01.pdf) | Blank checklist, with page-specific references. |
| IRV-AFF | [Irvine hold harmless affidavit](https://cityofirvine.gov/sites/default/files/legacy-documents/civica-35928-67-02.pdf) | Blank form; having a link does not mean the applicant completed or signed it. |
| HCD-ADU | [HCD handbook landing page](https://www.hcd.ca.gov/building-standards/adu/handbook) and [March 2026 handbook](https://www.hcd.ca.gov/sites/default/files/docs/policy-and-research/adu-handbook-update.pdf) | Agency guidance with citations. Direct statute text must be checked separately before publishing executable legal deadline rules. |
| IRV-BOUNDARY | [Official city boundary layer](https://gis.cityofirvine.org/arcgis/rest/services/CityBoundary/MapServer/0) | Official polygon, queried as EPSG:4326 GeoJSON. Validates a resolved point's city membership, not parcel eligibility or every agency's authority. |
| IRV-PLANS | [Irvine pre-approved plan program](https://cityofirvine.gov/building-permits-and-inspections/pre-approved-adu-plans-program) | The plan list currently says coming soon. Seed no available plan/vendor catalog; site-specific review still matters. |

The local source list associates a review clock with an older shorthand citation.
Current HCD guidance instead refers to Government Code 66317 for completeness and
decision timing. A direct [Leginfo section](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=GOV&sectionNum=66317)
fetch was blocked during this research. Record the verification gap; do not silently
turn either citation into an active legal deadline calculator.

Historical [HCD APR data](https://data.ca.gov/dataset/housing-element-annual-progress-report-apr-data-by-jurisdiction-and-year)
is a later enrichment. Its records are self-reported, and no exact Irvine ADU
cohort has been validated here. Metadata alone cannot establish an approval-time
benchmark. APN is not a unique permit key, and a broad text query for Irvine is
not an exact jurisdiction filter.

## 4. Architecture and operations

Use one deployable Python service, one PostgreSQL database, and an operator CLI
sharing the application's validation and persistence services.

| Module | Responsibility |
|---|---|
| `ingestion` | Validate manifests and source snapshots; stage immutable releases; publish atomically; report source drift. |
| `locations` | Normalize supported structured addresses, query an address adapter, and check official boundary geometry. |
| `permits` | Evaluate curated conditions, build checklists, and attach source evidence and missing facts. |
| `projects` | Persist project facts and checklist state against a pinned release. |
| `timelines` | Evaluate milestone dependencies, progress, timing evidence, and bottlenecks. |
| `api` | Request validation, shared-key authentication, HTTP responses, and OpenAPI. |

Proposed implementation stack: Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2,
Alembic, psycopg 3, HTTPX, and Shapely for polygon membership. Use PostgreSQL 17
with the pgvector extension. Lock exact compatible dependency versions and the
container image digest during implementation; do not use `latest` image tags.
Tests use pytest and a real disposable PostgreSQL database.

Local Docker Compose binds the API and database to loopback. The first backend
does not add Redis or a worker fleet. Imports run as explicit CLI commands, so
they are not lost as in-process HTTP background tasks. The [FastAPI background
task documentation](https://fastapi.tiangolo.com/tutorial/background-tasks/)
describes those tasks separately from heavier external processing.

All timestamps are timezone-aware UTC. Civil dates shown for city milestones use
`America/Los_Angeles`. API IDs are UUIDs; stable dataset keys are lowercase slugs.
Database changes use migrations, including `CREATE EXTENSION vector`. The
[pgvector project](https://github.com/pgvector/pgvector) documents the extension;
its presence must not be reported as implemented semantic search.

## 5. Data model

Required tables and constraints follow. JSONB structures described below are
validated with Pydantic before persistence and again before release publication.

| Table | Required fields and invariants |
|---|---|
| `jurisdictions` | `id`, unique `slug=irvine-ca`, `name`, `state=CA`, `timezone`, `supported_project_types`, optional boundary snapshot reference. A city name is not location verification. |
| `source_snapshots` | `id`, stable source key, canonical URL, title, publisher, authority type, MIME type, fetched/checked timestamps, optional effective dates, SHA-256, local artifact key, extraction status, review status. Unique `(source_key, sha256)`. Failed fetches do not replace a working snapshot. |
| `source_passages` | `id`, snapshot FK, locator (`page` or HTML heading/anchor), reviewed excerpt, excerpt hash. A citation resolves to one immutable snapshot and passage. |
| `ingestion_runs` | `id`, manifest hash, command kind, start/end timestamps, status, counts, sanitized error codes, resulting release FK. Duplicate import of the same manifest and content returns the same release. |
| `dataset_releases` | `id`, jurisdiction FK, project type/subtype, content hash, schema version, normalized manifest JSON including source conflicts, `draft/active/retired`, `synthetic/reviewed_public`, created/published timestamps, curator label. At most one active release per jurisdiction and supported subtype. Content is immutable after staging. |
| `pathways` | `id`, release FK, unique release-local key, title, applicability predicate, explanatory text, citation IDs. A candidate process is not approval eligibility. |
| `requirements` | `id`, release FK, unique release-local key, pathway key(s), `permit/document/review`, title, description, applicability predicate, required-for-preparation flag, citation IDs. Source-dependent requirements require at least one reviewed citation. |
| `milestone_templates` | `id`, release FK, pathway key, stable key, title, predecessor keys, associated requirement keys, optional forecast range, optional published clock metadata, citation IDs. Graph must be acyclic and every reference must resolve within its release. |
| `projects` | `id`, pinned release FK, selected pathway key or null, validated project facts, location evidence, `revision`, created/updated timestamps. No owner/applicant identity, contact details, or uploaded documents. |
| `project_requirements` | Project/requirement composite key; `not_started/in_progress/ready`, updated timestamp. Applicability comes from the rule engine; a client cannot mark an inapplicable requirement applicable. Ready is self-reported preparation, not municipal acceptance. |
| `project_milestones` | Project/template composite key; `not_started/in_progress/completed`, actual start/completion timestamps. Blocked/available states are derived from prerequisites and required documents. |
| `project_events` | `id`, project FK, unique project revision, event type, occurrence and recording timestamps, minimal structured payload. Append-only audit trail, committed with the state change. |

Citation IDs are stored as typed UUID arrays in the manifest and resolved to
passage rows on import; persistence uses join tables or constrained association
rows so deleting a cited passage cannot leave dangling evidence. The implementer
may choose the association-table layout without changing the API contract.

Use a partial unique index for the active-release constraint and lock the
jurisdiction row during publication. Retiring the old release and activating the
new one happen in one transaction. Existing projects retain their original
release; this slice offers no automatic project migration. PostgreSQL documents
the required [row-lock behavior](https://www.postgresql.org/docs/17/explicit-locking.html).

## 6. Dataset injector contract

The checked-in dataset directory will be `backend/data/irvine_adu/`. Its manifest
contains `schema_version`, jurisdiction/subtype, source descriptors, reviewed
passages, pathways, requirements, and milestone templates. Source descriptors
include original URL, fetch/check date, content hash, local snapshot path,
verification depth, and terms/provenance notes. No secret or absolute laptop
path belongs in the manifest.

The importable public bundle includes small reviewed extracts with provenance and
reuse terms. Large originals and live boundary geometry stay in an ignored local
cache; do not commit GIS geometry until its redistribution terms are established.
An explicitly synthetic polygon supports offline location tests. A copied blank form is
not a submitted application. Use only preapproved public technical sources and
blank forms. Do not ingest actual applicant/resident information or a raw APR
export containing prohibited personal fields. Detection stops the import without
persisting the offending payload, including in logs or quarantine storage.

Commands to implement:

| Command | Behavior |
|---|---|
| `clearpath data fetch --manifest PATH` | Explicitly refresh allowlisted public source snapshots. No database publication. Network access occurs only here and in the live location adapter. |
| `clearpath data import --manifest PATH --dry-run` | Validate existing local files, hashes, schema, citations, rule predicates, and graph. Print proposed counts/errors; write no DB rows or files and make no network calls. |
| `clearpath data import --manifest PATH` | Stage a complete immutable draft in one transaction. Repeated identical imports are no-ops. Invalid content leaves no partial release. |
| `clearpath data publish --release UUID --reviewed` | Operator explicitly confirms the curated bundle was checked. Reject broken references, missing required evidence, failed extraction, or unsupported schema. Atomically update the active release. |
| `clearpath data activate --release UUID` | Roll back to a previously published immutable release, under the same lock and validation. Existing projects remain pinned. |

Fetcher defaults are engineering limits: HTTPS only; approved hosts and paths;
reject credentials in URLs and nonpublic resolved IPs; validate every redirect;
one request per second per host; 10-second request timeout; one retry for transient
failures; 10 MiB maximum per file. This slice has no arbitrary URL ingestion API.
Import paths must resolve inside the dataset bundle or configured cache; reject
path traversal. Raw source text is data, never executable instructions.

Extraction states are `pending/parsed/needs_review/failed`. Text presence alone
does not indicate correct extraction. Corrupted PDF text is `needs_review` until
a manually checked extract supplies usable passages. Automatic OCR is deferred.
Release publication must not infer that inaccessible statute text was verified
from a successful handbook or page-title fetch.

Refreshing a source creates a new hash/version and a draft update. It does not
silently replace published facts. A new unavailable source produces a visible
error; existing last-checked evidence stays available with its date. Multiple
contradictory sources produce an explicit conflict record in the manifest and
responses, with affected rule keys. A conflicted rule is not a definitive answer.

## 7. Location and permit lookup

Support either a structured address, WGS84 coordinates, or an explicit Irvine
area selection. Require exactly one input mode. Area selection is labeled
`selected_area`; it does not claim a property was checked.

The live address adapter uses Irvine's [building-address table 19](https://gis.cityofirvine.org/arcgis/rest/services/OnlineParcel/MapServer/19?f=json)
and [building layer 1](https://gis.cityofirvine.org/arcgis/rest/services/OnlineParcel/MapServer/1?f=json).
Metadata and zero-result queries were checked; record-level matching/coverage is
not yet proven. Accept structured components `number`, `street_name`, optional
`prefix`, `pretype`, `street_type`, `suffix`, and `unit`. Preserve number/unit as
strings. Match the allowlisted fields `ADDRESS`, `NAME`, `PREFIX`, `PRETYPE`,
`STTYPE`, `SUFFIX`, and `UNIT` using exact normalized values. Normalize whitespace,
case, and an explicit tested abbreviation map; no fuzzy match in this slice.

Use a fixed query builder with escaped literals, selected technical output
fields, deterministic OBJECTID ordering, and a five-candidate cap. Reject
client-supplied SQL/ArcGIS expressions. A result cap overflow is ambiguous.
The table's `BIN` relates addresses to building polygons, one building to many
addresses. Resolve a unique candidate's building geometry via BIN and request
`outSR=4326`; never assume its unqualified X_COORD/Y_COORD attributes are
longitude/latitude. Multiple building matches remain ambiguous. Do not infer
active-record semantics from undocumented STATUS codes or ADU eligibility from
the layer's existing-building ADU category. Record these adapter limitations.
Retain only technical address/coordinate fields; never fetch owner/resident data.

Resolve a user-provided point or building representative point against the
official city polygon, not postal city or ZIP. The address method records its
building-geometry derivation; a building crossing the boundary is ambiguous.
Multiple candidates, boundary points, approximate locations, or missing
geometry yield `ambiguous` or `unresolved`; they never choose city rules silently.
The confirmed state means the resolved point is inside the city polygon, not
that zoning, property eligibility, or every reviewing agency was validated.
The adapter may fail without preventing selected-area lookup or offline fixtures.

Permit lookup uses only the active release and accepted facts. A response includes:

- Resolved location state, method, source snapshot, and supported scope.
- Release ID/hash and `synthetic/reviewed_public` mode.
- Candidate pathway(s), evaluated requirements, and missing project facts.
- Citations with original URL, title, locator, snapshot hash, and check date.
- Source conflicts, extraction/freshness warnings, and limits of the result.

Supported fact names for the initial subtype are `project_type`, `adu_form`,
`existing_dwelling`, and optional `floor_area_sqft`. Missing values remain unknown.
Only manifest-declared fact keys are accepted; the initial predicate evaluator
supports `all`, `any`, `not`, `eq`, `in`, `lt`, `lte`, `gt`, and `gte`. Types are
checked, and no expression runs through `eval` or dynamic SQL.

Evaluation has three values: true, false, unknown. `not unknown` is unknown;
`all` is false if any operand is false, otherwise unknown if any is unknown;
`any` is true if any operand is true, otherwise unknown if any is unknown.
An absent fact, a conflicted rule, or insufficient evidence cannot become false.
Expose `applies`, `not_applicable`, or `needs_information`, plus the missing keys.
No generated number, fee, statute reference, or guessed document enters a result.

When location is ambiguous/unresolved/outside the supported area, return a
resolution result and general source links with no property-specific checklist.
Selected Irvine area returns a clearly qualified area-level checklist. If no
active public release exists, public lookup returns `dataset_unavailable`;
synthetic fixtures are used only in explicit demo mode and are labeled throughout.

## 8. Project and timeline behavior

Project creation reruns server-side lookup using supplied location/facts and pins
the resulting release. It never trusts client-supplied applicability or boundary
verification. Require a selected supported pathway and either confirmed-point,
selected-area, or explicit synthetic-demo location. A selected-area project
retains the property-not-verified warning. Unresolved/out-of-scope cases cannot
create a supported project. Facts/location/pathway are immutable for this slice;
a corrected case creates a new project. The supported-scope predicate must be
true before creation; missing subtype/dwelling facts return 422 with missing keys.

The initial graph has six milestones: application preparation, submission,
completeness review, plan review, fee/payment readiness, and permit issuance.
These are workflow milestones, with
the exact dependencies reviewed against the city source. Construction is outside
the first timeline. Correction/resubmission cycles reopen the relevant review
milestone using a structured reason (`city_correction` or `applicant_revision`),
not an extra node or a cycle in the template graph. All six milestones belong to
the supported pathway; conditional milestone templates are deferred.

Progress is completed milestones / total milestones. Return integer
completed/total counts and a percentage rounded to one decimal; an empty graph
returns null, not 100%. Document readiness is separate: ready applicable items /
(applicable items + needs-information items). Unknown items remain pending in
that denominator; return their count and mark readiness provisional. Completing
a document cannot complete city approval.

An available next action has satisfied predecessors and required preparation
items. Return all available actions in template order. Bottlenecks carry reason
codes: `missing_information`, `missing_documents`, `awaiting_city`,
`source_conflict`, or `estimate_exceeded`. A forecast overrun is not a finding
that the city violated a statutory deadline.

Keep timing concepts separate in every response:

| Timing kind | Meaning | Computation in this slice |
|---|---|---|
| `city_service_target` | Published agency processing guidance | Display cited value, units, scope, and conditions; no promise of total elapsed time. |
| `statutory_clock` | Conditional legal decision/completeness period | Store cited guidance and verification status. Due-date/enforcement arithmetic remains disabled until direct law, triggering event, exceptions, and holiday calendar are validated. |
| `observed` | Measured comparable records | No observed estimate is initially seeded. Requires validated cohort, date definitions, sample size, deduplication, and coverage before later activation. |
| `assumption` | Explicit team estimate | Optional per-stage min/max calendar-day values, rationale, and ASSUMPTION label. Missing values remain unknown. |

An assumed finish range uses earliest-start/finish propagation through the DAG,
taking the maximum predecessor finish for parallel paths, rather than adding
every parallel duration. Required unknown stage durations make the total finish
range null with `missing_stage_estimates`. Completed milestones use actual dates;
for an in-progress stage subtract elapsed calendar days from each assumed bound
and clamp each remaining bound to zero. Not-started stages begin no earlier than
the as-of date and predecessor finishes. Forecasts require an explicit as-of date
and return current project state, not historical state reconstruction. Reject an
as-of date before the latest actual milestone date. Never make a test depend on
the wall clock. The demo uses labeled
synthetic estimates solely to exercise this calculation. The public Irvine
dataset can legitimately return no numeric finish forecast.

Checklist/milestone updates require `expected_revision`. Lock the project row,
check the revision, validate transitions and dates, and append an audit event in
the same transaction. Stale updates return 409. The server rejects completion
before predecessors are completed or required preparation is ready. Reopening a
completed prerequisite while a dependent is started/completed returns 409 until
the dependent is explicitly reopened; no silent cascade. Demoting a ready
requirement likewise requires explicitly reopening any started/completed milestone
that depends on it. Reject future event timestamps and completion before start.
Recorded corrections
reopen the relevant milestone through this same explicit transition path.

The milestone transitions are precise:

| Event | Allowed prior state | New state / date handling |
|---|---|---|
| `start` | `not_started`, with prerequisites and required items satisfied | `in_progress`; set current `started_at` to event occurrence time. |
| `complete` | `in_progress`, with prerequisites and required items satisfied | `completed`; set current `completed_at`, retaining `started_at`. |
| `reopen` | `in_progress` or `completed`, with no started/completed dependent | `not_started`; clear the current start/completion timestamps. Earlier cycles and their dates remain in immutable audit events. |

Other transitions return 409. Reopen affected dependents in reverse topological
order before the prerequisite. This makes correction/rework possible without
silently changing downstream state; a new `start` begins the next review cycle.

## 9. HTTP API contract

All application routes are under `/api/v1`; requests/responses use JSON. Unknown
request fields are rejected. Return an error envelope
`{error: {code, message, details}, request_id}`. Source links are safe public URLs;
responses never include private cache paths, secrets, or stack traces.

| Method / path | Input / result |
|---|---|
| `GET /health/live` | Process liveness; no sensitive configuration. |
| `GET /health/ready` | 200 when database/migrations are ready, including a separate dataset-availability flag. 503 for unavailable DB/schema. Empty data does not restart a healthy service; data-dependent routes return `dataset_unavailable`. |
| `GET /api/v1/jurisdictions` | Supported city/project/subtype combinations, current public release, and source check dates. |
| `POST /api/v1/locations/resolve` | One location mode; resolution status, sanitized candidates, boundary evidence. |
| `POST /api/v1/permit-lookups` | Location plus project facts; typed response defined in section 7. Stateless; no project created. |
| `GET /api/v1/sources/{snapshot_id}` | Public provenance and reviewed passage metadata. |
| `POST /api/v1/projects` | Location, facts, and pathway; creates a pinned project and initial state, returns 201. |
| `GET /api/v1/projects/{id}` | Facts, release, applicability, checklist, revision, and warnings. |
| `PATCH /api/v1/projects/{id}/requirements/{key}` | `status`, `expected_revision`; self-reported preparation status. |
| `POST /api/v1/projects/{id}/milestone-events` | Event kind, milestone key, `occurred_at`, optional structured correction code, and `expected_revision`. Returns updated revision/state. |
| `GET /api/v1/projects/{id}/timeline?as_of=YYYY-MM-DD` | Milestones, next actions, progress, bottlenecks, forecast range or explicit unavailability, and timing evidence. |
| `GET /api/v1/projects/{id}/events` | Cursor-paginated audit history, default 50 and maximum 100 events. |

Initial milestone event kinds are `start`, `complete`, and `reopen`. No free-text
notes or file attachments are accepted in this slice. Requirement updates do not
accept a claim that a city reviewed or accepted a document.

Use 422 for malformed/contradictory inputs, 401 for missing/wrong shared key,
404 for unknown IDs, 409 for revision or transition conflicts, and 503 for a
required unavailable dataset/upstream service. A valid no-match, ambiguous,
unsupported-area, or insufficient-facts lookup is a 200 domain result. The
location endpoint returns a typed upstream-unavailable result with 503 when a
live provider was requested; it never substitutes synthetic results.

Protect non-health application routes with `X-API-Key`, configured from
`CLEARPATH_API_KEY`. Imports/publication require operator CLI access to the DB;
there is no remote administrative import endpoint. CORS is disabled by default
and can use an explicit local-origin allowlist later. This is shared team demo
access, not a multi-user authorization model or a public production deployment.

## 10. Reproducible demo and future implementation layout

Proposed files, to be created only after design approval:

```text
backend/
  pyproject.toml + dependency lock
  src/clearpath/{api,ingestion,locations,permits,projects,timelines}/
  migrations/
  data/irvine_adu/manifest.json + reviewed public extracts
  tests/{unit,integration,contracts}/
  tests/fixtures/irvine_adu_synthetic/
compose.yaml
Makefile
.env.example
```

The implementation will document one-command targets `make backend-up`,
`make backend-migrate`, `make seed-demo`, `make seed-irvine`, and `make test-backend`.
These names are acceptance requirements for the future implementation, not
commands that currently exist. Synthetic and reviewed-public releases run in
separate demo/database profiles so neither can accidentally become the other's
active release. Demo mode is off by default and explicit in every result.

The demo script uses generated project IDs and a named synthetic location fixture,
without inventing a real address, parcel, applicant, or municipal decision. It
must visibly demonstrate unknown facts, an applicable checklist, missing
documents, a rejected premature completion, a successful revision update, and a
timeline with labeled assumptions. A public-data script demonstrates selected
Irvine area lookup and real citations without claiming verified parcel eligibility.

## 11. Acceptance and failure checks

| ID | Required observable result |
|---|---|
| A1 | Fresh PostgreSQL migrates successfully and has the pgvector extension. No backend command depends on frontend code or a Claude key. |
| A2 | Importing the same bundle twice leaves one release and no duplicate sources, requirements, or milestones. Concurrent publish attempts cannot leave two active releases. |
| A3 | A bad hash, invalid predicate/type, missing citation, broken reference, cyclic graph, or path traversal is rejected without a partial release. Dry-run changes nothing. |
| A4 | Garbled/unreviewed extraction cannot publish derived requirements. An unavailable refresh retains the earlier immutable evidence and reports the failure. |
| A5 | Only Irvine + the supported ADU subtype is advertised. Selected area, confirmed point, ambiguous match, boundary point, unsupported area, and provider outage have different tested outcomes. |
| A6 | Missing facts and conflicted evidence produce `needs_information`; true/false/unknown compound conditions follow section 7. Every returned sourced requirement resolves to a checked source passage. |
| A7 | Creating a project pins its release. Publishing/rolling back another release leaves existing project results unchanged. |
| A8 | Checklist completion, milestone completion, and city approval stay distinct. Stale writes, invalid dates, premature completion, and unsafe reopening return conflicts with no partial state/event writes. |
| A9 | Progress, provisional unknown counts, parallel-path forecasts, missing duration propagation, elapsed ranges, and reproducible `as_of` behavior have deterministic tests. No whole-project starter duration becomes an ADU forecast. |
| A10 | Statutory guidance is displayed with its verification gap; no legal due date is calculated. No pre-approved plan catalog is invented. |
| A11 | Demo tests run without network or private data. One opt-in live smoke check exercises source availability/address metadata without making CI depend on city uptime. |
| A12 | OpenAPI documents all domain states/errors; API-key failure, prohibited/extra input fields, invalid source URLs, and accidental secret/cache-path exposure are tested. |

Targets proposed for the hackathon: seeded local area lookup and timeline reads
have p95 under 500 ms over 100 sequential requests on a developer laptop; source
network time is excluded and reported separately. These are engineering targets,
not measurements. Use a 10-second total live-address timeout and return an
explicit outage result when exceeded. Import validation correctness takes
priority over a large data volume.

## 12. Implementation sequence after approval

1. Database migrations, configuration, health endpoints, and importer validation.
2. Synthetic fixtures plus the curated Irvine public bundle and atomic publication.
3. Location adapter boundary handling and deterministic permit lookup.
4. Projects, checklist state, milestone events, and timeline calculations.
5. Contract/integration verification, OpenAPI examples, and reproducible demo.

The next artifact after this design is approved is a Superpowers implementation
plan with exact files, task interfaces, and meaningful verification. Product code,
dependency installation, and application scaffolding have not started.
