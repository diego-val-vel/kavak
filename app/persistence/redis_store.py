"""
Provide an asynchronous Redis store abstraction for conversation state.
Keep only what we actually use:

- Conversation metadata (topic, stance, etc.)
- Sliding window history (e.g., last 5 messages)
- Short-lived response cache (dedup immediate retries)
- Lightweight per-conversation lock (avoid concurrent double-processing)
"""

from __future__ import annotations

import json
import hashlib
from typing import List, Optional, Dict

from redis.asyncio import Redis


class RedisStore:
    """
    Wrap a Redis asyncio client and expose operations needed by the service.
    The store does not own the client's lifecycle; caller is responsible for creation.
    """

    def __init__(self, client: Redis) -> None:
        self._client = client

    # Key builders

    @staticmethod
    def _meta_key(conversation_id: str) -> str:
        return f"conv:{conversation_id}:meta"

    @staticmethod
    def _history_key(conversation_id: str) -> str:
        return f"conv:{conversation_id}:history"

    @staticmethod
    def _lock_key(conversation_id: str) -> str:
        return f"lock:conv:{conversation_id}"

    @staticmethod
    def _resp_cache_key(conversation_id: str, user_payload: str) -> str:
        # Hash user payload to keep key short and avoid PII in keys
        digest = hashlib.sha256(user_payload.encode("utf-8")).hexdigest()
        return f"resp_cache:{conversation_id}:{digest}"


    # Conversation metadata
    async def set_meta(self, conversation_id: str, meta: Dict[str, str]) -> None:
        """
        Store conversation metadata (e.g., topic, stance, created_at, turn_count).
        Values are stored as strings in a Redis HASH.
        """
        key = self._meta_key(conversation_id)
        await self._client.hset(key, mapping=meta)

    async def get_meta(self, conversation_id: str) -> Dict[str, str]:
        """
        Return conversation metadata as a dict of strings.
        Return empty dict if metadata does not exist.
        """
        key = self._meta_key(conversation_id)
        data = await self._client.hgetall(key)
        return dict(data) if data else {}

    async def expire_meta(self, conversation_id: str, ttl_seconds: int) -> None:
        """Set TTL for conversation metadata."""
        await self._client.expire(self._meta_key(conversation_id), ttl_seconds)


    # Sliding window via LIST
    async def append_message(self, conversation_id: str, role: str, message: str) -> None:
        """
        Append a message (role, message) to the conversation window.
        Stored as a JSON line to keep list operations simple.
        """
        item = json.dumps({"role": role, "message": message}, ensure_ascii=False)
        await self._client.rpush(self._history_key(conversation_id), item)


    async def get_history(self, conversation_id: str, last_n: Optional[int] = None) -> List[dict]:
        """
        Retrieve the conversation window as a list of dicts in insertion order.
        If last_n is provided, return only the most recent N items.
        """
        key = self._history_key(conversation_id)
        if last_n is None:
            raw_items = await self._client.lrange(key, 0, -1)
        else:
            raw_items = await self._client.lrange(key, -last_n, -1)

        history: List[dict] = []
        for raw in raw_items:
            try:
                history.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return history


    async def trim_history(self, conversation_id: str, keep_last_n: int) -> None:
        """Keep only the most recent N messages."""
        await self._client.ltrim(self._history_key(conversation_id), -keep_last_n, -1)


    async def expire_history(self, conversation_id: str, ttl_seconds: int) -> None:
        """Set TTL for the conversation history key."""
        await self._client.expire(self._history_key(conversation_id), ttl_seconds)

    # Response short cache
    async def get_cached_response(self, conversation_id: str, user_payload: str) -> Optional[str]:
        """
        Return a cached bot response for the exact same user payload, if recently cached.
        Useful for quick retries; returns None if not present.
        """
        key = self._resp_cache_key(conversation_id, user_payload)
        return await self._client.get(key)

    async def set_cached_response(
        self,
        conversation_id: str,
        user_payload: str,
        bot_response: str,
        ttl_seconds: int = 60,
    ) -> None:
        """
        Cache the bot response for a short period to deduplicate immediate retries.
        """
        key = self._resp_cache_key(conversation_id, user_payload)
        await self._client.set(key, bot_response, ex=ttl_seconds)

    # Lightweight conversation lock
    async def acquire_lock(self, conversation_id: str, ttl_seconds: int = 10) -> bool:
        """
        Try to acquire a short-lived lock for a conversation to avoid concurrent processing.
        Returns True if lock acquired, False otherwise.
        Implemented with SET key value NX EX.
        """
        key = self._lock_key(conversation_id)
        # Using conversation_id as value is sufficient here; any non-empty value works
        return await self._client.set(key, conversation_id, nx=True, ex=ttl_seconds) is True

    async def release_lock(self, conversation_id: str) -> None:
        """Release the conversation lock."""
        await self._client.delete(self._lock_key(conversation_id))
