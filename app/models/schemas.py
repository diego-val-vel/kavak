# Define API request/response schemas to formalize the contract.

from typing import List, Literal, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class MessageItem(BaseModel):
    role: Literal["user", "bot"]
    message: str


class ChatResponse(BaseModel):
    conversation_id: str
    message: List[MessageItem]
