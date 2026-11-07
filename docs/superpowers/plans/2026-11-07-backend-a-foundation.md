# ClearPath Backend A Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Person 3's runnable platform, PostgreSQL schema, manifest contract, importer/publisher, and synthetic seeds so the other backend roles can start.

**Architecture:** A small FastAPI app and synchronous operator CLI share SQLAlchemy sessions and PostgreSQL 17 with pgvector. Source-backed release data is immutable and scoped by jurisdiction, project type, and profile. Project business logic and project tables belong to Person 5; lookup belongs to Person 4.

**Tech stack:** Python 3.12; pinned FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, psycopg 3, HTTPX, Shapely, pytest; uv lock; Docker Compose.

**Spec:** [SPEC.md](../../../SPEC.md), sections 4–6 and checks A1–A4, narrowed by the user's Person 3 assignment.

## Global Constraints

- This plan supersedes execution of the broader six-task plan for this chat. Implement only Person 3 work.
- Keep `locations/`, `permits/`, `projects/`, and `timelines/` as importable placeholders. Do not implement those roles' services or project migrations.
- Preserve teammate files, existing packet builder, Lane 2 data, and all unrelated changes.
- Multiple projects and future multifamily datasets remain compatible with the shared schema. No global ADU-only constraint.
- Use a real disposable PostgreSQL database for integration verification; never use SQLite as a substitute.
- Pin dependencies and the DB image; PostgreSQL 17 plus pgvector. Default application settings are public mode; demo commands explicitly select an isolated synthetic environment.
- Only synthetic technical data is seeded here. Person 2 owns reviewed-public Irvine requirements. `seed-irvine` must fail clearly if that bundle is absent; it cannot substitute synthetic facts.
- No applicant/owner/resident values, arbitrary uploads, OCR, chat, embeddings, live GIS, or application submission.
- Source hashes, citation references, typed predicates, and an acyclic milestone graph are validated before staging. Dry-run is offline and writes nothing.
- Core commands are import/dry-run and publish. Fetcher, rollback command, and source-provenance HTTP endpoint are deferred extras, not requirements for this scoped delivery.

## Review Focus

1. Authentication/validation errors must use the shared envelope and omit secrets and raw invalid input.
2. Readiness must distinguish missing migrations from a ready DB with no active dataset.
3. A duplicate or invalid import must not create partial data or duplicate snapshots/rules.
4. Concurrent publishers must leave exactly one active release per full scope; validation/review/mode checks cannot be bypassed by the publish CLI.
5. Public and synthetic environments must remain separate; missing real data cannot be reported as available synthetic permitting expertise.

### Task 1: Runnable platform and dataset schema

**Files:** Create `backend/pyproject.toml`, `uv.lock`, `.python-version`, Dockerfile,
`alembic.ini`, `migrations/env.py`, the initial dataset migration,
`src/clearpath/{api,core,db,domain,ingestion,locations,permits,projects,timelines}/`,
root `compose.yaml`, Makefile, `.env.example`, and focused foundation tests.
Modify `.gitignore` only for generated backend/runtime files.

**Interfaces:** `create_app(settings: Settings | None = None) -> FastAPI` in
`api/app.py`; `Settings` in `core/config.py`; `DomainError` in `domain/errors.py`;
`get_session() -> Iterator[Session]` in `db/session.py`; API dependencies for the
session and `X-API-Key`. Models: Jurisdiction, SourceSnapshot, SourcePassage,
DatasetRelease, IngestionRun, Pathway, Requirement, MilestoneTemplate, citation
associations. No project tables. Document exact model names/fields for the next task.

- [ ] Write failing behavior tests for health, protected routes/error envelope,
  strict input, real migrations/vector, empty-dataset readiness, and active-release
  uniqueness. Establish a runnable test environment before recording RED.
- [ ] Implement the package/app/config/session and explicit Alembic migration.
  Include `CREATE EXTENSION vector`, source/release keys/FKs, citation associations,
  and a partial unique active-release index including project type. Default settings
  must not expose credentials or enable synthetic mode silently.
