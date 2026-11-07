# ClearPath backend foundation

This is prototype platform infrastructure. No reviewed city requirements, permit
lookup, project services, timeline services or semantic search are implemented.
The vector extension is installed for future work; the dataset starts empty.

## Run with Docker

From the repository root, Docker Desktop/Engine with Compose and Make is enough:

```sh
make backend-up backend-migrate
```

This uses **public mode**, API `http://127.0.0.1:8000`, database port `55432`,
Compose project `clearpath-public`, and ignored credentials `.runtime/public.env`.
It does not create public regulatory data. Readiness succeeds once the schema is
migrated, with `dataset_available: false` until a matching active release exists.

For an isolated **synthetic** environment:

```sh
make demo
# Equivalent in this foundation:
make BACKEND_ENV=demo backend-up backend-migrate
```

The demo uses API port `8001`, database port `55433`, Compose project
`clearpath-demo`, and its own `.runtime/demo.env` credentials and database volume.
It is intentionally empty in Task 1; ingestion/seeding belongs to the next task.
Including a future `seed-demo` goal in a Make invocation selects this demo
configuration for **all goals**, so `make backend-up backend-migrate seed-demo`
will use the same synthetic database throughout once that target is implemented.
Explicit `BACKEND_ENV=public` with `seed-demo` fails immediately. A separate
`seed-demo` recipe must also depend on demo startup and migrations.

Credentials are generated inside a pinned Python container, with private file
permissions, and reused. They are not printed. Do not commit `.runtime/` or use
`.env.example`'s placeholders as real credentials. Make explicitly sets the
selected data mode so an ambient `CLEARPATH_DATA_MODE` cannot switch it silently.

Public health routes:

```sh
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

Liveness does not connect to the database and succeeds before migrations.
Readiness is `503` before migration or if the database is unreachable, then `200`
with independent `dataset_available` once the schema is ready. Health identifies
`public` or `synthetic` mode. Application routes require `X-API-Key`, including
`GET /api/v1/status` and `GET /api/v1/openapi.json`. The optional status query
`expected_mode=public|synthetic` rejects unknown fields/invalid values (`422`) and
reports an expectation mismatch (`409`). Status returns backend name and mode.

Use `make backend-down` or `make BACKEND_ENV=demo backend-down` to stop the
corresponding environment. Volumes and credentials are retained. Neither command
stops another Compose project.

## Develop and verify

The backend uses Python 3.12.12 and an exact dependency lock at `backend/uv.lock`.
Install [uv](https://docs.astral.sh/uv/) for local development, then run:

```sh
uv sync --project backend --locked
make test-backend
uv run --project backend ruff check backend
uv run --project backend ruff format --check backend
```

The complete test suite starts a uniquely named, disposable PostgreSQL 17 +
pgvector container with temporary storage and random credentials, creates isolated
test databases, and removes only its own resources. Docker must be running.
It never uses SQLite or an existing database. No credentials need to be supplied
for tests. Source fixtures are synthetic technical examples, not city rules.

## Shared interfaces

- `clearpath.api.app.create_app(settings: Settings | None = None) -> FastAPI`.
  App construction reads settings when not supplied, but does not connect to the
  database. Imports alone never require settings or database connectivity.
- `clearpath.core.config.Settings`: required secret `database_url` (only
  `postgresql+psycopg`, host/database required) and `api_key` (at least 32 characters);
  `data_mode` defaults to `public` and permits `public|synthetic`. Environment
  names are prefixed `CLEARPATH_`. No implicit dotenv loading or credential defaults.
- `clearpath.domain.errors.DomainError(code, message, status_code=400)`: use fixed,
  sanitized public code/message strings, never raw exceptions or applicant input.
  All HTTP failures use `{"error":{"code":"...","message":"..."}}`.
- `clearpath.db.session.get_session() -> Iterator[Session]`: lazy default settings
  and cached engine. `create_session_factory(settings)` creates an explicit
  `sessionmaker[Session]`; `dispose_session_factory(factory)` releases its engine.
  A yielded session closes after use and **never auto-commits**. Callers own the
  transaction (`with session.begin(): ...`) and rollback/commit decisions.
- HTTP routers use `clearpath.api.dependencies.get_settings`, `get_session`,
  `require_api_key`, `SessionDependency`, and `SettingsDependency`. These read the
  current app's state, so tests and multiple app instances remain isolated. Include
  future role routers under the protected `/api/v1` router in the app factory.
- Dataset models live in `clearpath.db.models`. All IDs are UUIDs, timestamps use
  timezone-aware PostgreSQL types, and references enforce evidence integrity.
  The task report documents every model field and constraint. JSON/array semantic
  validation, hashing, immutable staging and atomic publication belong to ingestion.
