import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from services import conversation_service
from services.voice_pipeline import run_voice_pipeline

log = structlog.get_logger()
router = APIRouter(tags=["conversation"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # ~30s clip headroom


class ChatRequest(BaseModel):
    text: str


class ActionRequest(BaseModel):
    scheme_id: str
    action: str
    step_number: int | None = None


@router.post("/conversation/{conversation_id}/voice")
async def post_voice(
    conversation_id: str,
    audio: UploadFile = File(...),
    language_hint: str = Form("hi"),
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
    )
    return await run_voice_pipeline(
        conversation_id=conversation_id,
        audio_bytes=audio_bytes,
        content_type=audio.content_type,
        filename=audio.filename,
        language_hint=language_hint,
    )


@router.post("/conversation/{conversation_id}/chat")
async def post_chat(conversation_id: str, body: ChatRequest):
    log.info("chat_stub", conversation_id=conversation_id)
    return {"conversation_id": conversation_id, "status": "not_implemented"}


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
