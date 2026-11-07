# A seed-demo goal selects the synthetic environment for every goal in this invocation.
ifneq ($(filter demo seed-demo,$(MAKECMDGOALS)),)
BACKEND_ENV ?= demo
else
BACKEND_ENV ?= public
endif

ifneq ($(filter seed-demo,$(MAKECMDGOALS)),)
ifneq ($(BACKEND_ENV),demo)
$(error seed-demo requires BACKEND_ENV=demo)
endif
endif
PYTHON_IMAGE := python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c

ifeq ($(BACKEND_ENV),demo)
DATA_MODE := synthetic
else ifeq ($(BACKEND_ENV),public)
DATA_MODE := public
else
$(error BACKEND_ENV must be public or demo)
endif

ENV_FILE := .runtime/$(BACKEND_ENV).env
# Remove ambient interpolation values so the selected private env file owns all
# credentials, database routing and ports (including both Settings URL spellings).
COMPOSE = env -u DATABASE_URL -u CLEARPATH_DATABASE_URL -u CLEARPATH_API_KEY \
  -u POSTGRES_USER -u POSTGRES_PASSWORD -u POSTGRES_DB \
  -u BACKEND_API_PORT -u BACKEND_DB_PORT CLEARPATH_DATA_MODE=$(DATA_MODE) \
  docker compose --env-file $(ENV_FILE) -p clearpath-$(BACKEND_ENV)

.PHONY: backend-env backend-up backend-migrate backend-down backend-logs demo test-backend
.NOTPARALLEL:

# Docker/Compose is enough for local startup; Python runs inside the pinned image.
backend-env:
	@mkdir -p .runtime
	@docker run --rm --user "$$(id -u):$$(id -g)" \
	  -v "$(CURDIR)/backend/scripts:/scripts:ro" -v "$(CURDIR)/.runtime:/runtime" \
	  $(PYTHON_IMAGE) python /scripts/local_env.py /runtime/$(BACKEND_ENV).env --mode $(DATA_MODE)

backend-up: backend-env
	@$(COMPOSE) up --build --detach --wait

backend-migrate: backend-env
	@$(COMPOSE) up --detach --wait db
	@$(COMPOSE) run --build --rm --no-deps api alembic -c alembic.ini upgrade head

backend-down: backend-env
	@$(COMPOSE) down

backend-logs: backend-env
	@$(COMPOSE) logs --tail=100 api

# Task 1 intentionally starts an empty synthetic environment. Ingestion adds seeding.
demo:
	@$(MAKE) BACKEND_ENV=demo backend-up backend-migrate

test-backend:
	@uv run --project backend pytest backend/tests
