"""
Pytest fixtures and configuration for the test suite.

Sets up a per-test application environment with isolated database and Redis instances,
overrides dependencies, and avoids external network calls.
"""

from __future__ import annotations

import os
import warnings

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from redis.asyncio import from_url as redis_from_url

# Suppress selected warnings to keep the test output clean
warnings.filterwarnings(
    "ignore",
    category=PendingDeprecationWarning,
    message="Please use `import python_multipart` instead.",
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*on_event.*deprecated.*",
)

# Configure environment variables for test execution
os.environ["ENVIRONMENT"] = "test"
os.environ["DEBUG"] = "false"
os.environ["APP_NAME"] = "Kavak Challenge API (tests)"
os.environ["DATABASE_URL"] = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@postgres:5432/kavak_db",
)
os.environ["REDIS_URL"] = os.environ.get("REDIS_URL", "redis://redis:6379/0")
os.environ["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "test-no-network")
os.environ["OPENAI_MODEL"] = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
os.environ["OPENAI_TIMEOUT_SECONDS"] = os.environ.get("OPENAI_TIMEOUT_SECONDS", "5")

# Import the application after environment variables are set
from app.main import create_app
from app.core.dependencies import get_db, get_redis
from app.persistence.database import init_models
from app.core import config as config_mod

# Ensure the Settings object reflects the test environment
config_mod.settings.environment = "test"


@pytest_asyncio.fixture(scope="function")
async def test_client():
    """
    Provides an AsyncClient bound to the ASGI app for test execution.
    Each test runs with a dedicated database session and Redis client to avoid cross-test state.
    External network calls to OpenAI are mocked.
    """
    # Per-test database engine and session
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, future=True, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Database schema initialization
    await init_models(engine)

    # Per-test Redis client
    redis_url = os.environ["REDIS_URL"]
    redis_client = redis_from_url(redis_url, decode_responses=True)

    # Application instance and dependency overrides
    app = create_app()

    async def _override_get_db():
        async with SessionLocal() as session:
            yield session

    async def _override_get_redis():
        yield redis_client

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    # OpenAI client mock to avoid external requests
    from app.services import openai_client as openai_mod

    async def _fake_chat(
        self, *, system_prompt: str, user_prompt: str, temperature: float, max_tokens: int
    ) -> str:
        return "TEST_BOT_REPLY"

    mp = MonkeyPatch()
    mp.setattr(openai_mod.OpenAIClient, "chat", _fake_chat, raising=True)

    # Application lifespan and HTTP client for tests
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            try:
                yield client
            finally:
                # Resource cleanup after each test
                mp.undo()
                try:
                    await redis_client.aclose()
                except Exception:
                    try:
                        await redis_client.close()
                    except Exception:
                        pass
                try:
                    await engine.dispose()
                except Exception:
                    pass
