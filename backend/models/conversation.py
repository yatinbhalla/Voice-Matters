"""Unified conversation schema: conversations, messages, user_actions.

Voice (Home) and chat (Sahayak) both write into the same messages table;
modality discriminates the channel.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class Role(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class Modality(str, enum.Enum):
    voice = "voice"
    text = "text"


class Confidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(SQLEnum(Role, name="message_role"), nullable=False)
    modality: Mapped[Modality] = mapped_column(
        SQLEnum(Modality, name="message_modality"), nullable=False
    )
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    retrieved_schemes: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    eligibility_results: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    confidence: Mapped[Confidence | None] = mapped_column(
        SQLEnum(Confidence, name="message_confidence"), nullable=True
    )
    sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class UserAction(Base):
    __tablename__ = "user_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    scheme_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    step_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
