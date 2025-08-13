"""
Provide repository functions for persisting and querying conversation messages.
This layer isolates SQL details from services and endpoints.
"""

from __future__ import annotations

from typing import List, Sequence

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.persistence.database import Message


async def add_message(
    session: AsyncSession,
    conversation_id: str,
    role: str,
    content: str,
) -> Message:
    """
    Persist a single message and return the ORM instance (with PK).
    """
    msg = Message(conversation_id=conversation_id, role=role, message=content)
    session.add(msg)
    await session.flush()
    return msg


async def add_messages(
    session: AsyncSession,
    items: Sequence[tuple[str, str, str]],
) -> List[Message]:
    """
    Bulk insert convenience: items = [(conversation_id, role, content), ...]
    Returns the list of persisted Message instances.
    """
    objs: List[Message] = [
        Message(conversation_id=c, role=r, message=m) for (c, r, m) in items
    ]
    session.add_all(objs)
    await session.flush()
    return objs


async def get_messages(
    session: AsyncSession,
    conversation_id: str,
    limit: int | None = None,
    offset: int = 0,
    ascending: bool = True,
) -> List[Message]:
    """
    Return messages for a conversation. Default sorting is chronological ascending.
    """
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if ascending:
        stmt = stmt.order_by(Message.created_at.asc(), Message.id.asc())
    else:
        stmt = stmt.order_by(Message.created_at.desc(), Message.id.desc())

    if limit is not None:
        stmt = stmt.limit(limit).offset(offset)

    res = await session.execute(stmt)
    rows = res.scalars().all()
    return list(rows)


async def get_last_n(
    session: AsyncSession,
    conversation_id: str,
    n: int,
) -> List[Message]:
    """
    Return the most recent N messages in chronological order (oldest first).
    """
    # First fetch newest N descending, then reverse to chronological
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(n)
    )
    res = await session.execute(stmt)
    rows_desc = list(res.scalars().all())
    rows_desc.reverse()
    return rows_desc


async def count_messages(session: AsyncSession, conversation_id: str) -> int:
    """
    Return total number of messages for a conversation.
    """
    stmt = select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
    res = await session.execute(stmt)
    return int(res.scalar_one())
