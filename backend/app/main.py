# Configure logging before any other app imports.
# session.py and other modules emit logger.debug() at import time;
# setup_logging() must run first so those messages respect OPENCASE_LOG_LEVEL.
from app.core.config import settings
from app.core.logging import setup_logging

setup_logging(settings.log_level, settings.log_output)

from fastapi import FastAPI  # noqa: E402

from app.api.auth import router as auth_router  # noqa: E402
from app.api.health import router as health_router  # noqa: E402
from app.core.telemetry import configure_instrumentation, setup_telemetry  # noqa: E402

setup_telemetry(settings)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.include_router(health_router)
app.include_router(auth_router)

configure_instrumentation(app, settings)
