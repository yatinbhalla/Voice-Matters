"""Voice pipeline: audio in -> envelope out.

Stages (timings logged per-stage, total, and persisted to telemetry):
  stt   - Sarvam Saaras
  rag   - hardcoded Sushila top-3 (real retrieval lands in Prompt 6)
  llm   - hardcoded Hindi response (real Mayura call lands in Prompt 6)
  tts   - Sarvam Bulbul -> mp3 on disk under /backend/static/audio
"""
import time
import uuid
from pathlib import Path

import structlog

from clients.sarvam_client import SarvamClient
from data.sushila_stub import STUB_RESPONSE_HI, TOP_3_SCHEMES
from models import Telemetry
from models.db import SessionLocal
from services import conversation_service
from services.audio import save_and_normalize

log = structlog.get_logger()

STATIC_AUDIO_DIR = Path(__file__).resolve().parent.parent / "static" / "audio"
STATIC_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _ms_since(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


async def _persist_telemetry(payload: dict) -> None:
    if SessionLocal is None:
        return
    try:
        async with SessionLocal() as session:
            session.add(Telemetry(event_type="voice_pipeline", payload=payload))
            await session.commit()
    except Exception as e:
        log.warning("telemetry_insert_failed", error=str(e))


async def run_voice_pipeline(
    conversation_id: str,
    audio_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    language_hint: str = "hi",
) -> dict:
    sarvam = SarvamClient()
    pipeline_start = time.perf_counter()
    message_id = uuid.uuid4().hex

    # Ensure the conversation row exists before we append any messages.
    try:
        conv = await conversation_service.get_or_create(conversation_id)
        canonical_conv_id = str(conv.id)
    except Exception as e:
        log.warning("conversation_create_failed", error=str(e))
        canonical_conv_id = conversation_id

    # Stage 0: normalize audio (write /tmp/<uuid>.<ext>, transcode if needed)
    norm_start = time.perf_counter()
    norm_bytes, norm_mime, norm_filename = await save_and_normalize(
        audio_bytes, content_type, filename
    )
    norm_ms = _ms_since(norm_start)

    # Stage 1: STT
    stt_start = time.perf_counter()
    try:
        transcript_hi = await sarvam.transcribe(
            norm_bytes,
            language_code=f"{language_hint}-IN" if "-" not in language_hint else language_hint,
            filename=norm_filename,
            content_type=norm_mime,
        )
    except Exception as e:
        log.error("stt_failed", error=str(e))
        transcript_hi = ""
    stt_ms = _ms_since(stt_start)

    # Stage 2: RAG (stub)
    rag_start = time.perf_counter()
    top_3 = TOP_3_SCHEMES
    rag_ms = _ms_since(rag_start)

    # Stage 3: LLM (stub)
    llm_start = time.perf_counter()
    response_text_hi = STUB_RESPONSE_HI
    llm_ms = _ms_since(llm_start)

    # Stage 4: TTS
    tts_start = time.perf_counter()
    audio_filename = f"{uuid.uuid4().hex}.mp3"
    audio_url = ""
    try:
        # Sarvam retired "meera"; "anushka" is the closest current female voice.
        tts_bytes = await sarvam.synthesize(response_text_hi, voice="anushka")
        (STATIC_AUDIO_DIR / audio_filename).write_bytes(tts_bytes)
        audio_url = f"/static/audio/{audio_filename}"
    except Exception as e:
        log.error("tts_failed", error=str(e))
    tts_ms = _ms_since(tts_start)

    total_ms = _ms_since(pipeline_start)

    log.info(
        "voice_pipeline_done",
        conversation_id=conversation_id,
        message_id=message_id,
        norm_ms=norm_ms,
        stt_ms=stt_ms,
        rag_ms=rag_ms,
        llm_ms=llm_ms,
        tts_ms=tts_ms,
        total_ms=total_ms,
        transcript_chars=len(transcript_hi),
    )

    await _persist_telemetry(
        {
            "conversation_id": conversation_id,
            "message_id": message_id,
            "norm_ms": norm_ms,
            "stt_ms": stt_ms,
            "rag_ms": rag_ms,
            "llm_ms": llm_ms,
            "tts_ms": tts_ms,
            "total_ms": total_ms,
            "transcript_chars": len(transcript_hi),
            "tts_ok": bool(audio_url),
        }
    )

    sources = [
        {"title": s["name_en"], "url": s["source_url"], "scheme_id": s["scheme_id"]}
        for s in top_3
    ]
    explanations = [
        {
            "span_text": top_3[0]["name_hi"],
            "why_hi": top_3[0]["one_line_pitch_hi"],
            "source_url": top_3[0]["source_url"],
        }
    ]

    # Persist both turns. Fail-soft: if the DB write fails we still return
    # the envelope so the user gets their answer.
    persisted_message_id = message_id
    try:
        await conversation_service.append_message(
            canonical_conv_id,
            role="user",
            modality="voice",
            content_text=transcript_hi,
        )
        assistant_msg = await conversation_service.append_message(
            canonical_conv_id,
            role="assistant",
            modality="voice",
            content_text=response_text_hi,
            content_audio_url=audio_url or None,
            retrieved_schemes=top_3,
            sources=sources,
            confidence="medium",
        )
        persisted_message_id = str(assistant_msg.id)
    except Exception as e:
        log.warning("message_persist_failed", error=str(e))

    return {
        "transcript_hi": transcript_hi,
        "response_text_hi": response_text_hi,
        "response_audio_url": audio_url,
        "top_3_schemes": top_3,
        "eligibility_results": [],
        "confidence": "medium",
        "sources": sources,
        "explanations": explanations,
        "conversation_id": canonical_conv_id,
        "message_id": persisted_message_id,
    }
