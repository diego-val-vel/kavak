"""
Prompt builder for debate-style conversations.

Consumes:
- Topic
- Stance
- A sliding window of recent messages from Redis

Produces:
- System and user prompts tailored to maintain the stance and remain persuasive.
"""

from __future__ import annotations

from typing import Dict, List

# {"role": "user"|"bot", "message": "..."}
MessageLike = Dict[str, str]


def build_system_prompt(topic: str, stance: str) -> str:
    """
    Builds the system prompt guiding the assistant to maintain a firm stance
    on the given topic and aim to persuade without being hostile.

    Notes:
    - The assistant must always reply in the user's current language (detected from the latest user message).
    - If topic or stance were not explicit in the first turn, consider the provided values as the initial seed
      and keep a consistent stance derived from that seed across the conversation.
    """
    return (
        "You are a debate assistant.\n"
        "Your objective is to firmly defend your assigned position and persuade the other side.\n"
        "Stay on topic, be coherent, avoid fallacies, and do not switch sides unless explicitly instructed.\n"
        "Use concise, well-structured arguments, anticipate counterpoints, and remain civil.\n\n"
        f"Topic: {topic}\n"
        f"Your stance: {stance}\n\n"
        "Global requirements:\n"
        "- Always reply in the user's language, detected from the latest user message. "
        "If the user switches languages, switch accordingly.\n"
        "- Maintain the same stance throughout the conversation. "
        "Acknowledge concerns without conceding the core position.\n"
        "- Be persuasive; provide reasons, short evidence summaries, and analogies when helpful.\n"
        "- Keep responses within a few paragraphs; avoid excessive verbosity.\n"
    )


def build_user_prompt(latest_user_message: str, recent_history: List[MessageLike]) -> str:
    """
    Builds the user-visible prompt that includes a compact transcript context.
    The history must be ordered oldest to newest and include both user and assistant roles.
    """
    transcript_lines: List[str] = []
    for item in recent_history:
        role = (item.get("role") or "").strip().lower()
        msg = (item.get("message") or "").strip()
        if not msg:
            continue

        if role == "user":
            transcript_lines.append(f"User: {msg}")
        elif role == "bot":
            transcript_lines.append(f"Assistant: {msg}")
        else:
            # Unknown role; include as-is to preserve context
            transcript_lines.append(f"{role}: {msg}")

    history_block = "\n".join(transcript_lines) if transcript_lines else "(no prior context)"

    return (
        "Conversation so far (oldest first):\n"
        f"{history_block}\n\n"
        "New message from user:\n"
        f"{latest_user_message}\n\n"
        "Using the conversation history above and maintaining your stance, provide a persuasive reply."
    )
