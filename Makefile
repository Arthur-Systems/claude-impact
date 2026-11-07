-include .env
export

.PHONY: backend-up backend-down backend-migrate run test-backend seed-cities seed-demo seed-irvine

backend-up:
	docker compose up -d --wait db

backend-down:
	docker compose down

backend-migrate:
	cd backend && CLEARPATH_API_KEY="$${CLEARPATH_API_KEY:-}" uv run alembic upgrade head

run:
	cd backend && uv run uvicorn --factory clearpath.api.app:create_app --host 127.0.0.1 --port 8000

test-backend:
	docker compose exec -T db psql -U clearpath -tc "SELECT 1 FROM pg_database WHERE datname='clearpath_test'" | grep -q 1 || docker compose exec -T db createdb -U clearpath clearpath_test
	cd backend && DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test CLEARPATH_API_KEY=test-key uv run alembic upgrade head
	cd backend && DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test CLEARPATH_API_KEY=test-key uv run pytest -q

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
	@printf '%s\n' 'seed-irvine: public publication requires reviewed pathways and requirements; the empty stub is rejected with empty_release until content is curated.'
	$(call seed-dataset,public,data/irvine_adu/manifest.json)
