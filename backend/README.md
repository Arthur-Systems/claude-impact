# ClearPath backend

Backend A provides a FastAPI service, PostgreSQL schema, curated dataset importer,
and publication gate. This is a local prototype, not legal, financial, or lending
advice. It does not file applications or contact a city or person.

## Start here

Install Docker with Compose and [uv](https://docs.astral.sh/uv/). Start Docker.
`uv run` installs the locked Python 3.12 environment and project dependencies.
Run the following from the repository root:

```sh
cp .env.example .env
# Edit .env: choose a local CLEARPATH_API_KEY and keep CLEARPATH_MODE=synthetic.
# Do not commit .env or put the key in a shared command transcript.
export COMPOSE_PROJECT_NAME=claude-impact
make backend-up
make backend-migrate
make seed-demo
make run
```

The API listens on `http://127.0.0.1:8000`. Open `/docs` for the routes registered in
this checkout. `GET /health/live` and `GET /health/ready` need no API key. After
`seed-demo`, synthetic-mode readiness should report `dataset_available: true`.
`/api/v1/_ping` requires the `X-API-Key` header. It and `POST /api/v1/_echo` are
foundation probes, not permit lookup or project endpoints.

## Commands

| Command, from the repository root | Effect |
|---|---|
| `make backend-up` | Start the PostgreSQL 17 + pgvector Compose service and wait for its healthcheck. |
| `make backend-migrate` | Apply Alembic migrations to `DATABASE_URL`. Migration setup requires `CLEARPATH_API_KEY`. |
| `make seed-cities` | Upsert the city registry without treating registry presence as rule coverage. |
| `make seed-demo` | Import and publish the synthetic fixture. Repeats reuse the release and record a no-op import. |
| `make seed-irvine` | Validate and import the curated Irvine bundle, then attempt public publication. Publication requires every cited passage to be reviewed. Validation or review failures stop the command. |
| `make run` | Start Uvicorn on `127.0.0.1:8000`, reading the root `.env`. Stop with Ctrl-C. |
| `make test-backend` | Create `clearpath_test` if missing, migrate it, and run pytest on PostgreSQL. |
| `make test-backend TEST_DB=clearpath_test_myname` | Use a separate test database for a teammate or worktree. Names must start with `clearpath_test`. |
| `make smoke` | Start/check the DB, migrate the dev DB, seed-demo, run synthetic-mode HTTP checks on `127.0.0.1:8765`, and stop the temporary API on exit. |

The smoke check creates a throwaway API key, checks live/ready and authenticated
and unauthenticated ping responses, and leaves the database running. It refuses an
occupied API port rather than stopping another process. If needed, select a free
loopback port with `make smoke SMOKE_PORT=18765` (the default remains 8765).
Seeding is repeatable;
smoke does not drop a database or run Compose teardown.

For operator commands, change to `backend`:

```sh
uv run clearpath data import-cities
uv run clearpath data import --manifest tests/fixtures/irvine_adu_synthetic/manifest.json --dry-run
uv run clearpath data import --manifest tests/fixtures/irvine_adu_synthetic/manifest.json
# Copy the release_id line from import, then choose the matching mode:
CLEARPATH_MODE=synthetic uv run clearpath data publish --release <release-uuid> --reviewed
```

Data commands do not require the HTTP API key. Dry-run performs file validation
without opening a database connection. Manifest paths resolve against the caller's
working directory and must stay under `backend/data/` or `backend/tests/fixtures/`,
including after symlink resolution. Errors use stable `code: path` lines and exit 1.
`uv run clearpath --debug data ...` exposes the underlying exception for local
troubleshooting. Do not share debug output that could include private input.

## Environment variables

Keep local values in the ignored root `.env`, or export them. Make command-line
assignments, such as `make CLEARPATH_MODE=public run`, override `.env` values.

| Variable | Default and meaning |
|---|---|
| `DATABASE_URL` | Local dev PostgreSQL URL from `.env.example`; must start with `postgresql+psycopg://`. Hidden from Settings repr and validation messages. |
| `CLEARPATH_API_KEY` | Required for HTTP startup and migration setup. No default. All `/api/v1` routers must require `X-API-Key`. |
| `CLEARPATH_MODE` | `public` unless configured. `synthetic` serves synthetic releases; `public` selects reviewed-public releases. The example `.env` selects synthetic mode. |
| `CLEARPATH_CORS_ORIGINS` | Empty by default, so CORS is off. Comma-separated allowlist, for example `http://localhost:5173`. |
| `TEST_DB` | Make's test database name; default `clearpath_test`. It drives database creation, migrations, and pytest. Tests refuse database names without the `clearpath_test` prefix. |
| `COMPOSE_PROJECT_NAME` | Set to `claude-impact` for the shared local Compose service, especially from worktrees. |
| `SMOKE_PORT` | Smoke-only API port, default `8765`. Override it if another local service owns that port. |

The application engine hides SQL bind parameters and uses a two-second connection
timeout. Readiness returns 503 when the database or Alembic head is unavailable;
a healthy database without a matching active dataset returns 200 with
`dataset_available: false`. Readiness does not certify legal or source accuracy.

## Public interfaces for teammates

- `clearpath.api.app.create_app(settings: Settings | None = None)` creates the app.
- `clearpath.db.session.get_session` is the FastAPI session dependency. Direct
  callers may pass Settings. `SessionLocal(settings)` opens a caller-owned session.
- `clearpath.domain.errors.DomainError(code, message, details=None, http_status=400)`
  becomes the shared HTTP envelope. Messages and details must be safe to return.
- `clearpath.domain.schemas.StrictModel` forbids unknown fields. Every request
  schema should inherit it.
- Shared enums are `ProjectType`, `ReleaseKind`, `ReleaseStatus`, and
  `AffordabilityGoal` in `clearpath.domain.schemas`.
- Dataset interfaces are `clearpath.ingestion.validation.validate_bundle` and
  `import_bundle`, `import_cities`, and `publish_release` in
  `clearpath.ingestion.service`. Services receive a Session and do
  not commit. `publish_release` requires a reviewed draft and locks its
  jurisdiction until the caller finishes the transaction. The CLI maps a
  publication unique violation to `publish_conflict` after rollback.
- `clearpath.permits.predicates` is owned by Person 4. Coordinate predicate
  grammar, validation, fact typing, and evaluation changes with that owner.

ORM models in `clearpath.db.models`:

| Reference and dataset models | Project models |
|---|---|
| `Jurisdiction`, `DatasetRelease`, `SourceSnapshot`, `SourcePassage` | `Project`, `ProjectRequirement` |
| `Pathway`, `Requirement`, `MilestoneTemplate`, `CitationLink`, `IngestionRun` | `ProjectMilestone`, `ProjectEvent` |

### Transaction and extension rules

1. Routes and CLI commands own transactions and call `commit()`. Services never
   commit. On failure, callers roll back and close their session.
2. Add route modules in `src/clearpath/api/routes/`. Register routers inside
   `create_app` in `api/app.py`; include them under the protected `/api/v1` router
   or explicitly attach `Depends(require_api_key)` to every `/api/v1` router.
3. Use new migrations for schema changes. Do not edit `0001_initial.py` after
   teammates have applied it.
4. Replace JSONB dicts and lists rather than mutating them in place. These mapped
   columns do not use SQLAlchemy's mutable change-tracking extension. For example,
   assign `project.rule_facts = {**project.rule_facts, "existing_dwelling": True}`.
5. Imported release content is immutable. Import a changed manifest as a new
   release; publication changes only release status and publication time. Existing
   project pins stay attached to their original release.
6. Keep real applicant, tenant, buyer, and resident information out of fixtures,
   manifests, logs, and git. Unknown facts remain unknown. No automatic personal
   data detector is implemented.

## What this slice does not provide

The schema includes project and timeline tables, but Backend A does not implement
portfolio, project activation, checklist, timeline, location-resolution, permit
lookup, or source/catalog HTTP routes. Those are separate teammate workstreams.
No Claude API key is needed for this foundation.

Network dataset fetching, rollback activation, source-file hash verification,
vector search, uploads/OCR, and chat are not built. Source hashes are optional
metadata; excerpt hashes are computed at import. One database holds both release
kinds instead of separate Compose DB profiles. Citation links are relational,
but other validated references remain JSONB. The Compose image uses a tag rather
than an immutable digest, and no backend CI workflow is included. See the root
README's status table for the complete Backend A design deferrals.
