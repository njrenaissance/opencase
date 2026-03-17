#!/bin/bash
# Build the backend Docker image and run basic smoke tests.
#
# Usage (run from repo root):
#   ./scripts/build-backend.sh           # build + smoke test
#   ./scripts/build-backend.sh --no-run  # build only
#
# Reads credentials from .env at the repo root (same file used by docker-compose).
# The image is tagged opencase-api:dev for local development use.
# CI will tag and push with a version once GH Actions are configured.

set -euo pipefail

IMAGE="opencase-api:dev"
CONTEXT="backend"
DOCKERFILE="backend/docker/Dockerfile"
CONTAINER="opencase-api-smoke"
PORT=18000

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

ENV_FILE=".env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: $ENV_FILE not found — copy .env.example to .env and fill in required values"
    exit 1
fi

echo "==> Building $IMAGE"
docker build -f "$DOCKERFILE" -t "$IMAGE" "$CONTEXT"
echo "==> Build complete"

if [[ "${1:-}" == "--no-run" ]]; then
    exit 0
fi

echo "==> Running smoke tests"

# Verify the image exists
docker image inspect "$IMAGE" > /dev/null

# Verify non-root user
USER_OUT=$(docker run --rm \
    --env-file "$ENV_FILE" \
    -e SKIP_MIGRATIONS=true \
    "$IMAGE" whoami)
if [[ "$USER_OUT" != "opencase" ]]; then
    echo "FAIL: expected 'opencase' user, got '$USER_OUT'"
    exit 1
fi
echo "  [ok] runs as non-root user: $USER_OUT"

# Verify /health endpoint responds
docker rm -f "$CONTAINER" 2>/dev/null || true
docker run -d \
    --name "$CONTAINER" \
    -p "${PORT}:8000" \
    --env-file "$ENV_FILE" \
    -e SKIP_MIGRATIONS=true \
    "$IMAGE"

HEALTH=""
for i in $(seq 1 30); do
    HEALTH=$(curl -sf "http://localhost:${PORT}/health" 2>/dev/null || true)
    if [[ -n "$HEALTH" ]]; then break; fi
    sleep 1
done

docker rm -f "$CONTAINER" > /dev/null

if [[ -z "$HEALTH" ]]; then
    echo "FAIL: /health did not respond within 30 seconds"
    exit 1
fi

STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''))")
if [[ "$STATUS" != "ok" ]]; then
    echo "FAIL: /health returned unexpected status: $HEALTH"
    exit 1
fi
echo "  [ok] /health returned status=ok"

echo "==> Smoke tests passed"
