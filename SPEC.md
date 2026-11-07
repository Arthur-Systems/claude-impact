# ClearPath backend design

Date: November 7, 2026

Status: Proposed design; awaiting user approval before implementation.

Scope: Lane 2 — Clear it. Backend only.

Product scope: a portfolio of housing projects, including affordable-housing projects.

First populated rule dataset: Irvine, California; accessory dwelling unit (ADU).

## 1. Outcome

Help nonprofit housing project managers, small builders, and applicants manage
multiple housing projects, find the relevant permitting process for each, and
track documents, missing facts, and review milestones. Affordable-housing
development is the product goal; Irvine ADU is the first sourced demonstration.
The first release supplies three working backend capabilities:

1. A PostgreSQL database and repeatable dataset importer for curated public sources.
2. Address or area lookup returning sourced, conditional permit checklists.
3. Separate project checklists and timelines, plus a portfolio list with filters.

Success is a reproducible API demonstration: seed a database, create two Irvine
ADU projects, update each independently, and list their separate progress. Also
save an affordable multifamily project as a draft whose missing rule coverage is
explicit. The demo must work from a checked-in public fixture bundle without
Claude credentials, a paid geocoder, or a live municipal website. Live address
resolution is a separate, honestly reported integration capability.

### Fit with the affordable-housing challenge

The [Lane 2 brief](lanes/2-clear-it/README.md) explicitly includes
nonprofit project managers, builders, ADUs, small subdivisions, and multifamily
approval pathways. ClearPath addresses the preparation and approval delays that
can slow housing delivery. Its value must be demonstrated through a sourced next
action, a missing requirement caught before submission, and a visible bottleneck
for a housing team. A portfolio also supports the judging criterion of a credible
path to more projects; it is not evidence that any homes have already been built.

ADUs are not automatically affordable or deed-restricted. Record a team's
affordability goal as declared intent, with `affordability_verification=not_assessed`.
Do not claim income eligibility, restricted rents, affordability certification,
subsidy qualification, or housing production from permit progress. Funding and
affordability-compliance engines remain outside these first backend modules.

## 2. Decisions and boundaries

**User decisions:** ClearPath; FastAPI/Python; PostgreSQL with pgvector; Irvine +
ADU as the first dataset; multiple housing projects and affordable-housing focus;
frontend later; begin with ingestion, lookup, and timelines.

Confirmed dataset sequence: **keep Irvine ADU first; add affordable multifamily
rules next**. The [implementation plan](../plans/2026-11-07-clearpath-backend.md)
preserves this order and multi-project support from the first release.

**Proposed engineering defaults:** a single FastAPI application with separate
modules, synchronous operator-run ingestion, one shared demo workspace containing
many independent projects, and
deterministic checklist evaluation. These defaults are recommendations for this
spec, rather than additional user requirements.

The initial backend excludes frontend code, a chat assistant, embedding generation,
vector search, user PDF uploads, OCR, accounts, multiple workspaces, live permit
status scraping, application submission, and messaging. It does not decide legal
eligibility or guarantee approval. Claude-based explanations and document search
can consume the same source references in a later slice; core results cannot
depend on generated prose. Enabling pgvector is included; building a vector index
without an embedding model and retrieval task is deferred.

The first curated rule profile uses a **proposed detached ADU on a lot with an
existing dwelling** as the demo default. This limits the initial verified data
coverage, not which housing projects can be saved. The project model supports
ADU, duplex, multifamily, and other housing cases, with optional subtype and
unit-count/affordability goals. Unsupported profiles can be saved as drafts;
they receive no invented ADU checklist or timeline. Adding a sourced profile
uses the same importer, lookup engine, and project services.

Completing this first backend does not require a second regulatory corpus,
other lanes, calculated fees from incomplete schedules, financing, construction
scheduling, or parcel/zoning eligibility. Multifamily rule coverage is a next
dataset, with a visible gap until its sources are curated.

## 3. Existing evidence and source limitations

The current repository contains event materials and a separate
[demo ADU packet builder](clear_path_checklist_build/README.md), but no
FastAPI permit service or application database. The packet includes a blank PDF
and a document/field schema and labels itself as an abbreviated testing sample,
not an official city form. Preserve its stable document/field IDs as possible
future integration keys, without treating sample `required` flags as verified
regulatory rules or ingesting filled applicant/owner fields. Packet upload/OCR
integration remains outside this first backend slice.

