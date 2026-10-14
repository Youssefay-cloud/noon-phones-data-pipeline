FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml .python-version uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY ingest/ingest.py .

ENTRYPOINT ["python", "ingest.py"]
