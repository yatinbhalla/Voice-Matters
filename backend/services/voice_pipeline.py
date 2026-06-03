"""Voice pipeline: audio in -> envelope out.

Stages (timings logged per-stage and persisted to telemetry):
  norm  - ffmpeg transcode to wav 16k mono (or passthrough)
  stt   - Sarvam Saaras
  rag   - OpenAI embed + Pinecone similarity
  llm   - Sarvam chat with the retrieved chunks (RAG_ANSWER_SYSTEM_HI)
  tts   - Sarvam Bulbul -> mp3 on disk under /backend/static/audio

Empty retrieval triggers the refusal path inside AnswerService.
"""
import asyncio
import time
import uuid
from pathlib import Path

import structlog
from sqlalchemy import select

from clients.sarvam_client import SarvamClient
from data import scheme_corpus
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


# ---------------------------------------------------------------------------
# Module-level singletons. Each of these wrappers holds a long-lived HTTPS
# connection pool (AsyncOpenAI / httpx.AsyncClient / Pinecone Index). Spinning
# them up per request was eating 3-5s of cold-start handshake on EVERY query.
# Construct once, reuse across the whole process.
# ---------------------------------------------------------------------------
_SARVAM = SarvamClient()
_RAG = RAGService()
_ANSWERER = AnswerService(sarvam=_SARVAM)
_ELIGIBILITY = EligibilityService(sarvam=_SARVAM)


async def run_voice_pipeline(
    conversation_id: str,
    audio_bytes: bytes,
    content_type: str | None,
    filename: str | None,
    language_hint: str = "hi",
    bitrate: str = "high",
) -> dict:
    sarvam = _SARVAM
    rag = _RAG
    answerer = _ANSWERER
    eligibility = _ELIGIBILITY

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
    # Let RAGService pick the provider-appropriate default (0.30 local, 0.75 openai).
    retrieved_chunks = await rag.retrieve(transcript_hi, top_k=5)
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

    # Stages 3.5 + 4 run in parallel: eligibility (LLM fact-extraction,
    # ~5-15s) and TTS (Bulbul synth, ~3-5s) share no data — running them
    # back-to-back wastes 3-15s on every voice query. asyncio.gather cuts
    # the wall-clock to max(eligibility, TTS) instead of sum.
    low_bitrate = (bitrate or "").lower() == "low"
    tts_sample_rate = 8000 if low_bitrate else 22050
    audio_filename = f"{uuid.uuid4().hex}{'-low' if low_bitrate else ''}.mp3"
    audio_url = ""
    eligibility_results: list[dict] = []
    follow_up_question_hi: str | None = None

    async def _do_eligibility():
        if not (retrieved_chunks and not answer.refused):
            return [], None, 0
        e_start = time.perf_counter()
        try:
            results, follow_up, _ = await eligibility.check(
                transcript_hi, retrieved_chunks
            )
            return (
                [r.to_dict() for r in results],
                follow_up,
                _ms_since(e_start),
            )
        except Exception as e:
            log.warning("eligibility_check_failed", error=str(e))
            return [], None, _ms_since(e_start)

    async def _do_tts():
        t_start = time.perf_counter()
        try:
            # Sarvam retired "meera"; "anushka" is the closest current female voice.
            tts_bytes = await sarvam.synthesize(
                response_text_hi, voice="anushka", sample_rate=tts_sample_rate
            )
            (STATIC_AUDIO_DIR / audio_filename).write_bytes(tts_bytes)
            return f"/static/audio/{audio_filename}", _ms_since(t_start)
        except Exception as e:
            log.error("tts_failed", error=str(e))
            return "", _ms_since(t_start)

    par_start = time.perf_counter()
    (eligibility_results, follow_up_question_hi, elig_ms), (audio_url, tts_ms) = (
        await asyncio.gather(_do_eligibility(), _do_tts())
    )
    par_wall_ms = _ms_since(par_start)
    log.info(
        "voice_parallel_done",
        elig_ms=elig_ms,
        tts_ms=tts_ms,
        wall_ms=par_wall_ms,
        saved_ms=(elig_ms + tts_ms) - par_wall_ms,
    )

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
    # Enrich each top scheme with display fields the schemes-list cards need.
    # Pulls from /scheme-corpus so we don't drift between display and source
    # of truth.
    top_3_envelope = []
    for s in top_schemes[:3]:
        corpus = scheme_corpus.get_scheme(s["scheme_id"]) or {}
        top_3_envelope.append(
            {
                "scheme_id": s["scheme_id"],
                "name_hi": s["name_hi"],
                "name_en": s["name_en"],
                "summary_hi": corpus.get("summary_hi", ""),
                "ministry": corpus.get("ministry"),
                "tags": corpus.get("tags", []),
                "one_line_pitch_hi": corpus.get("summary_hi", ""),
                "benefit_amount_inr": None,  # display layer chooses presentation
                "effort": "low",
                "source_url": s["source_url"],
                "match_confidence": s["match_confidence"],
            }
        )

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


