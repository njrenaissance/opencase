# Configure logging before any other app imports.
# session.py and other modules emit logger.debug() at import time;
# setup_logging() must run first so those messages respect OPENCASE_LOG_LEVEL.
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level, settings.log_output)

import logging  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402

from app.api.auth import router as auth_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.core.telemetry import configure_instrumentation, setup_telemetry  # noqa: E402

logger = logging.getLogger(__name__)

setup_telemetry(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run one-time startup jobs, then yield to serve requests."""
    # Seed admin user if configured. Idempotent — safe on every boot.
    if settings.admin_email and settings.admin_password:
        from scripts.create_admin import _seed

        try:
            await _seed(
                email=settings.admin_email,
                password=settings.admin_password,
                first_name=settings.admin_first_name,
                last_name=settings.admin_last_name,
                firm_name=settings.admin_firm_name,
            )
        except Exception:
            logger.exception("Admin seed failed — continuing startup")
    elif settings.admin_email and not settings.admin_password:
        logger.error(
            "OPENCASE_ADMIN_EMAIL is set but OPENCASE_ADMIN_PASSWORD is missing "
            "— skipping admin seed"
        )
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(auth_router)

configure_instrumentation(app, settings)
