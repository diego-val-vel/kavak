# Debate Chat API
Tech challenge for Kavak. Chatbot API capable of holding persuasive debates, built with FastAPI, Redis, PostgreSQL, and OpenAI, following best practices, clean architecture, and automated testing.

## Overview
This API exposes a persuasive debate chatbot built with **FastAPI**, **PostgreSQL**, **Redis**, and **OpenAI**. The service persists the full conversation history in PostgreSQL, maintains a short **sliding window** of recent messages in Redis for prompt coherence, and serves a single chat endpoint under a versioned path.

- Long-term storage: PostgreSQL (complete history).  
- Short-term context: Redis (last five messages total).  
- Transport: REST over HTTP with JSON bodies.  
- Documentation: Swagger UI and ReDoc enabled by FastAPI.

## Environment Variables
The following variables must be set for the service to run:

- `APP_NAME` – Name of the application.
- `ENVIRONMENT` – Environment (`development`, `test`, `production`).
- `DEBUG` – Boolean to enable or disable debug logging.
- `POSTGRES_USER` – PostgreSQL username.
- `POSTGRES_PASSWORD` – PostgreSQL password.
- `POSTGRES_DB` – PostgreSQL database name.
- `DATABASE_URL` – Full async database connection string.
- `REDIS_URL` – Redis connection URL.
- `OPENAI_API_KEY` – API key for OpenAI.
- `OPENAI_MODEL` – Model ID for OpenAI requests.
- `OPENAI_TIMEOUT_SECONDS` – Timeout (seconds) for OpenAI API calls.

## Branching Policy
This repository uses a **single branch**: `main`.  
All work is committed directly to `main` to simplify the review process for this challenge.

## Make Commands
Use the following `make` targets:

- `make install`: Build the API image, pull infrastructure images (PostgreSQL, Redis), and start them in detached mode.  
- `make run`: Start the full stack (API + infrastructure) in development mode with hot reload.  
- `make down`: Stop all containers.  
- `make clean`: Stop and remove containers including orphaned volumes.  
- `make test`: Run the test suite inside a one-off API container.

## Swagger / ReDoc and Endpoints
With `make run`:

- **Swagger UI**: http://localhost:8000/docs  
- **ReDoc**: http://localhost:8000/redoc  
- **Healthcheck**: http://localhost:8000/health  
- **Chat**: `POST http://localhost:8000/v1/chat`

## Chat Usage

### 1) Initial message (new conversation)
`
curl --location 'http://localhost:8000/v1/chat' \
--header 'Content-Type: application/json' \
--data '{
    "conversation_id": null,
    "message": "Topic: The Earth is flat; Stance: for. Opening argument: satellite and airline routes can be explained without assuming curvature, and horizon observations appear flat to the naked eye."
}'
`

#### Topic, Stance, and Opening argument
- **Topic**: The subject to debate. If not provided, the service treats the entire first message as the topic.  
- **Stance**: The position to defend (e.g., `for` or `against`). If not provided, the assistant is instructed to adopt a clear, defensible position inferred from the first instruction.  
- **Opening argument**: Optional booster for the stance. If present, it guides the assistant’s initial reasoning; if absent, the assistant still replies using the topic/stance information available.

**Context model**:  
- The service always persists both roles’ messages (user and bot) in PostgreSQL.  
- Redis holds a **sliding window of the last five messages total** (not five pairs). These five messages are the exact context provided to the LLM on each turn.

### 2) Follow-up messages (existing conversation)
`
curl --location 'http://localhost:8000/v1/chat' \
--header 'Content-Type: application/json' \
--data '{
    "conversation_id": "44df9cd1197a45b38a9c650f79cccccd",
    "message": "If the Earth is really flat, how do you explain photographs from space clearly showing a round planet?"
}'
`

Use the `conversation_id` returned in the initial response to continue the same conversation with preserved context.

## Responses
The endpoint returns JSON in the following shape:

`
{
  "conversation_id": "<string>",
  "message": [
    { "role": "user", "message": "<string>" },
    { "role": "bot",  "message": "<string>" }
    // ... only the last five messages total, oldest to newest
  ]
}
`

- `conversation_id`: Unique conversation identifier. Generated on the first turn; must be reused in subsequent turns.  
- `message`: Chronological sliding window used for context. This mirrors the exact five-message context associated with the conversation.

## Validation Rules
- Field `message` is **required**. If missing, the API responds with **422 Unprocessable Entity**.  
- Field `conversation_id` is **optional** on the first turn (`null`). If provided, the service will continue the existing conversation.  
- If the `conversation_id` has no recent Redis window, the service rehydrates the window from PostgreSQL when possible.

## Technologies
**Web Layer**  
- `fastapi` 0.111.0 — API framework.
- `uvicorn[standard]` 0.30.1 — ASGI server.  
- `pydantic-settings` 2.3.1 — Configuration via environment variables.  
- `asgi-lifespan` 2.1.0 — Explicit lifespan management.

**Database**  
- `SQLAlchemy` 2.0.31 — ORM / async engine.  
- `asyncpg` 0.29.0 — PostgreSQL async driver.  
- `aiosqlite` 0.20.0 — Auxiliary SQLite driver for non-production scenarios.

**Redis**  
- `redis[asyncio]` 5.0.8 — Async Redis client for sliding window and caches.  
- `fakeredis` 2.23.2 — Testing double for Redis (when applicable).

**HTTP Client (runtime)**  
- `httpx` 0.27.0 — Async HTTP client (internal usage when needed).

**OpenAI SDK**  
- `openai` 1.35.10 — LLM client SDK.

**Testing**  
- `pytest` 8.3.2 — Test runner.  
- `pytest-asyncio` 0.23.7 — Async test support.

## Docker Compose Services
Services are defined in **/kavak/docker-compose.yml**:

- **api**: FastAPI served by Uvicorn with `--reload`. Depends on PostgreSQL and Redis. Exposes port `8000`.  
- **postgres**: PostgreSQL 15 with named volume `postgres_data`. Exposes port `5432`.  
- **redis**: Redis 7 with named volume `redis_data`. Exposes port `6379`.

## Notes
- Only the **last five messages total** are used in the prompt context at any time (challenge requirement).  
- Full persistence in PostgreSQL ensures the conversation can be rehydrated and continued later.  
- Swagger and ReDoc are available for quick exploration during development.
