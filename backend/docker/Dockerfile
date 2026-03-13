# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency and build files first for layer caching
COPY pyproject.toml uv.lock README.md ./

# Install production dependencies only (no dev deps, no project yet)
RUN uv sync --frozen --no-dev --no-install-project

# Copy application source
COPY app/ app/

# Install the project itself (hatchling build)
RUN uv sync --frozen --no-dev


# ---- Stage 2: Runtime ----
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 opencase \
    && useradd --uid 1000 --gid opencase --shell /bin/bash opencase

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY app/ app/

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user
USER opencase

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
