import json
import re
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, HTTPException, Query

from clients.sarvam_client import SarvamClient
from models import SchemeExplainCache
from models.db import SessionLocal
from services.answer_service import _sanitize_jargon

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


def _parse_docs(text: str) -> list[str]:
    """Pull document names from "(1) X. (2) Y. (3) Z." style text.

    The frontend has a similar pattern, but we tolerate parentheses INSIDE
    the description (e.g. "(1) Aadhaar card (mandatory). (2) ...") by
    splitting on numbered markers instead of using a character-class regex
    that excludes parens.
    """
    if not text:
        return []
    parts = re.split(r"\((\d+)\)\s*", text)
    # parts = [pre, "1", "Aadhaar card (mandatory). ", "2", "Land ...", ...]
    out: list[str] = []
    for i in range(1, len(parts) - 1, 2):
        body = parts[i + 1] or ""
        # Take just the first sentence so the chip text stays short.
        first = re.split(r"\.\s|\.$", body, maxsplit=1)[0]
        first = first.strip().rstrip(",.;")
        if first:
            out.append(first)
        if len(out) >= 8:
            break
    return out


# Strip a leading "Benefits of X:" / "PM-JAY benefits:" label so the first
# benefit isn't just that label.
_BENEFIT_LABEL_RE = re.compile(r"^[^:]{4,80}benefits[^:]{0,40}:\s*", re.IGNORECASE)


def _split_into_benefits(text: str, limit: int = 3) -> list[dict]:
    """Split a 'benefits' chunk body into 1-`limit` items with head + sub.

    Each item is one sentence; we don't try to invent a sub-headline because
    that previously broke "₹6,000" on the comma. Keep head short with a
    soft 90-char cap.
    """
    if not text:
        return []
    text = _BENEFIT_LABEL_RE.sub("", text, count=1)
    pieces = [p.strip() for p in re.split(r"\.\s+|;\s+", text) if p.strip()]
    out: list[dict] = []
    for piece in pieces:
        if len(out) >= limit:
            break
        # Prefer an em-dash / en-dash / hyphenated split (e.g.
        # "Faayda: kam se kam 250 - 8.2% byaaj") - but only when the head
        # stays short. Otherwise keep the whole sentence as the head.
        clause_split = re.split(r"\s+[-—]\s+|:\s+", piece, maxsplit=1)
        if len(clause_split) == 2 and len(clause_split[0]) < 80:
            head, sub = clause_split[0], clause_split[1]
        else:
            head, sub = piece[:90].rstrip(),  piece[90:].strip()
        out.append({"head": head.strip(), "sub": sub.strip()})
    return out


def _category_label(data: dict) -> str:
    """Best-effort human label derived from tags + ministry."""
    tags = data.get("tags") or []
    primary = (tags[0] if tags else "").replace("-", " ").title()
    if not primary:
        primary = "Government Scheme"
    return f"{primary} · Central Govt"


def _scheme_response(data: dict) -> dict:
    chunks = data.get("chunks") or []
    chunks_by_type = {c.get("chunk_type"): c for c in chunks}

    benefits = _split_into_benefits((chunks_by_type.get("benefits") or {}).get("text", ""))
    documents_needed = _parse_docs(
        (chunks_by_type.get("documents_required") or {}).get("text", "")
    )

    rules = (data.get("eligibility_rules") or {}).get("rules", [])
    eligibility_rules = [
        {"field": r.get("field"), "text_hi": r.get("reason_hi", "")}
        for r in rules
        if r.get("reason_hi")
    ]

    source_url = data.get("source_url", "")
    return {
        # New richer surface
        "scheme_id": data["scheme_id"],
        "name_en": data["name_en"],
        "name_hi": data["name_hi"],
        "ministry": data.get("ministry"),
        "summary_hi": data.get("summary_hi"),
        "source_url": source_url,
        "source_urls": [source_url] if source_url else [],
        "helpline_phone": data.get("helpline_phone"),
        "tags": data.get("tags", []),
        "category_label": _category_label(data),
        "benefits": benefits,
        "eligibility_rules": eligibility_rules,
        "documents_needed": documents_needed,
        # Legacy short fields kept for backward compatibility
        "name": data["name_en"],
        "summary": data.get("summary_hi"),
    }


@router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: str):
    """Scheme metadata + structured fields the detail page needs.

    Corpus JSON under /scheme-corpus is the source of truth here; schemes_meta
    only holds the short-form Postgres copy and is missing the chunks /
    eligibility_rules / helpline. So we go to the JSON directly.
    """
    data = _load_scheme_json(scheme_id)
    if data is None:
        raise HTTPException(404, detail=f"scheme '{scheme_id}' not found")
    return _scheme_response(data)


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

    # For "short" we serve the curated summary_hi directly - no LLM call,
    # so no jargon contamination and no LLM-failure refusal. Medium/long
    # still expand via Sarvam-m for natural-language flow.
    if length == "short":
        explanation_text_hi = data.get("summary_hi") or ""
    else:
        system = (
            "Aap Sarkari Saathi hain. Niche di gayi scheme ki detail ke aadhaar par "
            f"{target_sentences} sentence ki saaf, samjhaane wali Hindi-Roman explanation do.\n"
            "STRICT RULES:\n"
            "1. Sirf niche diye context ka use karein. Apni training se yaad rakhi detail mat use karein.\n"
            "2. English jargon BILKUL MAT use karein. Yeh substitution karein:\n"
            "   process -> kaam | verification -> jaanch | documentation -> kaagaz\n"
            "   procedure -> tareeqa | premium -> kisht | maturity -> paisa wapas milne ka samay\n"
            "   eligibility -> patrata | beneficiary -> labharthi\n"
            "3. Sanskritised words mat use karein. Conversational Hindi-Roman mein likhein "
            "jaise ki ek dost se baat ho rahi ho.\n"
            "4. Numerical figures bilkul context jaisi rakhein.\n"
            "5. Section names jaise '80C' ya 'Section 8' wagairah short form mein likhein.\n"
        )
        prompt = f"Scheme: {data['name_en']}\nContext:\n{context}\n\nAb {length} length ki explanation dein."
        sarvam_for_text = SarvamClient()
        try:
            explanation_text_hi = await sarvam_for_text.generate(
                prompt=prompt, system_prompt=system
            )
        except Exception as e:
            log.error("explain_generate_failed", scheme_id=scheme_id, error=str(e))
            explanation_text_hi = data.get("summary_hi", "")

    # Belt-and-suspenders: enforce the substitution table even if the LLM
    # slipped (or if summary_hi happens to contain a jargon word).
    explanation_text_hi = _sanitize_jargon(explanation_text_hi)

    sarvam = SarvamClient()
    audio_url: str | None = None
    try:
        audio_bytes = await sarvam.synthesize(explanation_text_hi, voice="anushka")
        fname = f"explain-{scheme_id}-{length}-{uuid.uuid4().hex[:8]}.mp3"
        (STATIC_AUDIO_DIR / fname).write_bytes(audio_bytes)
        audio_url = f"/static/audio/{fname}"
    except Exception as e:
        log.warning("explain_tts_failed", scheme_id=scheme_id, error=str(e))

    # Only cache rows that HAVE a working audio URL - otherwise we'd serve
    # a null audio_url to the client forever and force browser-TTS fallback.
    if SessionLocal is not None and audio_url:
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
