from fastapi import FastAPI

from app.api.health import router as health_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.telemetry import configure_instrumentation, setup_telemetry

setup_logging(settings.log_level, settings.log_output)
setup_telemetry(settings)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
)

app.include_router(health_router)

configure_instrumentation(app, settings)
