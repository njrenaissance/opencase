"""Async SQLAlchemy engine and session factory.

Engine is created once at startup from settings.db. All async routes receive
an AsyncSession via the get_db dependency.
"""

import logging
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

_parsed = urlparse(settings.db.url)
logger.debug(
    "DB engine initialised: host=%s port=%s pool_size=%d max_overflow=%d pre_ping=%s",
    _parsed.hostname,
    _parsed.port,
    settings.db.pool_size,
    settings.db.max_overflow,
    settings.db.pool_pre_ping,
)

engine = create_async_engine(
    settings.db.url,
    pool_size=settings.db.pool_size,
    max_overflow=settings.db.max_overflow,
    pool_pre_ping=settings.db.pool_pre_ping,
    echo=settings.db.echo,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    logger.debug("DB session opened")
    async with AsyncSessionLocal() as session:
        yield session
    logger.debug("DB session closed")
