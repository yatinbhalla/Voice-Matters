"""Answer service: build a grounded Hindi answer from retrieved chunks.

Refusal path: if there are no retrieved chunks, return the canonical
"don't know, call 14434" reply rather than guessing.

Hallucination guard: after the LLM response, check that any scheme name
mentioned is among the retrieved scheme set. If we detect a *different*
scheme name that we have in our database but didn't retrieve for this
query, append a confirmation hint pointing to the helpline.
"""
import re
from dataclasses import dataclass

import structlog

from clients.openai_client import EMBED_PROVIDER
from clients.sarvam_client import SarvamClient
from prompts.system_prompts import RAG_ANSWER_SYSTEM_HI
from services.rag_service import Chunk

# Confidence bands are likewise embedder-dependent. Tuned for our code-mixed
# corpus where OpenAI tops out around 0.50 even on strong matches.
if EMBED_PROVIDER == "openai":
    _HIGH_BAND, _MED_BAND = 0.55, 0.45
else:
    _HIGH_BAND, _MED_BAND = 0.55, 0.40

log = structlog.get_logger()

REFUSAL_HI = (
    "अच्छा, समझा — आप इस योजना के बारे में पूछ रहे हैं।\n"
    "जैसे आपने कहा, इसके बारे में मुझे पक्की जानकारी नहीं है — "
    "ग़लत बात बताने से बेहतर है कि आप सही जगह से पुष्टि कर लें।\n"
    "सही जानकारी के लिए सरकारी हेल्पलाइन और सरकारी पोर्टल ही सबसे अच्छी जगह है।\n"
    "हेल्पलाइन 14434 पर बात कीजिए — 11 भाषाओं में मदद मिलती है। "
    "या अपने नज़दीकी सेवा केंद्र (CSC) में जाकर पूछ लीजिए।"
)

HALLUCINATION_SUFFIX_HI = (
    " Yeh jaankari purani ho sakti hai - helpline par confirm kariye."
)

# Hard substitution layer: even with prompt rules, Sarvam-m occasionally
# leaks these English tokens. Belt-and-suspenders sanitizer maps them to
# the Hindi equivalents the brief specified (process->kaam, etc).
_JARGON_SUBS = [
    (re.compile(r"\bprocess\b", re.IGNORECASE), "kaam"),
    (re.compile(r"\bverification\b", re.IGNORECASE), "jaanch"),
    (re.compile(r"\bdocumentation\b", re.IGNORECASE), "kaagaz"),
    (re.compile(r"\bprocedure\b", re.IGNORECASE), "tareeqa"),
    (re.compile(r"\bpremium\b", re.IGNORECASE), "kisht"),
    (re.compile(r"\bmaturity\b", re.IGNORECASE), "paisa wapas milne ka samay"),
]


def _sanitize_jargon(text: str) -> str:
    if not text:
        return text
    for pat, replacement in _JARGON_SUBS:
        text = pat.sub(replacement, text)
    return text


@dataclass
class Answer:
    response_text_hi: str
    confidence: str  # "high" | "medium" | "low"
    top_schemes: list[dict]  # deduped by scheme_id, ordered by best score
    sources: list[dict]
    refused: bool


def _dedupe_schemes(chunks: list[Chunk]) -> list[dict]:
    seen: dict[str, dict] = {}
    for c in chunks:
        if c.scheme_id in seen:
            continue
        seen[c.scheme_id] = {
            "scheme_id": c.scheme_id,
            "name_hi": c.scheme_name_hi,
            "name_en": c.scheme_name_en,
            "source_url": c.source_url,
            "match_confidence": c.score,
        }
    return list(seen.values())


def _confidence_from(chunks: list[Chunk]) -> str:
    if not chunks:
        return "low"
    top = chunks[0].score
    if top >= _HIGH_BAND:
        return "high"
    if top >= _MED_BAND:
        return "medium"
    return "low"


def _build_user_prompt(transcript: str, chunks: list[Chunk]) -> str:
    blocks = []
    for c in chunks:
        blocks.append(
            f"---\n"
            f"Scheme: {c.scheme_name_en} ({c.scheme_id})\n"
            f"Section: {c.chunk_type}\n"
            f"Source: {c.source_url}\n"
            f"{c.text}\n"
        )
    context = "\n".join(blocks) if blocks else "(no chunks)"
    # IMPORTANT: this prompt previously said "Hindi-Roman mein" — the
    # legacy phrasing from when the whole response path was transliterated
    # Hindi. The system prompt was later switched to Devanagari output, but
    # this user-side instruction wasn't updated. The conflict ("system: use
    # Devanagari" vs "user: use Hindi-Roman") confused Sarvam-m enough that
    # it defaulted to the safer fake_scheme refusal template instead of
    # producing an answer. The system prompt already covers script + format
    # rules; this prompt only needs to feed the data + a short instruction.
    return (
        f"USER QUERY (Devanagari Hindi):\n{transcript}\n\n"
        f"RETRIEVED CONTEXT (use ONLY this, nothing else):\n{context}\n\n"
        f"Ab is context se user ki query ka jawab Devanagari Hindi mein, "
        f"system prompt ke 4-part format mein dein. Refuse mat karein — "
        f"upar diya context aapke paas hai."
    )


