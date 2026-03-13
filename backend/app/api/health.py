from typing import Any

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready")
async def readiness_check() -> dict[str, Any]:
    checks: dict[str, str] = {}
    # Each dependency check will be added as services come online:
    # - postgres, redis, qdrant, minio, ollama
    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "services": checks,
    }
