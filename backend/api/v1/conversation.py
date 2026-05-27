import uuid as _uuid

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import case, func, select

from models import Feedback, Message
from models.db import SessionLocal
from services import conversation_service
from services.voice_pipeline import run_chat_pipeline, run_voice_pipeline

log = structlog.get_logger()
router = APIRouter(tags=["conversation"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # ~30s clip headroom


class ChatRequest(BaseModel):
    text: str
    language_hint: str = "hi"


class ActionRequest(BaseModel):
    scheme_id: str
    action: str
    step_number: int | None = None


class FeedbackRequest(BaseModel):
    rating: int | None = None
    comment: str | None = None
    vote: str | None = None  # "up" | "down" | None
    chips: list[str] | None = None
    message_id: str | None = None


@router.post("/conversation/{conversation_id}/voice")
async def post_voice(
    conversation_id: str,
    audio: UploadFile = File(...),
    language_hint: str = Form("hi"),
    bitrate: str = "high",
):
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        log.warning(
            "voice_too_large", conversation_id=conversation_id, bytes=len(audio_bytes)
        )
    log.info(
        "voice_received",
        conversation_id=conversation_id,
        filename=audio.filename,
        content_type=audio.content_type,
        bytes=len(audio_bytes),
        language_hint=language_hint,
        bitrate=bitrate,
    )
    return await run_voice_pipeline(
        conversation_id=conversation_id,
        audio_bytes=audio_bytes,
        content_type=audio.content_type,
        filename=audio.filename,
        language_hint=language_hint,
        bitrate=bitrate,
    )


@router.post("/conversation/{conversation_id}/chat")
async def post_chat(conversation_id: str, body: ChatRequest):
    log.info(
        "chat_received",
        conversation_id=conversation_id,
        chars=len(body.text or ""),
        language_hint=body.language_hint,
    )
    return await run_chat_pipeline(
        conversation_id=conversation_id,
        text=body.text or "",
        language_hint=body.language_hint or "hi",
    )


@router.get("/conversation/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    try:
        messages = await conversation_service.list_messages(conversation_id)
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    return {"conversation_id": conversation_id, "messages": messages}


@router.get("/conversations")
async def list_conversations():
    try:
        grouped = await conversation_service.list_conversations_grouped()
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    return grouped


def _normalize_feedback_body(body: FeedbackRequest) -> tuple[int | None, str | None]:
    rating = body.rating
    if rating is None and body.vote:
        rating = {"up": 1, "down": -1}.get(body.vote.lower())
    comment = body.comment
    if body.chips:
        chips_text = ", ".join(c for c in body.chips if c)
        comment = chips_text if not comment else f"{comment} | {chips_text}"
    return rating, comment


@router.post("/conversation/{conversation_id}/feedback")
async def post_feedback(conversation_id: str, body: FeedbackRequest):
    rating, comment = _normalize_feedback_body(body)
    try:
        fb = await conversation_service.record_feedback(
            conversation_id,
            message_id=body.message_id,
            rating=rating,
            comment=comment,
        )
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    return {
        "id": fb.id,
        "conversation_id": str(fb.conversation_id) if fb.conversation_id else None,
        "message_id": str(fb.message_id) if fb.message_id else None,
        "rating": fb.rating,
        "comment": fb.comment,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


@router.get("/messages/{message_id}/explanation")
async def get_message_explanation(message_id: str):
    """Per-message Samjhao payload.

    why_hi / sources / confidence come from the message row itself.
    Community stats are aggregated across feedback rows that point at any
    message with the same top retrieved scheme_id - this is the natural
    "how do other users rate Sukanya-answers" grouping.
    """
    if SessionLocal is None:
        raise HTTPException(503, detail="DATABASE_URL not configured")
    try:
        msg_uuid = _uuid.UUID(message_id)
    except (ValueError, TypeError):
        raise HTTPException(400, detail="invalid message_id") from None

    async with SessionLocal() as session:
        msg = await session.get(Message, msg_uuid)
        if msg is None:
            raise HTTPException(404, detail="message not found")

        # Top retrieved scheme for this message - drives the community
        # aggregation lookup.
        schemes = msg.retrieved_schemes or []
        top_scheme = schemes[0] if schemes else None
        top_scheme_id = (top_scheme or {}).get("scheme_id") if top_scheme else None

        # why_hi: prefer the first chunk-derived snippet on the message.
        # Fall back to the matched-scheme summary.
        why_hi = ""
        if top_scheme:
            why_hi = (
                top_scheme.get("summary_hi")
                or top_scheme.get("one_line_pitch_hi")
                or ""
            )
        if not why_hi:
            why_hi = (msg.content_text or "")[:280]

        # Aggregate feedback across all messages sharing this top scheme.
        up = down = total = 0
        if top_scheme_id:
            agg_stmt = (
                select(
                    func.count().label("total"),
                    func.sum(case((Feedback.rating > 0, 1), else_=0)).label("up"),
                    func.sum(case((Feedback.rating < 0, 1), else_=0)).label("down"),
                )
                .select_from(Feedback)
                .join(Message, Message.id == Feedback.message_id)
                .where(
                    Message.retrieved_schemes[0]["scheme_id"].astext == top_scheme_id
                )
            )
            try:
                row = (await session.execute(agg_stmt)).first()
                if row is not None:
                    total = int(row.total or 0)
                    up = int(row.up or 0)
                    down = int(row.down or 0)
            except Exception as e:
                log.warning("feedback_agg_failed", error=str(e))

    agreement_pct = round((100.0 * up) / total) if total else 0

    return {
        "message_id": str(msg.id),
        "scheme_id": top_scheme_id,
        "why_hi": why_hi,
        "sources": msg.sources or [],
        "confidence": (
            msg.confidence.value if hasattr(msg.confidence, "value") else msg.confidence
        ),
        "community_agreement_pct": agreement_pct,
        "community_vote_count": total,
        "community_up_count": up,
        "community_down_count": down,
    }


@router.post("/feedback")
async def post_feedback_root(body: FeedbackRequest):
    """Message-scoped feedback. Body must include message_id."""
    if not body.message_id:
        raise HTTPException(400, detail="message_id is required")
    rating, comment = _normalize_feedback_body(body)
    try:
        fb = await conversation_service.record_feedback(
            None, message_id=body.message_id, rating=rating, comment=comment
        )
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    return {
        "id": fb.id,
        "conversation_id": str(fb.conversation_id) if fb.conversation_id else None,
        "message_id": str(fb.message_id) if fb.message_id else None,
        "rating": fb.rating,
        "comment": fb.comment,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }


@router.post("/conversation/{conversation_id}/action")
async def post_action(conversation_id: str, body: ActionRequest):
    try:
        ua = await conversation_service.record_action(
            conversation_id,
            scheme_id=body.scheme_id,
            action=body.action,
            step_number=body.step_number,
        )
    except RuntimeError as e:
        raise HTTPException(503, detail=str(e))
    return {
        "id": str(ua.id),
        "conversation_id": str(ua.conversation_id),
        "scheme_id": ua.scheme_id,
        "action": ua.action,
        "step_number": ua.step_number,
        "created_at": ua.created_at.isoformat() if ua.created_at else None,
    }
