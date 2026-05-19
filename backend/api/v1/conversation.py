import structlog
from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from services.voice_pipeline import run_voice_pipeline

log = structlog.get_logger()
router = APIRouter(tags=["conversation"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB hard ceiling for ~30s clips


class ChatRequest(BaseModel):
    text: str


class ActionRequest(BaseModel):
    action_type: str
    payload: dict | None = None


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
    log.info("messages_stub", conversation_id=conversation_id)
    return {"conversation_id": conversation_id, "messages": []}


@router.get("/conversations")
async def list_conversations():
    log.info("list_conversations_stub")
    return {"conversations": []}


@router.post("/conversation/{conversation_id}/action")
async def post_action(conversation_id: str, body: ActionRequest):
    log.info("action_stub", conversation_id=conversation_id, action_type=body.action_type)
    return {"conversation_id": conversation_id, "status": "not_implemented"}
