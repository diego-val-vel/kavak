# Define a minimal FastAPI application to validate container runtime and routing.
# Expose a basic health endpoint and mount versioned routes.

from fastapi import FastAPI
from app.api.v1.endpoints import router as v1_router


def create_app() -> FastAPI:
    app = FastAPI(title="Kavak Challenge API")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(v1_router)
    return app


app = create_app()
