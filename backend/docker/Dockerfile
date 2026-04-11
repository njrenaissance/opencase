# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

WORKDIR /app

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace root files for uv workspace resolution
COPY pyproject.toml uv.lock ./

# Copy shared package (workspace dependency)
COPY shared/ shared/

# Copy backend dependency files first for layer caching
COPY backend/pyproject.toml backend/README.md backend/

# Install production dependencies with shared built as a wheel (not editable)
WORKDIR /app/backend
RUN uv sync --frozen --no-dev --no-editable --no-install-project

# Copy remaining backend source
COPY backend/app/ app/
COPY backend/alembic/ alembic/
COPY backend/alembic.ini alembic.ini
COPY backend/scripts/ scripts/

# Install the backend project itself.
# INSTALL_EXTRAS is empty by default; set to "monitoring" for the Flower container.
ARG INSTALL_EXTRAS=""
RUN if [ -n "$INSTALL_EXTRAS" ]; then \
      uv sync --frozen --no-dev --no-editable --extra "$INSTALL_EXTRAS"; \
    else \
      uv sync --frozen --no-dev --no-editable; \
    fi


# ---- Stage 2: Runtime ----
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 gideon \
    && useradd --uid 1000 --gid gideon --shell /bin/bash gideon

# Copy virtual environment (shared is installed as a wheel, no source needed)
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend/app /app/app
COPY --from=builder /app/backend/alembic /app/alembic
COPY --from=builder /app/backend/alembic.ini /app/alembic.ini
COPY --from=builder /app/backend/scripts /app/scripts

# Copy startup script
COPY backend/docker/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Copy editable system prompt (overridable via GIDEON_CHATBOT_SYSTEM_PROMPT_FILE)
COPY backend/SYSTEM_PROMPT.md /app/SYSTEM_PROMPT.md

# Put venv on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create celery schedule directory (used by celery-beat --schedule flag)
RUN mkdir -p /tmp/celery && chown gideon:gideon /tmp/celery

# Switch to non-root user
USER gideon

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
