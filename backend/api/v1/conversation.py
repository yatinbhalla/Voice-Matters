import structlog
from fastapi import APIRouter, File, UploadFile
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter(tags=["conversation"])


class ChatRequest(BaseModel):
    text: str


class ActionRequest(BaseModel):
    action_type: str
    payload: dict | None = None


@router.post("/conversation/{conversation_id}/voice")
async def post_voice(conversation_id: str, audio: UploadFile = File(...)):
    log.info("voice_stub", conversation_id=conversation_id, filename=audio.filename)
    return {"conversation_id": conversation_id, "status": "not_implemented"}


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
