import json
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, Query

from clients.sarvam_client import SarvamClient
from models import SchemeExplainCache, SchemeMeta
from models.db import SessionLocal

log = structlog.get_logger()
router = APIRouter(tags=["schemes"])

CORPUS_DIR = Path(__file__).resolve().parents[3] / "scheme-corpus" / "schemes" / "processed"
STATIC_AUDIO_DIR = Path(__file__).resolve().parents[2] / "static" / "audio"
STATIC_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _load_scheme_json(scheme_id: str) -> dict | None:
    path = CORPUS_DIR / f"{scheme_id}.json"
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: str):
    """Top-level scheme metadata. Pull from schemes_meta if present, else
    fall back to the source JSON corpus."""
    if SessionLocal is not None:
        async with SessionLocal() as session:
            row = await session.get(SchemeMeta, scheme_id)
            if row is not None:
                return {
                    "scheme_id": row.scheme_id,
                    "name": row.name,
                    "ministry": row.ministry,
                    "summary": row.summary,
                    "source_url": row.source_url,
                    "tags": row.tags or [],
                }
    data = _load_scheme_json(scheme_id)
    if data is None:
        raise HTTPException(404, detail=f"scheme '{scheme_id}' not found")
    return {
        "scheme_id": data["scheme_id"],
        "name": data["name_en"],
        "ministry": data.get("ministry"),
        "summary": data.get("summary_hi"),
        "source_url": data.get("source_url"),
        "tags": data.get("tags", []),
    }


@router.get("/schemes/{scheme_id}/explain")
async def explain_scheme(
    scheme_id: str,
    length: str = Query("medium", pattern="^(short|medium|long)$"),
):
    """Return a Hindi explanation at the requested length. Cached by
    (scheme_id, length) so repeat requests skip the LLM + TTS cost.
    """
    if SessionLocal is not None:
        async with SessionLocal() as session:
            row = await session.get(SchemeExplainCache, (scheme_id, length))
            if row is not None:
                return {
                    "scheme_id": scheme_id,
                    "length": length,
                    "explanation_text_hi": row.explanation_text_hi,
                    "explanation_audio_url": row.explanation_audio_url,
                    "cached": True,
                }

    data = _load_scheme_json(scheme_id)
    if data is None:
        raise HTTPException(404, detail=f"scheme '{scheme_id}' not found")

    target_sentences = {"short": 2, "medium": 4, "long": 8}[length]
    summary_chunks = [c for c in data["chunks"] if c.get("chunk_type") == "summary"]
    benefit_chunks = [c for c in data["chunks"] if c.get("chunk_type") == "benefits"]
    apply_chunks = [c for c in data["chunks"] if c.get("chunk_type") == "application_process"]
    chunks_for_prompt = (summary_chunks + benefit_chunks + apply_chunks)[:4]
    context = "\n---\n".join(c["text"] for c in chunks_for_prompt) or data.get(
        "summary_hi", ""
    )

    system = (
        "Aap Sarkari Saathi hain. Niche di gayi scheme ki detail ke aadhaar par "
        f"{target_sentences} sentence ki Hindi-Roman mein saaf, samjhaane wali explanation "
        "do. Apni training se yaad rakhi detail mat use karein - sirf niche likha "
        "context use karein. Numerical figures aur source bilkul wahi rakhein."
    )
    prompt = f"Scheme: {data['name_en']}\nContext:\n{context}\n\nAb {length} length ki explanation dein."

    sarvam = SarvamClient()
    try:
        explanation_text_hi = await sarvam.generate(prompt=prompt, system_prompt=system)
    except Exception as e:
        log.error("explain_generate_failed", scheme_id=scheme_id, error=str(e))
        explanation_text_hi = data.get("summary_hi", "")

    audio_url: str | None = None
    try:
        audio_bytes = await sarvam.synthesize(explanation_text_hi, voice="anushka")
        fname = f"explain-{scheme_id}-{length}-{uuid.uuid4().hex[:8]}.mp3"
        (STATIC_AUDIO_DIR / fname).write_bytes(audio_bytes)
        audio_url = f"/static/audio/{fname}"
    except Exception as e:
        log.warning("explain_tts_failed", scheme_id=scheme_id, error=str(e))

    if SessionLocal is not None:
        try:
            async with SessionLocal() as session:
                cached = SchemeExplainCache(
                    scheme_id=scheme_id,
                    length=length,
                    explanation_text_hi=explanation_text_hi,
                    explanation_audio_url=audio_url,
                )
                await session.merge(cached)
                await session.commit()
        except Exception as e:
            log.warning("explain_cache_write_failed", error=str(e))

    return {
        "scheme_id": scheme_id,
        "length": length,
        "explanation_text_hi": explanation_text_hi,
        "explanation_audio_url": audio_url,
        "cached": False,
    }


@router.get("/schemes/{scheme_id}/apply-steps")
async def apply_steps(scheme_id: str):
    """5-step structured application guide.

    Derived from the application_process + documents_required chunks in the
    corpus JSON. Returns a fixed 5-slot shape so the frontend can render
    consistent step cards.
    """
    data = _load_scheme_json(scheme_id)
    if data is None:
        raise HTTPException(404, detail=f"scheme '{scheme_id}' not found")

    chunks_by_type = {c.get("chunk_type"): c for c in data["chunks"]}

    def _chunk_text(name: str) -> str:
        c = chunks_by_type.get(name)
        return c["text"] if c else ""

    steps = [
        {
            "step_number": 1,
            "title_hi": "Patrata jaanchein",
            "title_en": "Check eligibility",
            "body_hi": _chunk_text("eligibility"),
        },
        {
            "step_number": 2,
            "title_hi": "Kagazaat taiyar karein",
            "title_en": "Gather documents",
            "body_hi": _chunk_text("documents_required"),
        },
        {
            "step_number": 3,
            "title_hi": "Form bharein / register karein",
            "title_en": "Register or fill the form",
            "body_hi": _chunk_text("application_process"),
        },
        {
            "step_number": 4,
            "title_hi": "Status track karein",
            "title_en": "Track status",
            "body_hi": _chunk_text("status_tracking") or _chunk_text("ekyc_requirement"),
        },
        {
            "step_number": 5,
            "title_hi": "Madad / Helpline",
            "title_en": "Helpline",
            "body_hi": _chunk_text("helpline"),
        },
    ]

    return {
        "scheme_id": scheme_id,
        "name_en": data["name_en"],
        "name_hi": data["name_hi"],
        "source_url": data.get("source_url"),
        "steps": steps,
    }
