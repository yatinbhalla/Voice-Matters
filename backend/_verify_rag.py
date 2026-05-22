"""End-to-end verification for the Prompt 6 brief.

Four cases (matches the brief verbatim):
  1) Ingest count -- Pinecone vector count and schemes_meta rows.
  2) Sushila script -> real Sukanya match with source URL.
  3) Fake scheme name -> refusal with helpline 14434.
  4) Hallucination guard at HIGH Sarvam temperature -- real LLM call,
     verify either model stays grounded OR guard appends the warning.
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import text  # noqa: E402

from clients.pinecone_client import PineconeClient  # noqa: E402
from clients.sarvam_client import SarvamClient  # noqa: E402
from models.db import SessionLocal  # noqa: E402
from prompts.system_prompts import RAG_ANSWER_SYSTEM_HI  # noqa: E402
from services.answer_service import (  # noqa: E402
    HALLUCINATION_SUFFIX_HI,
    _hallucination_guard,
)
from services.rag_service import Chunk, RAGService  # noqa: E402
from services.voice_pipeline import _all_known_scheme_names  # noqa: E402

OUT: dict = {}


async def case0_ingest() -> None:
    pc = PineconeClient()
    stats = await pc.index_stats()
    vec_count = stats.get("total_vector_count")
    rows: list[dict] = []
    if SessionLocal is not None:
        async with SessionLocal() as session:
            result = await session.execute(
                text("SELECT scheme_id, name FROM schemes_meta ORDER BY scheme_id")
            )
            rows = [dict(r._mapping) for r in result.fetchall()]
    OUT["case0_ingest"] = {
        "pinecone_vectors": vec_count,
        "schemes_meta_rows": [r["scheme_id"] for r in rows],
        "expected_schemes": ["apy", "e-shram", "pm-kisan", "pmjay", "sukanya-samriddhi-yojana"],
    }


async def case1_sushila() -> None:
    from services.answer_service import AnswerService

    rag = RAGService()
    answerer = AnswerService()
    transcript = "Meri beti ke liye sabse achi saving scheme kaun si hai?"
    chunks = await rag.retrieve(transcript, top_k=5)
    known = await _all_known_scheme_names()
    answer = await answerer.answer(transcript, chunks, all_known_scheme_names=known)
    OUT["case1_sushila"] = {
        "query": transcript,
        "matched_scheme_ids": [c.scheme_id for c in chunks],
        "top_score": round(chunks[0].score, 3) if chunks else None,
        "response_text_hi": answer.response_text_hi,
        "sources": [s["url"] for s in answer.sources],
        "passes": (
            bool(chunks)
            and chunks[0].scheme_id == "sukanya-samriddhi-yojana"
            and any("india.gov.in/spotlight/sukanya" in s["url"] for s in answer.sources)
        ),
    }


async def case2_fake_scheme() -> None:
    from services.answer_service import AnswerService

    rag = RAGService()
    answerer = AnswerService()
    transcript = "Pradhan Mantri Chamakte Sitare Yojana ke baare mein bataiye"
    chunks = await rag.retrieve(transcript, top_k=5)
    known = await _all_known_scheme_names()
    answer = await answerer.answer(transcript, chunks, all_known_scheme_names=known)
    contains_helpline = "14434" in answer.response_text_hi
    looks_like_refusal = any(
        tok in answer.response_text_hi.lower()
        for tok in ("pakka jaankari nahin", "koi jaankari nahi", "nahin hai", "nahi hai")
    )
    OUT["case2_fake_scheme"] = {
        "query": transcript,
        "n_passing_chunks": len(chunks),
        "response_text_hi": answer.response_text_hi,
        "contains_14434": contains_helpline,
        "looks_like_refusal": looks_like_refusal,
        "passes": contains_helpline and looks_like_refusal,
    }


async def case3_high_temp_guard() -> None:
    """Provide ONLY Sukanya chunks. Ask a broad question that might tempt
    the model to mention other schemes. Run Sarvam at temperature=1.0
    (high) and check: response either stays inside Sukanya, OR the guard
    appended the warning. Both outcomes pass."""
    only_sukanya = [
        Chunk(
            id="sukanya-samriddhi-yojana::ssy-summary",
            score=0.90,
            scheme_id="sukanya-samriddhi-yojana",
            scheme_name_hi="सुकन्या समृद्धि योजना",
            scheme_name_en="Sukanya Samriddhi Yojana",
            chunk_type="summary",
            source_url="https://www.india.gov.in/spotlight/sukanya-samriddhi-yojana",
            text=(
                "Sukanya Samriddhi Yojana (SSY) is a small-savings scheme for a "
                "girl child below age 10. 8.2% interest, tax-free under 80C. "
                "Account matures 21 years from opening. Minimum 250, maximum "
                "1.5 lakh per year. Open at post office or authorised bank."
            ),
        )
    ]

    # Build the same RAG_ANSWER prompt the live pipeline would build, then
    # call Sarvam directly at temperature=1.0 so we exercise the high-temp path.
    chunk_block = (
        f"---\nScheme: {only_sukanya[0].scheme_name_en} ({only_sukanya[0].scheme_id})\n"
        f"Section: {only_sukanya[0].chunk_type}\nSource: {only_sukanya[0].source_url}\n"
        f"{only_sukanya[0].text}\n"
    )
    transcript = (
        "Mere paas kuch paisa hai, kis sarkari scheme mein invest karoon? "
        "Kya saari saving schemes ke options bata sakte ho?"
    )
    user_prompt = (
        f"USER QUERY (Hindi/Devanagari):\n{transcript}\n\n"
        f"RETRIEVED CONTEXT (only use this — nothing else):\n{chunk_block}\n\n"
        "Ab user ki query ka jawab Hindi-Roman mein, format ke hisaab se, "
        "sirf upar diye context se dein."
    )

    sarvam = SarvamClient()
    raw = await sarvam.generate(
        prompt=user_prompt,
        system_prompt=RAG_ANSWER_SYSTEM_HI,
        temperature=1.0,
    )

    known = await _all_known_scheme_names()
    guarded = _hallucination_guard(raw, only_sukanya, known)

    other_scheme_aliases = ("pm-kisan", "pmjay", "pm-jay", "e-shram", "apy", "ayushman")
    lower_raw = raw.lower()
    lower_guarded = guarded.lower()
    leaked = [a for a in other_scheme_aliases if a in lower_raw]
    suffix_present = HALLUCINATION_SUFFIX_HI.strip() in guarded

    OUT["case3_high_temp_guard"] = {
        "temperature": 1.0,
        "transcript": transcript,
        "raw_llm_response": raw,
        "leaked_aliases": leaked,
        "guard_suffix_appended": suffix_present,
        # Pass conditions: no leakage (model stayed grounded) OR guard
        # appended the warning when leakage occurred.
        "passes": (not leaked) or suffix_present,
        "guarded_response": guarded,
        "final_lower_contains_leak_without_warning": bool(leaked) and not suffix_present,
        # sanity: if no other scheme leaks, also no warning should be appended
        "no_false_positive": (not leaked) and (not suffix_present)
        if not leaked
        else True,
        "raw_response_lowercased": lower_guarded[:200],
    }


async def main() -> None:
    await case0_ingest()
    await case1_sushila()
    await case2_fake_scheme()
    await case3_high_temp_guard()
    Path("verify_rag.json").write_text(
        json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Pass/fail roll-up for terminal
    print("\n=== VERIFY SUMMARY ===")
    passed = True
    for case_name, payload in OUT.items():
        if case_name == "case0_ingest":
            ok = (
                payload["pinecone_vectors"]
                and set(payload["schemes_meta_rows"]) == set(payload["expected_schemes"])
            )
        else:
            ok = bool(payload.get("passes"))
        passed = passed and ok
        print(f"  {case_name}: {'PASS' if ok else 'FAIL'}")
    print(f"OVERALL: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
