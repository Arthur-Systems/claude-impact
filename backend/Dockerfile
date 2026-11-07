FROM python:3.12.12-slim-trixie@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir uv==0.10.4 \
    && adduser --system --uid 10001 --group clearpath
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
COPY src ./src
RUN uv sync --locked --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
USER clearpath
EXPOSE 8000
CMD ["uvicorn", "clearpath.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