Three starter files need distinct handling:

| File | Actual contents | Import behavior |
|---|---|---|
| `lanes/2-clear-it/data/oc-cities.json` | 34 city names; every permit URL, checklist URL, fee URL, and checked date is null | Import the city registry as reference metadata. Only Irvine initially has a curated rule profile. Registry presence does not imply permitting coverage; null stays unknown. |
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
| `projects` | Save/list multiple housing projects; edit drafts; activate guidance against a pinned matching release; isolate every project's state. |
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
| `jurisdictions` | `id`, unique slug, name, state, timezone, optional boundary snapshot reference. Irvine's seed values are `irvine-ca`/`CA`, not schema constants. The registry and published rule-coverage catalog are separate; a city name is not location verification. |
| `source_snapshots` | `id`, stable source key, canonical URL, title, publisher, authority type, MIME type, fetched/checked timestamps, optional effective dates, SHA-256, local artifact key, extraction status, review status. Unique `(source_key, sha256)`. Failed fetches do not replace a working snapshot. |
| `source_passages` | `id`, snapshot FK, locator (`page` or HTML heading/anchor), reviewed excerpt, excerpt hash. A citation resolves to one immutable snapshot and passage. |
| `ingestion_runs` | `id`, manifest hash, command kind, start/end timestamps, status, counts, sanitized error codes, resulting release FK. Duplicate import of the same manifest and content returns the same release. |
| `dataset_releases` | `id`, jurisdiction FK, project type, explicit profile/subtype key, fact schema, content hash, schema version, normalized manifest JSON including source conflicts, `draft/active/retired`, `synthetic/reviewed_public`, created/published timestamps, curator label. At most one active release per `(jurisdiction, project_type, profile_key)`. No global ADU-only constraint; content is immutable after staging. |
| `pathways` | `id`, release FK, unique release-local key, title, applicability predicate, explanatory text, citation IDs. A candidate process is not approval eligibility. |
| `requirements` | `id`, release FK, unique release-local key, pathway key(s), `permit/document/review`, title, description, applicability predicate, required-for-preparation flag, citation IDs. Source-dependent requirements require at least one reviewed citation. |
| `milestone_templates` | `id`, release FK, pathway key, stable key, title, predecessor keys, associated requirement keys, optional forecast range, optional published clock metadata, citation IDs. Graph must be acyclic and every reference must resolve within its release. |
| `projects` | `id`, nonpersonal `project_label` (1–80 characters), project type, optional subtype/jurisdiction, declared location, optional proposed unit count, affordability goal, optional affordable-unit goal, `draft/active`, nullable pinned release FK/pathway, validated rule facts, location evidence, `revision`, created/updated timestamps. Drafts have no pinned release/pathway; active projects require both. No owner/applicant identity, contact details, or uploaded documents. |
| `project_requirements` | Project/requirement composite key; `not_started/in_progress/ready`, updated timestamp. Applicability comes from the rule engine; a client cannot mark an inapplicable requirement applicable. Ready is self-reported preparation, not municipal acceptance. |
| `project_milestones` | Project/template composite key; `not_started/in_progress/completed`, actual start/completion timestamps. Blocked/available states are derived from prerequisites and required documents. |
| `project_events` | `id`, project FK, unique project revision, event type, occurrence and recording timestamps, minimal structured payload. Append-only audit trail, committed with the state change. |

Citation IDs are stored as typed UUID arrays in the manifest and resolved to
passage rows on import; persistence uses join tables or constrained association
rows so deleting a cited passage cannot leave dangling evidence. The implementer
may choose the association-table layout without changing the API contract.

