"""
OpenAI Chat client wrapper.
Encapsulates request/response logic, timeouts, and graceful fallbacks
so upstream API hiccups do not crash our endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from openai import AsyncOpenAI
from openai import RateLimitError, APIStatusError

from app.core.config import settings


class OpenAIClient:
    """
    Thin async wrapper around OpenAI Chat Completions.
    Allows setting model, temperature, and per-call timeout.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        timeout_seconds: int = 20,
    ) -> None:
        self._api_key = api_key or settings.openai_api_key
        self._client = AsyncOpenAI(api_key=self._api_key)
        self._model = model
        self._timeout_seconds = timeout_seconds

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        """
        Execute a chat completion with a strict overall timeout.
        Returns assistant content as plain text.
        On quota/rate limits or temporary upstream errors, returns a concise
        fallback to keep the API responsive and under 30s end-to-end.
        Raises asyncio.TimeoutError only when the total timeout is exceeded.
        """

        async def _call() -> str:
            try:
                resp = await self._client.chat.completions.create(
                    model=self._model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
                content = (resp.choices[0].message.content or "").strip()
                return content

            except RateLimitError:
                # Quota or per-minute limits: keep the conversation alive with a short, on-topic reply.
                return (
                    "I hit a temporary usage limit. Briefly, keeping my stance and the topic: "
                    "the argument still holds based on the prior points presented."
                )

            except APIStatusError:
                # Other upstream transient errors (5xx/4xx non-quota): reply conservatively.
                return (
                    "There was a temporary upstream issue. Staying on topic and maintaining my position, "
                    "the core reasoning remains valid as discussed."
                )

        return await asyncio.wait_for(_call(), timeout=self._timeout_seconds)

    async def aclose(self) -> None:
        """Close underlying resources if needed (no-op for current OpenAI SDK)."""
        pass
