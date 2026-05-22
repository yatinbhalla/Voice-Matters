"""Drive the verify cases for Prompt 6 (RAG + answer + hallucination guard).

Cases:
  1) Sushila query (beti ke liye saving scheme) -> Sukanya match with source.
  2) Fake scheme query -> refusal with helpline 14434.
  3) High-temp generation -> hallucination guard appends warning when LLM
     mentions a known scheme that wasn't retrieved.
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from clients.sarvam_client import SarvamClient  # noqa: E402
from services.answer_service import AnswerService, _hallucination_guard  # noqa: E402
from services.rag_service import Chunk, RAGService  # noqa: E402
from services.voice_pipeline import _all_known_scheme_names  # noqa: E402

OUT = {}


async def case1_sushila() -> None:
    rag = RAGService()
    answerer = AnswerService()
    transcript = "Meri beti ke liye sabse achi saving scheme kaun si hai?"
    chunks = await rag.retrieve(transcript, top_k=5)  # uses DEFAULT_MIN_SCORE
    known = await _all_known_scheme_names()
    answer = await answerer.answer(transcript, chunks, all_known_scheme_names=known)
    OUT["case1"] = {
        "query": transcript,
        "top_chunks": [
            {"id": c.id, "score": round(c.score, 3), "scheme_id": c.scheme_id}
            for c in chunks
        ],
        "response_text_hi": answer.response_text_hi,
        "top_schemes": [s["scheme_id"] for s in answer.top_schemes],
        "sources": [s["url"] for s in answer.sources],
        "confidence": answer.confidence,
        "refused": answer.refused,
    }


async def case2_fake_scheme() -> None:
    rag = RAGService()
    answerer = AnswerService()
    transcript = "Pradhan Mantri Chamakte Sitare Yojana ke baare mein bataiye"
    chunks = await rag.retrieve(transcript, top_k=5)  # uses DEFAULT_MIN_SCORE
    known = await _all_known_scheme_names()
    answer = await answerer.answer(transcript, chunks, all_known_scheme_names=known)
    OUT["case2"] = {
        "query": transcript,
        "n_chunks_passing_threshold": len(chunks),
        "response_text_hi": answer.response_text_hi,
        "refused": answer.refused,
        "contains_14434": "14434" in answer.response_text_hi,
    }


async def case3_hallucination_guard() -> None:
    """Direct test of the guard: feed it a response that mentions a known
    scheme name that was NOT among the retrieved chunks, confirm the warning
    suffix is appended.
    """
    retrieved = [
        Chunk(
            id="ssy-summary",
            score=0.92,
            scheme_id="sukanya-samriddhi-yojana",
            scheme_name_hi="सुकन्या समृद्धि योजना",
            scheme_name_en="Sukanya Samriddhi Yojana",
            chunk_type="summary",
            source_url="https://www.india.gov.in/spotlight/sukanya-samriddhi-yojana",
            text="Sukanya Samriddhi Yojana for girl child savings...",
        )
    ]
    known = await _all_known_scheme_names()
    fake_llm_text = (
        "Sukanya Samriddhi Yojana aapki beti ke liye sabse achi hai - 8.2% byaaj. "
        "Aap PM-KISAN bhi consider kar sakte hain agar aap kisaan hain."
    )
    guarded = _hallucination_guard(fake_llm_text, retrieved, known)
    OUT["case3"] = {
        "input_text": fake_llm_text,
        "retrieved_scheme_ids": [c.scheme_id for c in retrieved],
        "known_scheme_count": len(known),
        "guarded_text": guarded,
        "suffix_appended": "purani ho sakti hai" in guarded,
    }


async def main() -> None:
    await case1_sushila()
    await case2_fake_scheme()
    await case3_hallucination_guard()
    Path("verify_rag.json").write_text(json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote verify_rag.json")


if __name__ == "__main__":
    asyncio.run(main())
