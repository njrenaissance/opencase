#!/bin/sh
# Run database migrations then start the API server (default) or a custom
# command supplied via docker-compose `command:`.
#
# Set SKIP_MIGRATIONS=true to skip migrations (e.g. when running the image
# in isolation for smoke tests without a live database).
#
# Bind address and port are read from environment variables:
#   OPENCASE_API_HOST  (default: 0.0.0.0)
#   OPENCASE_API_PORT  (default: 8000)
set -e

if [ "${SKIP_MIGRATIONS:-false}" != "true" ]; then
    alembic upgrade head
fi

# If compose supplies a command, run that instead of the default Uvicorn.
if [ $# -gt 0 ]; then
    exec "$@"
fi

exec uvicorn app.main:app \
    --host "${OPENCASE_API_HOST:-0.0.0.0}" \
    --port "${OPENCASE_API_PORT:-8000}"
