# Define versioned API routes. Expose a minimal /chat endpoint stub.

from fastapi import APIRouter
from app.models.schemas import ChatRequest, ChatResponse, MessageItem

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """
    Accept a chat request and return a placeholder response.
    This stub only echoes structure; business logic will be added later.
    """
    conv_id = payload.conversation_id or "tmp-conv-id"
    history = [
        MessageItem(role="user", message=payload.message),
        MessageItem(role="bot", message="Acknowledged. Business logic pending."),
    ]
    return ChatResponse(conversation_id=conv_id, message=history)
