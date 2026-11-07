# Backend A: platform, database and dataset import (hackathon slice)

**Status:** approved design, November 7, 2026. Owner: Person 3 (Backend A).
**Parent spec:** [SPEC.md](../../../SPEC.md). This document narrows SPEC sections 4, 5, 6 and 10
to what Backend A builds today (plan Tasks 1 and 2). Where the two differ, this document
governs today's build and the difference is listed in "Deferred and deviations".

## 1. Goal

Give the team a running service and database by 12:30 PM:

- Persons 4 and 5 can write code in their own packages against real tables and a session.
- Person 2 can enter Irvine ADU content into a frozen manifest format and import it.
- Person 1 can hit a health endpoint and, once lookups exist, a stable error format.

**Done means:** on a fresh clone,
`make backend-up backend-migrate seed-demo run` starts the API, and
`GET /health/ready` returns 200 with `dataset_available: true` in synthetic mode.

## 2. Repository layout

```text
compose.yaml                 # Postgres 17 + pgvector, loopback only
Makefile
.env.example                 # variable names and harmless placeholders only
backend/
  pyproject.toml, uv.lock    # uv project, Python 3.12, exact versions locked
  alembic.ini
  migrations/                # env.py + versions/0001_initial.py
  src/clearpath/
    __init__.py
    cli.py                   # Typer app: `clearpath data ...`
    core/config.py           # Settings
    db/session.py            # engine, SessionLocal, get_session
    db/models.py             # every ORM model (sections 4 and 5)
    domain/errors.py         # DomainError
    domain/schemas.py        # StrictModel base, shared enums
    api/app.py               # create_app, health routes, error handlers
    api/dependencies.py      # require_api_key, get_settings
    api/routes/__init__.py   # empty; P4/P5 add route modules here
    ingestion/schemas.py     # manifest Pydantic models (the contract)
    ingestion/validation.py  # cross-reference, predicate and graph checks
    ingestion/service.py     # import_bundle, publish_release, import_cities
    permits/predicates.py    # ALLOWED_OPS only; evaluator belongs to P4
    locations/ permits/ projects/ timelines/   # empty __init__.py, owned by P4/P5
  data/irvine_adu/manifest.json               # Person 2 fills; starts as a stub
  tests/
    conftest.py
    fixtures/irvine_adu_synthetic/manifest.json
    integration/test_foundation.py
    integration/test_ingestion.py
    unit/test_manifest_validation.py
```

`clear_path_checklist_build/` stays unchanged. Its packet `required` flags are not rules.

## 3. Foundation (plan Task 1)

### 3.1 Dependencies

Runtime: fastapi, uvicorn[standard], pydantic 2, pydantic-settings, sqlalchemy 2, alembic,
psycopg[binary] 3, typer. Dev: pytest, httpx (for FastAPI TestClient). `uv lock` pins exact
versions; commit `uv.lock`. Shapely and HTTPX runtime use are added by Person 4 when needed.

### 3.2 Compose

One service `db`: image `pgvector/pgvector:pg17`, env `POSTGRES_USER/PASSWORD/DB=clearpath`,
port `127.0.0.1:5432:5432`, named volume `clearpath-pg`, healthcheck `pg_isready -U clearpath`.
The API runs on the host with `uv run` (no API container today), bound to `127.0.0.1:8000`.

Tests use a second database `clearpath_test` on the same server, created by `make test-backend`
if missing. Tests never use SQLite.

### 3.3 Settings (`core/config.py`)

| Env var | Field | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | `database_url` | `postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath` | |
| `CLEARPATH_API_KEY` | `api_key` (SecretStr) | none, required | Startup fails if unset |
| `CLEARPATH_MODE` | `mode` | `public` | `public` or `synthetic`; decides which release kind the API serves |
| `CLEARPATH_CORS_ORIGINS` | `cors_origins` | empty list | CORS off unless set (Person 1 may need `http://localhost:5173`) |

Settings never appear in responses or logs.

### 3.4 Session (`db/session.py`)

Synchronous SQLAlchemy 2. `get_session()` yields a `Session` and closes it. **Routes and CLI
commands own the transaction and call `commit()`; service functions receive a `Session` and never
commit.** This is the rule Persons 4 and 5 follow.

### 3.5 App (`api/app.py`, `api/dependencies.py`)

- `create_app(settings: Settings | None = None) -> FastAPI`. Run with
  `uvicorn --factory clearpath.api.app:create_app`.