- [ ] Implement a repeatable local setup. `make backend-up backend-migrate` must
  work from a fresh clone with Docker/Compose, generating ignored local credentials
  if necessary without printing them. The Make demo workflow explicitly selects
  a separate synthetic DB/app environment, identified in health output. Container
  liveness must not wait for migrations; ready returns 503 before migration and
  200 with dataset availability false after migration. Add shared-key protection
  to an application router, keeping health endpoints public.
- [ ] Run foundation tests against real PostgreSQL 17+pgvector, plus repeat upgrade
  and a basic Docker build/start/migrate smoke. Commit named files and report RED,
  GREEN, actual dependency/image pins, commands, model contract, and any concerns.

### Task 2: Manifest schema, transactional import/publish, and synthetic seed

**Files:** Create `ingestion/{schemas.py,validation.py,service.py}`, `cli.py`,
`backend/tests/fixtures/irvine_adu_synthetic/` with manifest and source artifact,
unit/integration tests, `backend/README.md`, and the handoff manifest documentation.
Finish Make targets; update root README/CLAUDE and team-role links only as needed
to describe implemented Backend A and deferred lookup/projects.

**Interfaces:** Consume Task 1's dataset models/session/config.
Provide `validate_bundle(path: Path) -> ValidatedBundle`,
`import_bundle(session: Session, bundle: ValidatedBundle) -> ImportResult`, and
`publish_release(session: Session, release_id: UUID, reviewed: bool) -> DatasetRelease`.
The caller owns transactions. No network access in import/dry-run/publish.
Freeze and document the canonical Pydantic manifest contract, derived from the
team-role draft and SPEC.md. Keep stable source/passage/rule keys and a complete
scope key. Optional profile key may default from subtype for draft-contract
compatibility; the stored active-release key must remain unambiguous.

- [ ] Write failing tests for invalid hashes/paths/citations/types/operators,
  unknown fields, graph cycles, unreviewed derived requirements, idempotent
  duplicate import, transactional rollback, public/synthetic separation, and
  publication races. Test dry-run by observing no DB/network/file writes.
- [ ] Implement strict typed source/passages/pathways/requirements/milestone and
  conflict models; include an exported JSON Schema and working synthetic example
  for Person 2. Validate three-valued predicate syntax/types without implementing
  Person 4's runtime rule evaluator. No `eval` or dynamic SQL.
- [ ] Implement staging/import and reviewed publish with a jurisdiction row lock
  and partial uniqueness guard. Preserve immutable source versions. Reimporting
  the same content returns the same release and creates no duplicate rows;
  publication retires/activates atomically. Reject mismatched data mode and missing
  review, extraction, or citation evidence. Keep user-facing errors sanitized.
- [ ] Provide `clearpath data import --manifest PATH [--dry-run]` and
  `clearpath data publish --release UUID --reviewed`. Provide `backend-up`,
  `backend-migrate`, `seed-demo`, `seed-irvine`, `test-backend`. Seed-demo imports
  and explicitly publishes clearly labeled synthetic data. Seed-irvine requires
  a separate reviewed-public bundle and matching environment; absent data fails
  with an actionable message. No fetch/rollback/source API unless necessary to
  satisfy the core, and no placeholder claiming those features work.
- [ ] Run the full backend test suite, migrations on a fresh disposable DB, dry-run,
  repeated seed, and fresh-clone three-command smoke. Confirm health reports an
  active synthetic dataset after demo seed; real seed absence is honest. Freeze
  handoff docs and commit named files. The final report includes actual counts,
  commands, contract paths, RED/GREEN evidence, and deferred features.

## Preflight / completion

Execute Task 1 then Task 2 with independent task reviews and a whole-change review.
One implementer writes at a time; readonly runtime research can run in parallel.
Any narrower user instruction wins over the earlier whole-product plan. Finish by
publishing a reviewable branch/PR for the foundation without overwriting shared
main changes or merging another role's unfinished work.
