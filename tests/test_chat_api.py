"""
Test suite for the /v1/chat endpoint.

Covers:
- Creation of new conversations and validation of returned data.
- Sliding window behavior to retain only the most recent five messages.
- Validation errors when required fields are missing.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_new_conversation_returns_id_and_history(test_client):
    """Verifies that a new conversation returns a valid ID and initial message history."""
    payload = {
        "conversation_id": None,
        "message": "Topic: The Earth is flat; Stance: for. Opening argument: horizon looks flat."
    }
    resp = await test_client.post("/v1/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data["conversation_id"], str) and data["conversation_id"]
    assert isinstance(data["message"], list) and len(data["message"]) >= 1
    assert data["message"][-1]["role"] == "bot"
    assert data["message"][-1]["message"] == "TEST_BOT_REPLY"


@pytest.mark.asyncio
async def test_sliding_window_keeps_last_five_messages(test_client):
    """Ensures that the sliding window retains no more than five messages."""
    # Initialize conversation
    r0 = await test_client.post("/v1/chat", json={
        "conversation_id": None,
        "message": "Topic: Flat Earth; Stance: for."
    })
    assert r0.status_code == 200
    conv_id = r0.json()["conversation_id"]

    # Send multiple turns; the window must not exceed five messages
    for i in range(6):
        r = await test_client.post("/v1/chat", json={
            "conversation_id": conv_id,
            "message": f"turn {i}"
        })
        assert r.status_code == 200
        win = r.json()["message"]
        assert 1 <= len(win) <= 5

    # Verify final state: exactly five messages and the last one from the bot
    final = await test_client.post("/v1/chat", json={
        "conversation_id": conv_id,
        "message": "final check"
    })
    assert final.status_code == 200
    win = final.json()["message"]
    assert len(win) == 5
    assert win[-1]["role"] == "bot"
    assert win[-1]["message"] == "TEST_BOT_REPLY"


@pytest.mark.asyncio
async def test_validation_missing_message_returns_422(test_client):
    """Checks that missing 'message' field returns a 422 validation error."""
    resp = await test_client.post("/v1/chat", json={"conversation_id": None})
    assert resp.status_code == 422
