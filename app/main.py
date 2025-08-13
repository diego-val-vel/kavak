"""
FastAPI application entry point.

Configures application lifespan, logging, health check, and API routes.
Initializes database tables only in development mode; production relies on migrations.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.endpoints import router as v1_router
from app.core.config import settings
from app.core.dependencies import engine
from app.persistence.database import init_models


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context.

    Configures logging and initializes database tables in development mode.
    No explicit shutdown actions are required as connections are managed elsewhere.
    """
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if settings.environment.lower() == "development":
        await init_models(engine)

    yield


def create_app() -> FastAPI:
    """Creates and configures the FastAPI application instance."""
    app = FastAPI(title="Kavak Challenge API", lifespan=lifespan)

    @app.get("/health")
    def health():
        """Simple health check endpoint."""
        return {"status": "ok"}

    app.include_router(v1_router)
    return app


app = create_app()
