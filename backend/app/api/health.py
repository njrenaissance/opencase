import logging
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# Individual readiness checks
#
# Each check is an async callable returning "ok" or "error".
# To add a new service, define the function and append it to READINESS_CHECKS.
# ---------------------------------------------------------------------------


async def check_postgres(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


async def check_redis() -> str:
    try:
        r = aioredis.from_url(settings.redis.url, socket_timeout=2)  # type: ignore[no-untyped-call]
        try:
            await r.ping()
        finally:
            await r.aclose()
        return "ok"
    except Exception:  # noqa: BLE001
        return "error"


# Registry of zero-argument readiness checks: (service_name, check_callable).
# Postgres is excluded — it requires the injected DB session and is called
# directly in the readiness_check endpoint.
READINESS_CHECKS: list[tuple[str, Callable[[], Awaitable[str]]]] = [
    ("redis", check_redis),
    # ("qdrant", check_qdrant),
    # ("minio", check_minio),
    # ("ollama", check_ollama),
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict[str, Any]:
    checks: dict[str, str] = {}

    # Postgres is special — it receives the injected DB session.
    checks["postgres"] = await check_postgres(db)

    # Run all registered service checks.
    for name, check_fn in READINESS_CHECKS:
        checks[name] = await check_fn()

    all_ok = all(v == "ok" for v in checks.values())
    status = "ok" if all_ok else "degraded"
    logger.debug("Readiness check: status=%s services=%s", status, checks)
    return {"status": status, "services": checks}