- `GET /health/live` → `200 {"status":"ok"}`. No auth.
- `GET /health/ready` → no auth. Checks `SELECT 1`, that the Alembic head is applied, and whether
  an active release of the kind matching `mode` exists:
  `200 {"status":"ready","database":true,"schema":true,"dataset_available":bool,"mode":"public|synthetic"}`;
  `503` with the same shape and `status:"unavailable"` if the DB or schema check fails.
- `require_api_key`: reads `X-API-Key`, compares with `secrets.compare_digest`; missing or wrong →
  `401 unauthorized`. Every router under `/api/v1` is mounted with this dependency.
- Error envelope on every non-2xx: `{"error":{"code":str,"message":str,"details":{}},"request_id":str}`.
  `request_id` is a UUID4 generated per request and returned in the `X-Request-ID` header.
- `DomainError(code, message, details=None, http_status=400)` in `domain/errors.py` → envelope.
- `RequestValidationError` → `422 validation_error`, `details.fields` lists field paths and error
  types only, never the submitted values.
- Unhandled exceptions → `500 internal_error` with no stack trace in the body.
- `StrictModel` in `domain/schemas.py` = `BaseModel` with `extra="forbid"`. Every request model
  inherits it, so unknown fields return 422.
- One test-only protected route `GET /api/v1/_ping` returns `{"ok":true}`; remove it once a real
  route exists.

Shared enums in `domain/schemas.py`: `ProjectType = adu|duplex|multifamily|other_housing`,
`ReleaseKind = synthetic|reviewed_public`, `ReleaseStatus = draft|active|retired`,
`AffordabilityGoal = affordable_housing|mixed_income|unspecified`.

## 4. Database schema (single migration `0001_initial`)

All IDs are UUID (generated in Python). All timestamps are `timestamptz` in UTC. The migration
first runs `CREATE EXTENSION IF NOT EXISTS vector`; no vector columns exist today.

### 4.1 Reference and dataset tables

| Table | Columns | Constraints |
|---|---|---|
| `jurisdictions` | id, slug, name, state, timezone (default `America/Los_Angeles`), permit_page_url, adu_checklist_url, fee_schedule_url, checked_at (all four nullable) | `slug` unique |
| `dataset_releases` | id, jurisdiction_id FK, project_type, profile_key, kind, status, schema_version, content_hash, fact_schema JSONB, conflicts JSONB, curator_label, created_at, published_at nullable | `UNIQUE(content_hash)`; partial unique index on `(jurisdiction_id, project_type, profile_key, kind) WHERE status='active'` |
| `source_snapshots` | id, release_id FK, source_key, url, title, publisher, authority_type, checked_at, sha256 nullable, verification_depth, terms_note nullable | `UNIQUE(release_id, source_key)` |
| `source_passages` | id (DB-generated), release_id FK, manifest_passage_id (UUID from manifest), snapshot_id FK, locator, excerpt, excerpt_hash, review_status | `UNIQUE(release_id, manifest_passage_id)`. A new release of an edited manifest may reuse passage UUIDs, so the manifest UUID is not the primary key |
| `pathways` | id, release_id FK, key, title, applies_if JSONB, description | `UNIQUE(release_id, key)` |
| `requirements` | id, release_id FK, key, pathway_keys JSONB, kind, title, description, applies_if JSONB, required_for_preparation bool | `UNIQUE(release_id, key)` |
| `milestone_templates` | id, release_id FK, key, position int, title, predecessors JSONB, requirement_keys JSONB, published_clock JSONB nullable, assumed_days JSONB nullable | `UNIQUE(release_id, key)` |
| `citation_links` | id, release_id FK, owner_type (`pathway/requirement/milestone`), owner_key, passage_id FK → `source_passages.id` (resolved from the manifest UUID within the same release) | `UNIQUE(release_id, owner_type, owner_key, passage_id)`; passage FK `ON DELETE RESTRICT` |
| `ingestion_runs` | id, manifest_path (repo-relative), content_hash, command, status (`ok/no_op/failed`), counts JSONB, error_codes JSONB, release_id FK nullable, started_at, finished_at | |

Release content is immutable after import: no service updates pathway, requirement, milestone,
source or passage rows. Only `dataset_releases.status` and `published_at` change.

### 4.2 Project tables (written here so Person 5 starts with them)