Use a partial unique index over jurisdiction/type/profile for the active-release constraint and lock the
jurisdiction row during publication. Retiring the old release and activating the
new one happen in one transaction. Existing projects retain their original
release; this slice offers no automatic project migration. Publishing a dataset
must not automatically activate drafts. Every child lookup/mutation is scoped by
project ID, and its requirement/milestone must belong to that project's pinned
release. Updating one project's state or revision cannot change another project,
even when both share the same release and requirement keys. This is record
isolation in a shared workspace, not multi-tenant authorization. PostgreSQL documents
the required [row-lock behavior](https://www.postgresql.org/docs/17/explicit-locking.html).

## 6. Dataset injector contract

The first dataset directory will be `backend/data/irvine_adu/`; the importer accepts
other named bundles using the same schema. A manifest
contains `schema_version`, jurisdiction, project type, profile/subtype, fact schema, source descriptors, reviewed
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

Support either a structured address, WGS84 coordinates, or an explicit registered
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

Common project metadata is independent of a regulatory manifest: `project_label`,
`project_type` (`adu/duplex/multifamily/other_housing`), optional subtype and
jurisdiction, `proposed_unit_count`, `affordability_goal`
(`affordable_housing/mixed_income/unspecified`), and `affordable_unit_count_goal`.
Counts are optional integers: proposed units must be positive, affordable-unit
goal nonnegative and no greater than the total when both are supplied. These are
declared project goals, not verified outcomes. Do not store income or resident data.

Rule-specific facts are separate and validated against the matching manifest's
fact schema. The first ADU profile uses `adu_form`, `existing_dwelling`, and
optional `floor_area_sqft`; project type comes from common metadata and cannot
contradict it. A draft without a matching manifest accepts common metadata and
an empty rule-facts object, rather than arbitrary unvalidated facts. Missing
evaluated values remain unknown. Only manifest-declared rule fact keys are
accepted; the initial predicate evaluator
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
An area with a matching profile returns a clearly qualified area-level checklist.
A known city/type/profile without curated coverage returns a 200
`rule_coverage_unavailable` result with no generated checklist. A configured
profile whose required active dataset is operationally unavailable returns
`dataset_unavailable` (503). Never substitute the ADU profile for another housing type;
synthetic fixtures are used only in explicit demo mode and are labeled throughout.

## 8. Project and timeline behavior

The shared workspace supports many projects from the first release. Creation
saves a draft with common metadata and a declared location, even when facts,
location resolution, or a matching dataset are unavailable. Drafts have
`coverage_status=unconfigured`, no release/pathway, no generated checklist or
milestones, and null progress/forecast. Their locally derived coverage reason is
`rule_coverage_unavailable`, `missing_information`, `location_unresolved`, or
`activation_required`, based on the current catalog and known scope facts. This
does not silently run a live address lookup.

Draft metadata/location/rule facts can be edited with `expected_revision`.
Activation is a separate explicit operation: rerun server-side lookup, require
a matching active profile and selected pathway, and pin its release in the same
transaction that creates project checklist/milestone rows. Never trust a
client's applicability or boundary result. Require confirmed-point,
selected-area, or explicit synthetic-demo location and a true profile scope
predicate. Missing facts or unsupported types leave the draft intact and return
409 with the corresponding missing-information/coverage reason. A selected-area
project retains its property-not-verified warning. Successful activation changes
the state to `active` and `coverage_status=configured`.

Failed activation returns the reason and unchanged current revision in its 409
response. It writes no project state, partial checklist/milestone rows, or audit
event. Draft edits recompute local coverage reasons. Stale/invalid requests also
write no state or event. Active project facts/location/pathway stay immutable for this
slice; corrections that change rule scope use a new draft project.

Portfolio listing supports filters for city, project type, draft/active state,
and configured/unconfigured coverage. It reports each project's ID, label,
declared housing/affordability goals, scope, revision, coverage, and progress
summary. A team can track multiple supported projects independently and retain
other housing opportunities as explicitly unconfigured drafts.

The initial graph has six milestones: application preparation, submission,
completeness review, plan review, fee/payment readiness, and permit issuance.
These are workflow milestones, with
the exact dependencies reviewed against the city source. Construction is outside
the first timeline. Correction/resubmission cycles reopen the relevant review
milestone using a structured reason (`city_correction` or `applicant_revision`),
not an extra node or a cycle in the template graph. All six milestones belong to
the first ADU profile. Other profiles supply their own graph through the dataset
manifest; the application does not hard-code ADU milestones as a universal
housing process. Conditional nodes within one graph are deferred.

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
| `GET /api/v1/jurisdictions` | City reference registry with an explicit list of curated type/profile coverage, current public releases, and source check dates. No coverage is inferred from registry membership. |
| `POST /api/v1/locations/resolve` | One location mode; resolution status, sanitized candidates, boundary evidence. |
| `POST /api/v1/permit-lookups` | Location plus project facts; typed response defined in section 7. Stateless; no project created. |
| `GET /api/v1/sources/{snapshot_id}` | Public provenance and reviewed passage metadata. |
| `POST /api/v1/projects` | Common metadata, declared location, and optional validated rule facts; creates a draft, returns 201 even when rule coverage is unavailable. |
| `GET /api/v1/projects` | Cursor pagination, default 50/max 100; city, project type, state, and coverage filters; stable `(created_at, id)` ordering. Returns project summaries and `next_cursor`. |
| `GET /api/v1/projects/{id}` | Metadata/goals, facts, nullable release, coverage state/reason, checklist, revision, and warnings. Draft generated checklist is empty. |
| `PATCH /api/v1/projects/{id}` | Draft-only metadata/location/rule-fact updates with `expected_revision`; reject edits to active project scope with 409. |
| `POST /api/v1/projects/{id}/activate` | Pathway key and `expected_revision`; server revalidates scope and atomically pins a matching release and generates state. Failure keeps a draft and returns the reason/revision. |
| `PATCH /api/v1/projects/{id}/requirements/{key}` | `status`, `expected_revision`; self-reported preparation status. |
| `POST /api/v1/projects/{id}/milestone-events` | Event kind, milestone key, `occurred_at`, optional structured correction code, and `expected_revision`. Returns updated revision/state. |
| `GET /api/v1/projects/{id}/timeline?as_of=YYYY-MM-DD` | Active: project-specific milestones/progress/timing. Draft: 200 `timeline_unconfigured`, empty generated milestones, null progress/forecast, and coverage reason. |
| `GET /api/v1/projects/{id}/events` | Cursor-paginated audit history, default 50 and maximum 100 events. |

Initial milestone event kinds are `start`, `complete`, and `reopen`. No free-text
notes or file attachments are accepted in this slice. Requirement updates do not
accept a claim that a city reviewed or accepted a document.
Checklist/milestone mutations on drafts return 409 `project_not_active`.

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

The demo script creates two ADU projects from the same profile, activates both,
and updates only one before checking the other's unchanged state. It also saves
an affordable multifamily draft and shows its explicit unavailable rule coverage
in portfolio filtering and timeline responses. Use generated project IDs and a named synthetic location fixture,
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
| A5 | Only Irvine + the seeded ADU profile is advertised as curated rule coverage. Multiple housing types can be saved as drafts; selected area, confirmed point, ambiguous/boundary match, coverage gaps, and provider outage remain distinct. |
| A6 | Missing facts and conflicted evidence produce `needs_information`; true/false/unknown compound conditions follow section 7. Every returned sourced requirement resolves to a checked source passage. |
| A7 | Draft creation needs no active release. Explicit activation pins a matching release atomically; publishing/rolling back a release neither rewrites active projects nor silently activates drafts. |
| A8 | Checklist completion, milestone completion, and city approval stay distinct. Stale writes, invalid dates, premature completion, and unsafe reopening return conflicts with no partial state/event writes. |
| A9 | Progress, provisional unknown counts, parallel-path forecasts, missing duration propagation, elapsed ranges, and reproducible `as_of` behavior have deterministic tests. No whole-project starter duration becomes an ADU forecast. |
| A10 | Statutory guidance is displayed with its verification gap; no legal due date is calculated. No pre-approved plan catalog is invented. |
| A11 | Demo tests run without network or private data. One opt-in live smoke check exercises source availability/address metadata without making CI depend on city uptime. |
| A12 | OpenAPI documents all domain states/errors; API-key failure, prohibited/extra input fields, invalid source URLs, and accidental secret/cache-path exposure are tested. |
| A13 | Two active projects sharing a release/key have independent checklist status, milestones, revision, events, and forecasts. Updating A leaves B unchanged; an item belonging to another project's release cannot be mutated through A. |
| A14 | Portfolio pagination/filtering returns both supported ADU projects and an affordable multifamily draft correctly. Draft reads expose empty generated state/null timing; failed activation preserves the draft and its revision, reports the coverage reason, and creates no partial guidance state. |
| A15 | Affordability/unit goals stay labeled as declared intent with verification `not_assessed`. No ADU or permit progress is presented as proof of affordable-housing qualification or homes built. |

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
4. Project portfolio/drafts, explicit guidance activation, isolated checklist state,
   milestone events, and timeline calculations.
5. Contract/integration verification, OpenAPI examples, and reproducible demo.

The next artifact after this design is approved is a Superpowers implementation
plan with exact files, task interfaces, and meaningful verification. Implementation,
dependency installation, and scaffolding for this backend design have not started;
the independently added packet builder is an existing separate component.
