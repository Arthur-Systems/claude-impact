-include .env
export

TEST_DB ?= clearpath_test

.PHONY: backend-up backend-down backend-migrate run test-backend seed-cities seed-demo seed-irvine smoke

backend-up:
	docker compose up -d --wait db

backend-down:
	docker compose down

backend-migrate:
	cd backend && CLEARPATH_API_KEY="$${CLEARPATH_API_KEY:-}" uv run alembic upgrade head

run:
	cd backend && uv run uvicorn --factory clearpath.api.app:create_app --host 127.0.0.1 --port 8000

# Person 5's project-timeline tests drop and rebuild the public schema, so they get
# their own disposable database, $(TEST_DB)_p5 (TEST_DB is capped at 60 characters
# so that name stays within PostgreSQL's 63-character limit).
test-backend:
	@uv run --project backend python -c 'import re, sys; name = sys.argv[1]; sys.exit(0 if re.fullmatch(r"clearpath_test[a-z0-9_]{0,46}", name) else "TEST_DB must start with clearpath_test, contain only lowercase letters, digits or underscores, and be at most 60 characters")' "$(TEST_DB)"
	docker compose exec -T db psql -U clearpath -tc "SELECT 1 FROM pg_database WHERE datname='$(TEST_DB)'" | grep -q 1 || docker compose exec -T db createdb -U clearpath $(TEST_DB)
	docker compose exec -T db psql -U clearpath -tc "SELECT 1 FROM pg_database WHERE datname='$(TEST_DB)_p5'" | grep -q 1 || docker compose exec -T db createdb -U clearpath $(TEST_DB)_p5
	cd backend && DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/$(TEST_DB) CLEARPATH_API_KEY=test-key uv run alembic upgrade head
	cd backend && DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/$(TEST_DB) CLEARPATH_API_KEY=test-key CLEARPATH_P5_TEST_DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/$(TEST_DB)_p5 uv run pytest -q

smoke:
	bash backend/scripts/smoke.sh

seed-cities:
	@cd backend && uv run clearpath data import-cities

# Keep the CLI's command forms; parse only its dedicated release_id line and
# fail immediately if either import, parsing or publication fails.
define seed-dataset
	@set -eu; \
	output=$$(cd backend && CLEARPATH_MODE=$(1) uv run clearpath data import --manifest $(2)); \
	printf '%s\n' "$$output"; \
	release_id=$$(printf '%s\n' "$$output" | uv run --project backend python -c 'import sys; from uuid import UUID; ids=[line.removeprefix("release_id=") for line in sys.stdin.read().splitlines() if line.startswith("release_id=")]; assert len(ids)==1, "Expected one release_id from import"; UUID(ids[0]); print(ids[0])'); \
	cd backend && CLEARPATH_MODE=$(1) uv run clearpath data publish --release "$$release_id" --reviewed
endef

seed-demo: seed-cities
	$(call seed-dataset,synthetic,tests/fixtures/irvine_adu_synthetic/manifest.json)

seed-irvine: seed-cities
	@printf '%s\n' 'seed-irvine: publication requires every cited passage to be reviewed; check curated evidence before publishing.'
	$(call seed-dataset,public,data/irvine_adu/manifest.json)
