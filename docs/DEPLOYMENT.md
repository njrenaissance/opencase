# Gideon Deployment Guide

## Overview

Gideon backend services (FastAPI, Celery Worker, Celery Beat, Flower) are now
deployed as pre-built container images from GitHub Container Registry (GHCR).
This replaces the previous local build approach, ensuring consistent, versioned
artifacts across environments.

---

## Building the Backend Image

### Triggering the Build

The GitHub Actions workflow `build-container.yml` builds and pushes the backend
image to GHCR on-demand.

1. Go to **GitHub → Actions → Build Container**
2. Click **Run workflow**
3. Optionally specify a branch/tag/SHA (defaults to `main`)
4. The workflow will:
   - Build the backend image with all extras (including Flower monitoring)
   - Tag with `latest` (if on `main`), commit SHA, and branch/PR refs
   - Push all tags to `ghcr.io/njrenaissance/gideon/backend`

The image is pushed immediately after successful build — no separate release
step.

---

## Production Deployment

### Prerequisites

- Docker Compose 2.0+
- `.env` file (copy from `.env.example` and fill in secrets)

### Pulling Pre-Built Images

Use the main compose file, which references the GHCR image by default:

```bash
cd infrastructure
docker compose -f docker-compose.yml --env-file ../.env up -d
```

All five backend services will pull
`ghcr.io/njrenaissance/gideon/backend:latest`:

- `db-migrate` — runs Alembic migrations once, then exits
- `fastapi` — FastAPI API server (port 8000)
- `celery-worker` — background task processor
- `celery-beat` — scheduled task submitter (cron)
- `flower` — Celery monitoring UI (port 5555)

**Authentication for private registries**: If the image is private, configure
Docker credentials:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <username> --password-stdin
```

Docker Compose respects daemon credentials for `image:` pulls once you've
logged in via `docker login`. Ensure the token has `read:packages` scope.

For advanced credential management (e.g., in CI/CD), consider:

- Docker 25.0+: Use `--registry-auth` flag with embedded credentials in compose
- Earlier versions: Set credentials in `.env` or use `DOCKER_CONFIG` env var

---

## Local Development

### Building Locally

To build the backend image locally instead of pulling from GHCR:

```bash
cd infrastructure
docker compose -f docker-compose.yml \
  -f docker-compose.local-build.yml \
  --env-file ../.env up -d
```

The `local-build` override restores the `build:` directives, so Docker Compose
will:

1. Build the image from `backend/docker/Dockerfile`
2. Include the `monitoring` extra for Flower
3. Use the same compose network and services as production

This is useful for:

- Testing local code changes before pushing
- Development without Docker Hub/GHCR access
- Rapid iteration on the Dockerfile itself

### Rebuilding After Code Changes

```bash
docker compose -f docker-compose.yml \
  -f docker-compose.local-build.yml build
docker compose -f docker-compose.yml \
  -f docker-compose.local-build.yml up -d
```

---

## Integration Tests

Integration tests use the `docker-compose.integration.yml` override, which:

1. **Uses ephemeral test volumes** for postgres, qdrant, and minio — data is
   wiped between test runs for a clean slate. The `ollama-models-test` volume
   is persistent (external) so LLM models are cached across test runs
2. **Enables OTEL tracing** with the OTLP exporter to Grafana (otel-lgtm)
3. **Disables Flower** (not needed for tests)

The integration compose is applied automatically by `pytest-docker` via
`conftest.py` — developers do not invoke it directly.

### Running Integration Tests

```bash
cd backend
pytest -m integration
```

This will:

1. Create/start all services (ephemeral test volumes for postgres, qdrant, minio)
2. Run tests against `gideon_test` and `gideon_tasks_test` databases
3. Tear down services with `docker compose down -v` (removes ephemeral test
   volumes; ollama-models-test is preserved)

---

## Image Tagging Strategy

Each build produces multiple tags:

| Tag | Used for |
| --- | --- |
| `latest` | Most recent build on `main` (production default) |
| `<commit-sha>` | Specific commit — useful for rollback |
| `<branch-name>` | Latest on a branch (e.g., `main`, `feature/xxx`) |
| `<pr-number>` | Preview builds for pull requests |

Example tags for a commit on `main`:

```text
ghcr.io/njrenaissance/gideon/backend:latest
ghcr.io/njrenaissance/gideon/backend:abc1234def5678
ghcr.io/njrenaissance/gideon/backend:main
```

### Pinning a Specific Image Version

All backend services use `${IMAGE_TAG:-latest}`, which allows overriding via
an environment variable. To pin to a specific commit or tag:

```bash
# Pin to a specific commit SHA for rollback
export IMAGE_TAG=abc1234def5678
docker compose -f docker-compose.yml up -d

# Or set in .env file:
echo "IMAGE_TAG=abc1234def5678" >> .env
docker compose -f docker-compose.yml up -d
```

This is safer than editing compose files and allows quick rollback by
changing one env variable.

---

## Configuration

### Environment Variables

Default values are in `.env.example`. Key variables:

| Variable | Description |
| --- | --- |
| `GIDEON_OTEL_ENABLED` | Enable OpenTelemetry (true/false) |
| `GIDEON_OTEL_EXPORTER` | Exporter type (console/otlp) |
| `GIDEON_OTEL_ENDPOINT` | OTLP collector endpoint |
| `GIDEON_CHUNKING_CHUNK_SIZE` | Document chunk size for RAG |
| `GIDEON_CHUNKING_CHUNK_OVERLAP` | Overlap between chunks |
| `DEPLOYMENT_MODE` | airgapped or internet |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database credentials |
| `GIDEON_ADMIN_EMAIL`, `GIDEON_ADMIN_PASSWORD` | Initial admin user |

Copy `.env.example` to `.env` and fill in secrets:

```bash
cp .env.example .env
# Edit .env and set required values
```

---

## Troubleshooting

### Image Pull Fails (403 Forbidden)

The image is private. Authenticate:

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u <username> --password-stdin
```

Or use a Personal Access Token (PAT) with `read:packages` scope.

### Migrations Fail

`db-migrate` runs migrations on startup. Check logs:

```bash
docker compose logs db-migrate
```

Common issues:

- Database is not healthy — check `postgres` logs
- Schema version mismatch — ensure you're using the right image version

### OTEL Traces Not Appearing in Grafana

1. Verify `GIDEON_OTEL_ENABLED=true` and `GIDEON_OTEL_EXPORTER=otlp`
2. Check that `grafana` service is healthy: `docker compose ps grafana`
3. Visit Grafana at `http://localhost:3001` (admin/admin by default)
4. Check **Explore → Traces** for incoming spans

---

## Security Notes

1. **Do not commit `.env`** — use `.env.example` as a template
2. **Image pull credentials** — store `$GITHUB_TOKEN` in CI secrets, not in
   `.env`
3. **No third-party LLM API calls** — Ollama runs locally; no external
   inference
4. **Self-hosted only** — Gideon is designed for on-premise deployment; do not
   expose to the public internet without additional hardening (VPN, mTLS,
   etc.)