| Table | Columns | Constraints |
|---|---|---|
| `projects` | id, project_label (1-80 chars), project_type, subtype nullable, jurisdiction_id FK nullable, location JSONB, proposed_unit_count nullable, affordability_goal, affordable_unit_count_goal nullable, state (`draft/active`), release_id FK nullable, pathway_key nullable, rule_facts JSONB default `{}`, revision int default 1, created_at, updated_at | CHECK: `state='draft'` ⇒ release_id and pathway_key NULL; `state='active'` ⇒ both NOT NULL. CHECK unit counts ≥ 0 and affordable ≤ proposed when both set |
| `project_requirements` | project_id FK, requirement_key, status (`not_started/in_progress/ready`), updated_at | PK `(project_id, requirement_key)` |
| `project_milestones` | project_id FK, milestone_key, status (`not_started/in_progress/completed`), started_at, completed_at | PK `(project_id, milestone_key)` |
| `project_events` | id, project_id FK, revision, event_type, occurred_at, recorded_at, payload JSONB | `UNIQUE(project_id, revision)` |

No owner, applicant, contact or upload columns exist. Person 5 may add columns in a later
migration `0002_*`; they do not edit `0001`.

## 5. Manifest contract (frozen at 11:45 with Person 2)

Pydantic models in `ingestion/schemas.py`, all `extra="forbid"`. Example (values are
placeholders, not facts):

```json
{
  "schema_version": 1,
  "kind": "reviewed_public",
  "jurisdiction": "irvine-ca",
  "project_type": "adu",
  "profile_key": "irvine-adu-detached-existing-dwelling",
  "curator_label": "Person 2, checked 2026-11-07",
  "fact_schema": {
    "adu_form": {"type": "enum", "values": ["detached", "attached", "conversion", "jadu"]},
    "existing_dwelling": {"type": "bool"},
    "floor_area_sqft": {"type": "number"}
  },
  "sources": [{
    "key": "IRV-ADU",
    "url": "https://cityofirvine.gov/...",
    "title": "<page title>",
    "publisher": "City of Irvine",
    "authority_type": "city_guidance",
    "checked_at": "2026-11-07",
    "sha256": null,
    "verification_depth": "full_text_read",
    "terms_note": null
  }],
  "passages": [{
    "id": "7f9c2b1e-0000-4000-8000-000000000001",
    "source_key": "IRV-ADU",
    "locator": "#submittal-requirements",
    "excerpt": "<exact text copied from the source>",
    "review_status": "reviewed"
  }],
  "pathways": [{
    "key": "irvine_adu_standard",
    "title": "<title>",
    "description": "<plain language>",
    "applies_if": {"eq": ["adu_form", "detached"]},
    "citations": ["7f9c2b1e-0000-4000-8000-000000000001"]
  }],
  "requirements": [{
    "key": "building_permit_application",
    "pathways": ["irvine_adu_standard"],
    "kind": "document",
    "title": "<city's own name>",
    "description": "<plain language, no invented details>",
    "applies_if": {"all": [{"eq": ["existing_dwelling", true]}]},
    "required_for_preparation": true,
    "citations": ["7f9c2b1e-0000-4000-8000-000000000001"]
  }],
  "milestones": [{
    "key": "application_preparation",
    "title": "<title>",
    "predecessors": [],
    "requirements": ["building_permit_application"],
    "published_clock": null,
    "assumed_days": null,
    "citations": []
  }],
  "conflicts": []
}
```

Field rules:

- `kind`: `synthetic` or `reviewed_public`. `profile_key`, every `key`: lowercase slug
  `^[a-z0-9][a-z0-9_-]{0,79}$`. `jurisdiction` must match a seeded `jurisdictions.slug`.
- `fact_schema` types: `bool`, `number` (int or float), `enum` (with `values`), `string`.
- `sources[].verification_depth`: `full_text_read`, `title_only` or `blocked`. `sha256`: null or
  64 lowercase hex characters (null means "not hashed", shown as such in provenance).
  `url` must be `https://` with no credentials.
- `passages[].review_status`: `reviewed`, `needs_review` or `failed`. Garbled PDF text is
  `needs_review` until a person types a checked excerpt.
- `requirements[].kind`: `permit`, `document` or `review`.
- `milestones[].assumed_days`: null, or `{"min":int|null,"max":int|null,"label":"ASSUMPTION","rationale":str}`;
  `label` must equal `ASSUMPTION`; `min ≤ max` when both set.
  `published_clock`: null or `{"text":str,"citations":[uuid]}`, displayed only, never computed.
- `conflicts[]`: `{"rule_keys":[str],"source_keys":[str],"summary":str}`.
- Milestone `position` is its index in the `milestones` array.

