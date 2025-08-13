"""
Chat service orchestrating the conversation flow:
- Detect new vs. existing conversations
- Persist full history in PostgreSQL
- Maintain a sliding window in Redis for prompt context
- Build prompts and call the LLM client (OpenAI)
- Return the last 5 messages in chronological order ("most recent message last")
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from typing import List, Optional, Tuple

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse, MessageItem
from app.persistence.message_repo import add_message, get_last_n
from app.persistence.redis_store import RedisStore
from app.services.prompt_builder import build_system_prompt, build_user_prompt
from app.services.openai_client import OpenAIClient

# Configure module logger
logger = logging.getLogger("chat_service")

# Operational constants
HISTORY_WINDOW = 5
# 7 days
META_TTL_SECONDS = 7 * 24 * 60 * 60
# 7 days
HISTORY_TTL_SECONDS = 7 * 24 * 60 * 60

RESP_CACHE_TTL_SECONDS = 60
LOCK_TTL_SECONDS = 10


class ChatService:
    """
    High-level service that handles the end-to-end chat flow.
    One instance can be reused per request; dependencies (db, redis) are passed in.
    """

    def __init__(
        self,
        openai_client: Optional[OpenAIClient] = None,
        history_window: int = HISTORY_WINDOW,
    ) -> None:
        # Ensure logger level respects DEBUG flag without reconfiguring global handlers.
        logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

        # LLM client used throughout this class
        self._llm = openai_client or OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.openai_timeout_seconds,
        )
        self._history_window = history_window

    async def handle_message(
        self,
        payload: ChatRequest,
        db: AsyncSession,
        redis: Redis,
    ) -> ChatResponse:
        """
        Main entry point to process a message and produce a response.
        """
        store = RedisStore(redis)

        # New conversation
        if payload.conversation_id is None:
            conversation_id = self._new_conversation_id()
            topic, stance = self._extract_topic_and_stance(payload.message)

            # Initialize Redis metadata
            await store.set_meta(
                conversation_id,
                {
                    "topic": topic,
                    "stance": stance,
                    "created_at": str(int(time.time())),
                    "turn_count": "0",
                },
            )
            await store.expire_meta(conversation_id, META_TTL_SECONDS)

            # Persist first user message
            await add_message(db, conversation_id, role="user", content=payload.message)
            # Update sliding window
            await store.append_message(conversation_id, role="user", message=payload.message)
            await store.trim_history(conversation_id, keep_last_n=self._history_window)
            await store.expire_history(conversation_id, HISTORY_TTL_SECONDS)

            # Produce assistant reply
            assistant_text = await self._produce_reply(conversation_id, payload.message, store, db)

            # Persist assistant reply
            await add_message(db, conversation_id, role="bot", content=assistant_text)
            await store.append_message(conversation_id, role="bot", message=assistant_text)
            await store.trim_history(conversation_id, keep_last_n=self._history_window)

            # Update turn count
            await self._increment_turn_count(store, conversation_id)

            # Build response with last N messages
            last_messages = await store.get_history(conversation_id, last_n=self._history_window)
            items = [MessageItem(role=m["role"], message=m["message"]) for m in last_messages]
            return ChatResponse(conversation_id=conversation_id, message=items)

        # Existing conversation
        conversation_id = payload.conversation_id

        # Acquire lightweight lock to avoid concurrent double-processing
        locked = await store.acquire_lock(conversation_id, ttl_seconds=LOCK_TTL_SECONDS)
        if not locked:
            await asyncio.sleep(0.1)
            locked = await store.acquire_lock(conversation_id, ttl_seconds=LOCK_TTL_SECONDS)
            if not locked:
                window = await self._ensure_window(store, db, conversation_id)
                items = [MessageItem(role=m["role"], message=m["message"]) for m in window]
                return ChatResponse(conversation_id=conversation_id, message=items)

        try:
            cached = await store.get_cached_response(conversation_id, payload.message)
            if cached:
                await add_message(db, conversation_id, role="user", content=payload.message)
                await store.append_message(conversation_id, role="user", message=payload.message)
                await store.trim_history(conversation_id, keep_last_n=self._history_window)

                await add_message(db, conversation_id, role="bot", content=cached)
                await store.append_message(conversation_id, role="bot", message=cached)
                await store.trim_history(conversation_id, keep_last_n=self._history_window)

                await self._increment_turn_count(store, conversation_id)

                window = await store.get_history(conversation_id, last_n=self._history_window)
                items = [MessageItem(role=m["role"], message=m["message"]) for m in window]
                return ChatResponse(conversation_id=conversation_id, message=items)

            await self._ensure_window(store, db, conversation_id)

            await add_message(db, conversation_id, role="user", content=payload.message)
            await store.append_message(conversation_id, role="user", message=payload.message)
            await store.trim_history(conversation_id, keep_last_n=self._history_window)

            assistant_text = await self._produce_reply(conversation_id, payload.message, store, db)

            await add_message(db, conversation_id, role="bot", content=assistant_text)
            await store.append_message(conversation_id, role="bot", message=assistant_text)
            await store.trim_history(conversation_id, keep_last_n=self._history_window)

            await store.set_cached_response(
                conversation_id,
                payload.message,
                assistant_text,
                ttl_seconds=RESP_CACHE_TTL_SECONDS,
            )

            await self._increment_turn_count(store, conversation_id)

            window = await store.get_history(conversation_id, last_n=self._history_window)
            items = [MessageItem(role=m["role"], message=m["message"]) for m in window]
            return ChatResponse(conversation_id=conversation_id, message=items)

        finally:
            await store.release_lock(conversation_id)

    async def _produce_reply(
        self,
        conversation_id: str,
        latest_user_message: str,
        store: RedisStore,
        db: AsyncSession,
    ) -> str:
        meta = await store.get_meta(conversation_id)
        topic = meta.get("topic") or "Use the initial instruction as the topic."
        stance = meta.get("stance") or (
            "Adopt a clear position based on the initial instruction and defend it."
        )

        recent = await store.get_history(conversation_id, last_n=self._history_window)
        if not recent:
            recent = await self._rehydrate_window_from_db(conversation_id, store, db)

        system_prompt = build_system_prompt(topic=topic, stance=stance)
        user_prompt = build_user_prompt(
            latest_user_message=latest_user_message,
            recent_history=recent
        )

        try:
            response_text = await self._llm.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.6,
                max_tokens=400,
            )
        except asyncio.TimeoutError:
            response_text = (
                "I am experiencing temporary delays. Here is a concise argument maintaining my stance: "
                "The position remains well supported by the points already presented."
            )

        return response_text.strip() if response_text else "..."

    @staticmethod
    async def _increment_turn_count(store: RedisStore, conversation_id: str) -> None:
        meta = await store.get_meta(conversation_id)
        try:
            turns = int(meta.get("turn_count", "0")) + 1
        except ValueError:
            turns = 1
        meta["turn_count"] = str(turns)
        await store.set_meta(conversation_id, meta)
        await store.expire_meta(conversation_id, META_TTL_SECONDS)

    async def _ensure_window(
        self,
        store: RedisStore,
        db: AsyncSession,
        conversation_id: str,
    ) -> List[dict]:
        window = await store.get_history(conversation_id, last_n=self._history_window)
        if window:
            return window
        return await self._rehydrate_window_from_db(conversation_id, store, db)

    async def _rehydrate_window_from_db(
        self,
        conversation_id: str,
        store: RedisStore,
        db: AsyncSession,
    ) -> List[dict]:
        records = await get_last_n(db, conversation_id, self._history_window)
        for rec in records:
            await store.append_message(conversation_id, role=rec.role, message=rec.message)
        await store.trim_history(conversation_id, keep_last_n=self._history_window)
        await store.expire_history(conversation_id, HISTORY_TTL_SECONDS)
        return [{"role": r.role, "message": r.message} for r in records]

    @staticmethod
    def _new_conversation_id() -> str:
        return uuid.uuid4().hex

    @staticmethod
    def _extract_topic_and_stance(first_message: str) -> Tuple[str, str]:
        text = first_message.strip()
        topic = ""
        stance = ""
        topic_match = re.search(r"(?:^|\b)topic\s*[:=]\s*(.*?)(?:;|\||$)", text, flags=re.IGNORECASE)
        stance_match = re.search(r"(?:^|\b)stance\s*[:=]\s*(.*?)(?:;|\||$)", text, flags=re.IGNORECASE)
        if topic_match:
            topic = topic_match.group(1).strip()
        if stance_match:
            stance = stance_match.group(1).strip()
        if not topic:
            topic = text
        if not stance:
            stance = "Choose a clear position implied by the initial instruction and defend it consistently."
        return topic, stance