async def run_chat_pipeline(
    conversation_id: str,
    text: str,
    language_hint: str = "hi",
) -> dict:
    """Text-only sibling of run_voice_pipeline.

    Skips audio normalize, Saaras STT, and Bulbul TTS. The remaining flow
    (RAG -> answer -> hallucination guard -> eligibility -> DB persist) is
    identical, and the returned envelope matches /voice's shape so the
    frontend can render either response with the same code path. Messages
    are persisted with modality="text".
    """
    # Chat path doesn't call STT or TTS, so no `sarvam` local alias needed;
    # _ANSWERER / _ELIGIBILITY already hold the singleton client internally.
    rag = _RAG
    answerer = _ANSWERER
    eligibility = _ELIGIBILITY

    pipeline_start = time.perf_counter()
    message_id = uuid.uuid4().hex

    try:
        conv = await conversation_service.get_or_create(conversation_id)
        canonical_conv_id = str(conv.id)
    except Exception as e:
        log.warning("conversation_create_failed", error=str(e))
        canonical_conv_id = conversation_id

    transcript_hi = (text or "").strip()

    # RAG
    rag_start = time.perf_counter()
    retrieved_chunks = await rag.retrieve(transcript_hi, top_k=5)
    rag_ms = _ms_since(rag_start)

    # Run answer + eligibility in parallel — both depend only on
    # retrieved_chunks. Saves 5-15s per query (eligibility LLM call no
    # longer waits for the answer LLM call). If retrieval is empty the
    # eligibility task no-ops; if answer ends up refused, eligibility
    # results are still computed but discarded — acceptable cost.
    par_start = time.perf_counter()
    known_names = await _all_known_scheme_names()

    async def _do_answer():
        a_start = time.perf_counter()
        a = await answerer.answer(
            transcript_hi, retrieved_chunks, all_known_scheme_names=known_names
        )
        return a, _ms_since(a_start)

    async def _do_eligibility():
        if not retrieved_chunks:
            return [], None, 0
        e_start = time.perf_counter()
        try:
            results, follow_up, _ = await eligibility.check(
                transcript_hi, retrieved_chunks
            )
            return (
                [r.to_dict() for r in results],
                follow_up,
                _ms_since(e_start),
            )
        except Exception as e:
            log.warning("eligibility_check_failed", error=str(e))
            return [], None, _ms_since(e_start)

    (answer, llm_ms), (eligibility_results, follow_up_question_hi, elig_ms) = (
        await asyncio.gather(_do_answer(), _do_eligibility())
    )
    response_text_hi = answer.response_text_hi
    top_schemes = answer.top_schemes
    sources = answer.sources
    confidence = answer.confidence
    # If the answer refused, drop the eligibility results — they're noise.
    if answer.refused:
        eligibility_results = []
        follow_up_question_hi = None
    par_wall_ms = _ms_since(par_start)

    total_ms = _ms_since(pipeline_start)

    log.info(
        "chat_parallel_done",
        llm_ms=llm_ms,
        elig_ms=elig_ms,
        wall_ms=par_wall_ms,
        saved_ms=(llm_ms + elig_ms) - par_wall_ms,
    )
    log.info(
        "chat_pipeline_done",
        conversation_id=canonical_conv_id,
        message_id=message_id,
        rag_ms=rag_ms,
        llm_ms=llm_ms,
        elig_ms=elig_ms,
        total_ms=total_ms,
        transcript_chars=len(transcript_hi),
        retrieved=len(retrieved_chunks),
        refused=answer.refused,
        confidence=confidence,
        eligibility_n=len(eligibility_results),
    )

    await _persist_telemetry(
        {
            "modality": "text",
            "conversation_id": canonical_conv_id,
            "message_id": message_id,
            "rag_ms": rag_ms,
            "llm_ms": llm_ms,
            "elig_ms": elig_ms,
            "total_ms": total_ms,
            "transcript_chars": len(transcript_hi),
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

    top_3_envelope = []
    for s in top_schemes[:3]:
        corpus = scheme_corpus.get_scheme(s["scheme_id"]) or {}
        top_3_envelope.append(
            {
                "scheme_id": s["scheme_id"],
                "name_hi": s["name_hi"],
                "name_en": s["name_en"],
                "summary_hi": corpus.get("summary_hi", ""),
                "ministry": corpus.get("ministry"),
                "tags": corpus.get("tags", []),
                "one_line_pitch_hi": corpus.get("summary_hi", ""),
                "benefit_amount_inr": None,
                "effort": "low",
                "source_url": s["source_url"],
                "match_confidence": s["match_confidence"],
            }
        )

    persisted_message_id = message_id
    try:
        await conversation_service.append_message(
            canonical_conv_id,
            role="user",
            modality="text",
            content_text=transcript_hi,
        )
        assistant_msg = await conversation_service.append_message(
            canonical_conv_id,
            role="assistant",
            modality="text",
            content_text=response_text_hi,
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
        "response_audio_url": "",
        "top_3_schemes": top_3_envelope,
        "eligibility_results": eligibility_results,
        "follow_up_question_hi": follow_up_question_hi,
        "confidence": confidence,
        "sources": sources,
        "explanations": explanations,
        "conversation_id": canonical_conv_id,
        "message_id": persisted_message_id,
    }