### Predicate grammar

A predicate is a JSON object with exactly one key:

| Operator | Shape |
|---|---|
| `all`, `any` | list of ≥ 1 predicates |
| `not` | one predicate |
| `eq`, `lt`, `lte`, `gt`, `gte` | `[fact_name, literal]` |
| `in` | `[fact_name, [literal, ...]]` |

`permits/predicates.py` exports `ALLOWED_OPS` and `validate_predicate(pred, fact_schema)`.
Validation checks shape, that `fact_name` exists in `fact_schema`, and that literals match the
fact's type (enum literals must be in `values`; `lt/lte/gt/gte` only on `number`). Evaluation
(three-valued logic) is Person 4's `evaluate_predicate` in the same module. Nothing is `eval`'d.

## 6. Validation, import and publish (plan Task 2)

### 6.1 `validate_bundle(path) -> ValidatedBundle`

Pure function, no DB or network. Fails with a list of `{code, path}` errors (no excerpt or
value text in error output). Checks:

| Code | Rejected when |
|---|---|
| `schema_invalid` | Pydantic validation fails (unknown field, wrong type, bad slug, bad URL) |
| `unsupported_schema_version` | `schema_version != 1` |
| `path_outside_bundle` | manifest path resolves outside `backend/data/` or `backend/tests/fixtures/` |
| `duplicate_key` | duplicate source key, passage id, pathway, requirement or milestone key |
| `dangling_reference` | passage → unknown source; citation → unknown passage; requirement → unknown pathway; milestone → unknown predecessor or requirement; conflict → unknown rule or source key |
| `invalid_predicate` | `validate_predicate` fails |
| `cyclic_milestones` | milestone predecessor graph has a cycle (Kahn's algorithm) |
| `missing_citation` | a pathway or requirement in a `reviewed_public` bundle has no citations |

`content_hash` = SHA-256 of the manifest re-serialized with sorted keys and no whitespace.

### 6.2 `import_bundle(session, bundle) -> ImportResult`

- If a release with the same `content_hash` exists: return it with `no_op=True`, write nothing
  except an `ingestion_runs` row with `status=no_op`.
- Otherwise, in the caller's transaction, insert the release (`status=draft`), sources, passages
  (computing `excerpt_hash`), pathways, requirements, milestones and `citation_links`. Any error
  rolls back the whole release.
- `ImportResult`: `release_id`, `no_op`, `counts` per table.

### 6.3 `publish_release(session, release_id, reviewed: bool, mode) -> DatasetRelease`

- `reviewed` must be true, else `review_confirmation_required`.
- Release must be `draft`, else `release_not_draft`.
- `kind=synthetic` cannot be published by a CLI running with `mode=public`, and vice versa
  (`release_kind_mismatch`).
- Any pathway, requirement or milestone citing a passage whose `review_status != reviewed` →
  `unreviewed_evidence` (lists owner keys).
- Then `SELECT ... FOR UPDATE` the jurisdiction row, set the current active release for the same
  `(jurisdiction, project_type, profile_key, kind)` to `retired`, set this one `active` with
  `published_at=now()`. Same transaction. Existing projects keep their `release_id`.

### 6.4 `import_cities(session, path)`

Upserts the 34 entries of `lanes/2-clear-it/data/oc-cities.json` by slug
(`<name lowercased, spaces to hyphens>-ca`), keeping null URL fields null. Re-running changes
nothing. Registry presence is not rule coverage.

### 6.5 CLI (`clearpath` entry point, Typer)

| Command | Behavior | Exit |
|---|---|---|
| `clearpath data import-cities [--path P]` | 6.4; prints count | 0 |
| `clearpath data import --manifest P --dry-run` | 6.1 only; prints counts or errors; no DB connection | 0 ok / 1 errors |
| `clearpath data import --manifest P` | 6.1 then 6.2, commit; prints release id and `no_op` | 0 / 1 |
| `clearpath data publish --release ID --reviewed` | 6.3, commit | 0 / 1 |

Errors print as `code: path` lines. No stack traces unless `--debug`.

## 7. Seeds and Make targets

**Synthetic fixture** `backend/tests/fixtures/irvine_adu_synthetic/manifest.json`:
`kind: synthetic`, jurisdiction `irvine-ca`, profile `irvine-adu-detached-existing-dwelling`,
one source with title `SYNTHETIC TEST SOURCE` and `url: https://example.org/synthetic`,
3 requirements (one conditioned on `floor_area_sqft` so `needs_information` can be exercised),
the 6 milestones from SPEC section 8 with `assumed_days` labeled ASSUMPTION and rationale
"synthetic test value". No real address, fee, deadline or form name.

**Real bundle** `backend/data/irvine_adu/manifest.json`: starts as a valid stub with
`kind: reviewed_public` and empty rule lists; Person 2 fills it.

| Target | Runs |
|---|---|
| `make backend-up` | `docker compose up -d --wait db` |
| `make backend-migrate` | `uv run --project backend alembic upgrade head` |
| `make seed-cities` | `clearpath data import-cities` |
| `make seed-demo` | seed-cities, import synthetic fixture, publish it with `CLEARPATH_MODE=synthetic` |
| `make seed-irvine` | seed-cities, import real bundle, publish with `CLEARPATH_MODE=public` |
| `make run` | uvicorn factory on 127.0.0.1:8000 (reads `.env`) |
| `make test-backend` | create `clearpath_test` if missing, migrate it, `pytest backend/tests -q` |

`.env.example` (four lines): `DATABASE_URL=<the default above>`, `CLEARPATH_API_KEY=change-me`,
`CLEARPATH_MODE=synthetic`, `CLEARPATH_CORS_ORIGINS=`.

## 8. Tests

All against `clearpath_test`; each test runs in a transaction rolled back at teardown, except the
migration test.

| Test | Asserts |
|---|---|
| `test_migration_creates_schema` | extension `vector` present; all 13 tables exist; second `upgrade head` is a no-op |
| `test_health` | live 200; ready 200 with `dataset_available:false` on empty DB; no settings values in body |
| `test_api_key` | `/api/v1/_ping` 401 without/with wrong key, 200 with key; 401 body is the envelope |
| `test_extra_fields_rejected` | a StrictModel request with an unknown field → 422 envelope without echoing values |
| `test_validation_rejects` | one bad manifest per code in 6.1 → that code, no DB access |
| `test_dry_run_writes_nothing` | row counts unchanged after dry run |
| `test_reimport_is_noop` | same release id, identical row counts |
| `test_publish_retires_previous` | publish A then B (same scope) → A retired, B active; a project pinned to A keeps A |
| `test_publish_rejects_unreviewed` | release citing a `needs_review` passage → `unreviewed_evidence`, stays draft |
| `test_publish_kind_mismatch` | synthetic release with mode public → `release_kind_mismatch` |
| `test_project_state_check` | inserting an active project without release fails the CHECK |
| `test_import_cities_idempotent` | 34 rows, rerun leaves 34, null URLs stay null |

## 9. Handoffs and checkpoints

| By | Deliver | To |
|---|---|---|
| 11:45 | Package skeleton pushed; `ingestion/schemas.py` + example manifest frozen | P2, P4, P5 |
| 12:15 | Migration, models, `get_session`, `DomainError`, `StrictModel`, `ALLOWED_OPS` merged to main | P4, P5 |
| 12:30 | `make backend-up backend-migrate seed-demo run` works; health ready | P1 |
| 1:15 | `seed-irvine` imports Person 2's first real batch | everyone |
| 1:45 | README "Try it" tested on a fresh clone | team |

Rules for teammates: register routers in `api/app.py` with one line each; add Make targets by
asking Person 3; never edit `0001_initial.py`.

## 10. Deferred and deviations from SPEC.md

| Item | SPEC | Today |
|---|---|---|
| `data fetch` with allowlist, rate limit, IP checks | §6 | Deferred. No network access in Backend A code |
| `data activate` rollback | §6 | Deferred. Re-publishing requires a new import |
| Concurrent publish test (two connections) | A2 | Deferred. Partial unique index still enforces one active release |
| Separate Compose DB profiles | §10 | Replaced by `dataset_releases.kind` + `CLEARPATH_MODE` filtering in one DB |
| Source hash verification against local file | §6 | `sha256` optional; importer hashes excerpts only |
| Full citation association tables for every relation | §5 | `citation_links` for passages; other references JSONB validated at import |
| Image digest pinning, CI workflow | §4, Task 6 | Deferred; tag `pgvector/pgvector:pg17` |
| Personal-data detection in imports | §6 | Not automated; manifest schema has no free-form personal fields and Person 2 reviews content |
| `GET /api/v1/sources/{id}`, `/jurisdictions` | §9 | Not Backend A today; P4 owns catalog routes, can query these tables |

The README "What is real and what is mocked" table must list these deferrals.
