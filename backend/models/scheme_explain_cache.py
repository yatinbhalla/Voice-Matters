"""Cache table for /schemes/{id}/explain.

Composite PK (scheme_id, length) so repeated requests at the same length
are served straight from the row without re-running LLM + TTS.
"""
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .base import Base


class SchemeExplainCache(Base):
    __tablename__ = "scheme_explain_cache"

    scheme_id: Mapped[str] = mapped_column(String, primary_key=True)
    length: Mapped[str] = mapped_column(String, primary_key=True)  # short | medium | long
    explanation_text_hi: Mapped[str] = mapped_column(Text, nullable=False)
    explanation_audio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
