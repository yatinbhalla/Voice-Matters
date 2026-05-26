"""ConversationService - the only place we read/write conversation tables.

Public surface:
  get_or_create(conversation_id)        -> Conversation
  append_message(conversation_id, ...)  -> Message
  list_messages(conversation_id)        -> list[Message]
  list_conversations_grouped()          -> dict[str, list[Summary]]
  record_action(conversation_id, ...)   -> UserAction

The conversation_id arriving from the URL is a string (the frontend's
crypto.randomUUID, but our older verify scripts pass things like
"test123"). We coerce: real UUIDs pass through; anything else gets a
deterministic uuid5 mapping so existing scripts keep working.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models import Conversation, Feedback, Message, UserAction
from models.db import SessionLocal

log = structlog.get_logger()

_NAMESPACE = uuid.UUID("6f7a4b3d-1d2c-4f7b-9a5d-8e1a2b3c4d5e")


def coerce_conversation_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return uuid.uuid5(_NAMESPACE, str(value))


def _require_session() -> None:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL not configured")


async def get_or_create(conversation_id: str) -> Conversation:
    _require_session()
    conv_uuid = coerce_conversation_uuid(conversation_id)
    async with SessionLocal() as session:
        existing = await session.get(Conversation, conv_uuid)
        if existing is not None:
            return existing
        conv = Conversation(id=conv_uuid)
        session.add(conv)
        await session.commit()
        await session.refresh(conv)
        log.info("conversation_created", conversation_id=str(conv_uuid))
        return conv


async def append_message(
    conversation_id: str,
    *,
    role: str,
    modality: str,
    content_text: str = "",
    content_audio_url: str | None = None,
    retrieved_schemes: list | None = None,
    eligibility_results: list | None = None,
    confidence: str | None = None,
    sources: list | None = None,
) -> Message:
    _require_session()
    conv_uuid = coerce_conversation_uuid(conversation_id)
    async with SessionLocal() as session:
        msg = Message(
            conversation_id=conv_uuid,
            role=role,
            modality=modality,
            content_text=content_text,
            content_audio_url=content_audio_url,
            retrieved_schemes=retrieved_schemes or [],
            eligibility_results=eligibility_results or [],
            confidence=confidence,
            sources=sources or [],
        )
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg


def _msg_dict(m: Message) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "role": m.role.value if hasattr(m.role, "value") else m.role,
        "modality": m.modality.value if hasattr(m.modality, "value") else m.modality,
        "content_text": m.content_text,
        "content_audio_url": m.content_audio_url,
        "retrieved_schemes": m.retrieved_schemes or [],
        "eligibility_results": m.eligibility_results or [],
        "confidence": (
            m.confidence.value if hasattr(m.confidence, "value") else m.confidence
        ),
        "sources": m.sources or [],
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


async def list_messages(conversation_id: str) -> list[dict]:
    _require_session()
    conv_uuid = coerce_conversation_uuid(conversation_id)
    async with SessionLocal() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conv_uuid)
            .order_by(Message.created_at.asc())
        )
        return [_msg_dict(m) for m in result.scalars().all()]


def _bucket_for(ts: datetime, now: datetime) -> str:
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if ts >= today_start:
        return "today"
    if ts >= now - timedelta(days=7):
        return "week"
    return "all"


def _badge_from_actions(actions: list[UserAction], has_response: bool) -> str:
    action_names = {a.action for a in actions}
    # Completion wins over everything else.
    if "applied_completed" in action_names or "applied" in action_names:
        return "applied"
    # Anyone partway through the apply flow is in_progress.
    if "step_completed" in action_names or "applied_started" in action_names:
        return "in_progress"
    if "saved" in action_names:
        return "saved"
    if "in_progress" in action_names:
        return "in_progress"
    return "answered" if has_response else "in_progress"


async def list_conversations_grouped() -> dict[str, list[dict]]:
    _require_session()
    now = datetime.now(timezone.utc)
    grouped: dict[str, list[dict]] = {"today": [], "week": [], "all": []}
    async with SessionLocal() as session:
        result = await session.execute(
            select(Conversation).options(selectinload(Conversation.messages))
        )
        conversations = result.scalars().unique().all()

        actions_q = await session.execute(select(UserAction))
        all_actions = actions_q.scalars().all()

    actions_by_conv: dict[uuid.UUID, list[UserAction]] = {}
    for a in all_actions:
        actions_by_conv.setdefault(a.conversation_id, []).append(a)

    summaries: list[tuple[datetime, dict]] = []
    for conv in conversations:
        msgs = sorted(conv.messages, key=lambda m: m.created_at)
        if not msgs:
            continue
        last_user = next(
            (m for m in reversed(msgs) if (m.role.value if hasattr(m.role, "value") else m.role) == "user"),
            None,
        )
        last_assistant = next(
            (m for m in reversed(msgs) if (m.role.value if hasattr(m.role, "value") else m.role) == "assistant"),
            None,
        )
        top_scheme = (last_assistant.retrieved_schemes[0]
                      if last_assistant and last_assistant.retrieved_schemes else None)
        summary = {
            "conversation_id": str(conv.id),
            "last_user_query_hi": last_user.content_text if last_user else "",
            "last_scheme_id": top_scheme.get("scheme_id") if top_scheme else None,
            "last_scheme_name": (
                (top_scheme.get("name_en") or top_scheme.get("name_hi"))
                if top_scheme else None
            ),
            "badge": _badge_from_actions(
                actions_by_conv.get(conv.id, []), bool(last_assistant)
            ),
            "timestamp": msgs[-1].created_at.isoformat() if msgs[-1].created_at else None,
        }
        ts = msgs[-1].created_at
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        summaries.append((ts, summary))

    summaries.sort(key=lambda t: t[0], reverse=True)
    for ts, summary in summaries:
        grouped[_bucket_for(ts, now)].append(summary)
    return grouped


async def record_feedback(
    conversation_id: str,
    *,
    rating: int | None = None,
    comment: str | None = None,
) -> Feedback:
    """Persist a rating/comment for the given conversation.

    The Feedback FK is SET NULL on conversation delete, but we still ensure
    the conversation row exists at insert time so the link survives.
    """
    _require_session()
    conv_uuid = coerce_conversation_uuid(conversation_id)
    async with SessionLocal() as session:
        existing = await session.get(Conversation, conv_uuid)
        if existing is None:
            session.add(Conversation(id=conv_uuid))
            await session.flush()
        fb = Feedback(conversation_id=conv_uuid, rating=rating, comment=comment)
        session.add(fb)
        await session.commit()
        await session.refresh(fb)
        return fb


async def record_action(
    conversation_id: str,
    *,
    scheme_id: str,
    action: str,
    step_number: int | None = None,
) -> UserAction:
    _require_session()
    conv_uuid = coerce_conversation_uuid(conversation_id)
    async with SessionLocal() as session:
        # Ensure the conversation row exists so the FK holds.
        existing = await session.get(Conversation, conv_uuid)
        if existing is None:
            session.add(Conversation(id=conv_uuid))
            await session.flush()
        ua = UserAction(
            conversation_id=conv_uuid,
            scheme_id=scheme_id,
            action=action,
            step_number=step_number,
        )
        session.add(ua)
        await session.commit()
        await session.refresh(ua)
        return ua