class AnswerService:
    def __init__(self, sarvam: SarvamClient | None = None) -> None:
        self.sarvam = sarvam or SarvamClient()

    async def answer(
        self,
        transcript: str,
        retrieved_chunks: list[Chunk],
        all_known_scheme_names: list[tuple[str, str]] | None = None,
    ) -> Answer:
        if not retrieved_chunks:
            return Answer(
                response_text_hi=REFUSAL_HI,
                confidence="low",
                top_schemes=[],
                sources=[],
                refused=True,
            )

        top_schemes = _dedupe_schemes(retrieved_chunks)
        sources = [
            {
                "title": s["name_en"],
                "url": s["source_url"],
                "scheme_id": s["scheme_id"],
            }
            for s in top_schemes
        ]

        prompt = _build_user_prompt(transcript, retrieved_chunks)
        try:
            llm_text = await self.sarvam.generate(
                prompt=prompt,
                system_prompt=RAG_ANSWER_SYSTEM_HI,
            )
        except Exception as e:
            log.error("llm_failed_fallback_refusal", error=str(e))
            return Answer(
                response_text_hi=REFUSAL_HI,
                confidence="low",
                top_schemes=top_schemes,
                sources=sources,
                refused=True,
            )

        sanitized = _sanitize_jargon(llm_text)
        guarded = _hallucination_guard(
            sanitized,
            retrieved_chunks,
            all_known_scheme_names or [],
        )
        return Answer(
            response_text_hi=guarded,
            confidence=_confidence_from(retrieved_chunks),
            top_schemes=top_schemes,
            sources=sources,
            refused=False,
        )


def _aliases_for(scheme_id: str, name_en: str) -> list[str]:
    """Distinctive surface forms used to detect mentions in free text.

    Includes the scheme_id token (pm-kisan, pmjay, e-shram, apy, ...), the
    full English name, and any parenthetical abbreviation in the name
    (e.g. "(PM-JAY)", "(APY)").
    """
    out = {scheme_id, scheme_id.replace("-", " "), scheme_id.replace("-", "")}
    if name_en:
        out.add(name_en)
        # Parenthetical short form (e.g. "Atal Pension Yojana (APY)")
        import re as _re

        for m in _re.findall(r"\(([^)]+)\)", name_en):
            out.add(m.strip())
        # Hyphenated leading token (e.g. "PM-KISAN" or "PM-JAY")
        for token in _re.split(r"\s+", name_en):
            if "-" in token and len(token) >= 3:
                out.add(token.strip("-,.:;"))
    return [a.lower() for a in out if a and len(a) >= 3]


def _hallucination_guard(
    response_text: str,
    retrieved_chunks: list[Chunk],
    all_known_scheme_names: list[tuple[str, str]],
) -> str:
    """If the response mentions a scheme we know about but did NOT retrieve
    for this query, append the "purani ho sakti hai" suffix.

    We don't try to delete sentences — too risky in Hindi-Roman — but we
    flag the response so the user knows to verify with the helpline.
    """
    if not response_text:
        return response_text

    retrieved_ids = {c.scheme_id for c in retrieved_chunks}
    retrieved_aliases: set[str] = set()
    for c in retrieved_chunks:
        for alias in _aliases_for(c.scheme_id, c.scheme_name_en):
            retrieved_aliases.add(alias)

    lower = response_text.lower()
    flagged: list[str] = []
    for scheme_id, name in all_known_scheme_names:
        if scheme_id in retrieved_ids:
            continue
        for alias in _aliases_for(scheme_id, name):
            if alias in retrieved_aliases:
                continue
            # Require word-ish boundary so "apy" doesn't match "happy".
            import re as _re

            if _re.search(rf"(?<![a-z0-9]){_re.escape(alias)}(?![a-z0-9])", lower):
                flagged.append(f"{scheme_id} (via '{alias}')")
                break

    if flagged:
        log.warning(
            "hallucination_guard_flagged",
            unretrieved_schemes_in_response=flagged,
        )
        if HALLUCINATION_SUFFIX_HI.strip() not in response_text:
            return response_text.rstrip() + HALLUCINATION_SUFFIX_HI

    return response_text
