-include .env
export

.PHONY: backend-up backend-down backend-migrate run test-backend

backend-up:
	docker compose up -d --wait db

backend-down:
	docker compose down

backend-migrate:
	cd backend && uv run alembic upgrade head

run:
	cd backend && uv run uvicorn --factory clearpath.api.app:create_app --host 127.0.0.1 --port 8000

test-backend:
	docker compose exec -T db psql -U clearpath -tc "SELECT 1 FROM pg_database WHERE datname='clearpath_test'" | grep -q 1 || docker compose exec -T db createdb -U clearpath clearpath_test
	cd backend && DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test CLEARPATH_API_KEY=test-key uv run pytest -q

# seed-cities: added with ingestion commands in Task 2.
# seed-demo: added with ingestion commands in Task 2.
# seed-irvine: added with ingestion commands in Task 2.
