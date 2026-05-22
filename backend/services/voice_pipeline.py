"""Voice pipeline: audio in -> envelope out.

Stages (timings logged per-stage and persisted to telemetry):
  norm  - ffmpeg transcode to wav 16k mono (or passthrough)
  stt   - Sarvam Saaras
  rag   - OpenAI embed + Pinecone similarity
  llm   - Sarvam chat with the retrieved chunks (RAG_ANSWER_SYSTEM_HI)
  tts   - Sarvam Bulbul -> mp3 on disk under /backend/static/audio

Empty retrieval triggers the refusal path inside AnswerService.
"""
import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select

from clients.sarvam_client import SarvamClient
from models import SchemeMeta, Telemetry
from models.db import SessionLocal
from services import conversation_service
from services.answer_service import AnswerService
from services.audio import save_and_normalize
from services.eligibility_service import EligibilityService
from services.rag_service import RAGService

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


async def _all_known_scheme_names() -> list[tuple[str, str]]:
    """For the hallucination guard: every scheme name we have in the DB.
    Returns list of (scheme_id, name) tuples for both English and Hindi names.
    """
    if SessionLocal is None:
        return []
    try:
        async with SessionLocal() as session:
            result = await session.execute(select(SchemeMeta))
            rows = result.scalars().all()
        out: list[tuple[str, str]] = []
        for r in rows:
            if r.name:
                out.append((r.scheme_id, r.name))
        return out
    except Exception as e:
        log.warning("scheme_meta_load_failed", error=str(e))
        return []


async def run_voice_pipeline(
    conversation_id: str,
    audio_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    language_hint: str = "hi",
) -> dict:
    sarvam = SarvamClient()
    rag = RAGService()
    answerer = AnswerService(sarvam=sarvam)
    eligibility = EligibilityService(sarvam=sarvam)

    pipeline_start = time.perf_counter()
    message_id = uuid.uuid4().hex

    # Ensure conversation exists.
    try:
        conv = await conversation_service.get_or_create(conversation_id)
        canonical_conv_id = str(conv.id)
    except Exception as e:
        log.warning("conversation_create_failed", error=str(e))
        canonical_conv_id = conversation_id

    # Stage 0: normalize audio
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
            language_code=(
                f"{language_hint}-IN" if "-" not in language_hint else language_hint
            ),
            filename=norm_filename,
            content_type=norm_mime,
        )
    except Exception as e:
        log.error("stt_failed", error=str(e))
        transcript_hi = ""
    stt_ms = _ms_since(stt_start)

    # Stage 2: RAG retrieval
    rag_start = time.perf_counter()
    retrieved_chunks = await rag.retrieve(transcript_hi, top_k=5, min_score=0.75)
    rag_ms = _ms_since(rag_start)

    # Stage 3: LLM answer
    llm_start = time.perf_counter()
    known_names = await _all_known_scheme_names()
    answer = await answerer.answer(
        transcript_hi, retrieved_chunks, all_known_scheme_names=known_names
    )
    llm_ms = _ms_since(llm_start)
    response_text_hi = answer.response_text_hi
    top_schemes = answer.top_schemes
    sources = answer.sources
    confidence = answer.confidence

    # Stage 3.5: eligibility check (separate LLM call to extract facts)
    elig_start = time.perf_counter()
    eligibility_results: list[dict] = []
    follow_up_question_hi: str | None = None
    if retrieved_chunks and not answer.refused:
        try:
            results, follow_up_question_hi, _ = await eligibility.check(
                transcript_hi, retrieved_chunks
            )
            eligibility_results = [r.to_dict() for r in results]
        except Exception as e:
            log.warning("eligibility_check_failed", error=str(e))
    elig_ms = _ms_since(elig_start)

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
        conversation_id=canonical_conv_id,
        message_id=message_id,
        norm_ms=norm_ms,
        stt_ms=stt_ms,
        rag_ms=rag_ms,
        llm_ms=llm_ms,
        elig_ms=elig_ms,
        tts_ms=tts_ms,
        total_ms=total_ms,
        transcript_chars=len(transcript_hi),
        retrieved=len(retrieved_chunks),
        refused=answer.refused,
        confidence=confidence,
        eligibility_n=len(eligibility_results),
    )

    await _persist_telemetry(
        {
            "conversation_id": canonical_conv_id,
            "message_id": message_id,
            "norm_ms": norm_ms,
            "stt_ms": stt_ms,
            "rag_ms": rag_ms,
            "llm_ms": llm_ms,
            "elig_ms": elig_ms,
            "tts_ms": tts_ms,
            "total_ms": total_ms,
            "transcript_chars": len(transcript_hi),
            "tts_ok": bool(audio_url),
            "retrieved": len(retrieved_chunks),
            "refused": answer.refused,
            "confidence": confidence,
            "eligibility_n": len(eligibility_results),
        }
    )

    explanations: list[dict] = []
    if top_schemes:
        explanations = [
            {
                "span_text": top_schemes[0]["name_en"],
                "why_hi": (
                    retrieved_chunks[0].text[:280] + "…"
                    if retrieved_chunks and len(retrieved_chunks[0].text) > 280
                    else (retrieved_chunks[0].text if retrieved_chunks else "")
                ),
                "source_url": top_schemes[0]["source_url"],
            }
        ]

    # Frontend currently consumes name_en/one_line_pitch_hi/effort/benefit fields.
    # Adapt the deduped scheme dicts to the legacy envelope shape.
    top_3_envelope = [
        {
            "scheme_id": s["scheme_id"],
            "name_hi": s["name_hi"],
            "name_en": s["name_en"],
            "one_line_pitch_hi": "",
            "benefit_amount_inr": None,
            "effort": "low",
            "source_url": s["source_url"],
            "match_confidence": s["match_confidence"],
        }
        for s in top_schemes[:3]
    ]

    # Persist both turns. Fail-soft.
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
            retrieved_schemes=top_3_envelope,
            sources=sources,
            confidence=confidence,
            eligibility_results=eligibility_results,
        )
        persisted_message_id = str(assistant_msg.id)
    except Exception as e:
        log.warning("message_persist_failed", error=str(e))

    return {
        "transcript_hi": transcript_hi,
        "response_text_hi": response_text_hi,
        "response_audio_url": audio_url,
        "top_3_schemes": top_3_envelope,
        "eligibility_results": eligibility_results,
        "follow_up_question_hi": follow_up_question_hi,
        "confidence": confidence,
        "sources": sources,
        "explanations": explanations,
        "conversation_id": canonical_conv_id,
        "message_id": persisted_message_id,
    }
