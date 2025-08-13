"""
Chat API endpoint definitions.

Provides the /v1/chat route to handle both new and ongoing conversations.
Integrates database persistence, Redis sliding window, and LLM-based responses.
"""

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import ChatRequest, ChatResponse
from app.core.dependencies import get_db, get_redis
from app.services.chat_service import ChatService

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> ChatResponse:
    """
    Processes a chat turn.

    Workflow:
    - Creates a new conversation if conversation_id is null.
    - Persists the complete history in PostgreSQL.
    - Maintains a 5-message sliding window in Redis for prompt context.
    - Calls the LLM and returns the last 5 combined messages (most recent last).
    """
    service = ChatService()
    response = await service.handle_message(payload=payload, db=db, redis=redis)
    return response
