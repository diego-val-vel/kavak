"""
Provide application-wide dependency providers for database and cache.
Create a single async SQLAlchemy session factory and a Redis client instance.
Expose lightweight FastAPI dependencies to acquire/release resources per request.
"""

from typing import AsyncGenerator
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


# Database: build async engine and session factory once
DATABASE_URL = settings.database_url
engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession tied to the request lifecycle.
    Ensure proper cleanup regardless of success or failure.
    """
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Redis: create a single client instance (lazy) and reuse it
_redis_client: Redis | None = None


def get_redis() -> Redis:
    """
    Return a process-wide Redis client.
    Use decode_responses=True to work with str keys/values by default.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client
