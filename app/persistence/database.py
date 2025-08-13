"""
Define SQLAlchemy ORM metadata and models.
This module does not create the engine nor the session; those are provided by app.core.dependencies.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Index, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Common declarative base for all ORM models."""
    pass


class Message(Base):
    """
    Represent a single utterance in a conversation.
    Stores both user and bot messages to reconstruct full history.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(16))
    message: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        Index("ix_messages_conv_created", "conversation_id", "created_at"),
    )


async def init_models(engine) -> None:
    """
    Create database tables based on ORM metadata.
    Intended for local/dev environments; use migrations in production.
    """
    from sqlalchemy.ext.asyncio import AsyncEngine
    if not isinstance(engine, AsyncEngine):
        raise TypeError("init_models expects an AsyncEngine")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
