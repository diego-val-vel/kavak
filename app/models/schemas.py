"""
Pydantic schemas for chat API requests and responses.

Defines input validation for conversation identifiers and messages, and
structures the response payload with a bounded recent-history list.
"""

from __future__ import annotations

import re
from typing import List, Literal, Optional

from pydantic import BaseModel, field_validator, model_validator

# Basic input constraints
MAX_MESSAGE_CHARS = 4000
_CONV_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class ChatRequest(BaseModel):
    """
    Request payload for the chat endpoint.

    Includes an optional conversation identifier and the user's message.
    """
    conversation_id: Optional[str] = None
    message: str

    @field_validator("conversation_id")
    @classmethod
    def _validate_conversation_id(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip().lower()
        if not _CONV_ID_RE.match(v):
            raise ValueError(
                "conversation_id must be a 32-char lowercase hex string (uuid4 hex)."
            )
        return v

    @field_validator("message")
    @classmethod
    def _validate_message(cls, v: str) -> str:
        if v is None:
            raise ValueError("message is required.")
        v = v.strip()
        if not v:
            raise ValueError("message cannot be empty.")
        if len(v) > MAX_MESSAGE_CHARS:
            raise ValueError(f"message exceeds {MAX_MESSAGE_CHARS} characters.")
        return v


class MessageItem(BaseModel):
    """
    Message item within the recent-history window.

    Represents either a user or bot message.
    """
    role: Literal["user", "bot"]
    message: str

    @field_validator("message")
    @classmethod
    def _validate_item_message(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("message cannot be empty.")
        # Max-length is not enforced here, outputs or persisted inputs may exceed it.
        return v


class ChatResponse(BaseModel):
    """
    Response payload for the chat endpoint.

    Contains the conversation identifier and the most recent combined messages
    (newest last).
    """
    conversation_id: str
    message: List[MessageItem]

    @field_validator("conversation_id")
    @classmethod
    def _validate_resp_conversation_id(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if not _CONV_ID_RE.match(v):
            raise ValueError("conversation_id invalid in response.")
        return v

    @model_validator(mode="after")
    def _validate_history_not_empty(self) -> "ChatResponse":
        """
        Ensures the response always includes a non-null message history.
        The service logic guarantees at least one item.
        """
        if self.message is None:
            raise ValueError("message history cannot be null.")
        return self
