# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency and build files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies only (no dev deps, no project yet)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source, migration scripts, and utility scripts
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini
COPY scripts/ scripts/

# Install the project itself (hatchling build)
RUN uv sync --frozen --no-dev


# ---- Stage 2: Runtime ----
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 opencase \
    && useradd --uid 1000 --gid opencase --shell /bin/bash opencase

# Copy virtual environment and application from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/scripts /app/scripts

# Copy startup script
COPY docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER opencase

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
