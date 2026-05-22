"""Verify the Prompt 7 eligibility checker end-to-end.

Cases:
  1) Rich transcript (Sushila with a few facts) -> some ELIGIBLE,
     others NEED_MORE_INFO, none falsely ELIGIBLE.
  2) Ambiguous transcript -> ALL NEED_MORE_INFO; follow_up_question_hi
     is non-null. False-positive guard validated.
  3) Direct rule evaluation (no LLM): hand-built facts where one rule
     violates -> NOT_ELIGIBLE.
  4) Direct rule evaluation: facts that satisfy a verification-required
     scheme -> still NEED_MORE_INFO (PMJAY/PM-KISAN/SSY external verify).
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from data import scheme_corpus  # noqa: E402
from services.eligibility_service import (  # noqa: E402
    STATUS_ELIGIBLE,
    STATUS_NEED_MORE_INFO,
    STATUS_NOT_ELIGIBLE,
    EligibilityService,
    UserFacts,
    evaluate,
)
from services.rag_service import Chunk  # noqa: E402

OUT: dict = {}


def _make_chunks_for(scheme_ids: list[str]) -> list[Chunk]:
    """Fake retrieval -- we want to drive the eligibility check directly
    for a known scheme set, independent of vector search behaviour."""
    chunks = []
    for sid in scheme_ids:
        s = scheme_corpus.get_scheme(sid)
        if not s:
            continue
        chunks.append(
            Chunk(
                id=f"{sid}::test",
                score=0.9,
                scheme_id=sid,
                scheme_name_hi=s["name_hi"],
                scheme_name_en=s["name_en"],
                chunk_type="summary",
                source_url=s["source_url"],
                text=s.get("summary_hi", ""),
            )
        )
    return chunks


async def case1_rich_transcript() -> None:
    """Sushila profile: woman, 35, has Aadhaar + bank, low income. No
    occupation as kisan and no daughter-under-10 stated."""
    transcript = (
        "Mera naam Sushila hai, main 35 saal ki hoon, ghar pe rehti hoon. "
        "Mere paas Aadhaar card hai aur bank khaata bhi hai. "
        "Mahine ki aamdani lagbhag 8000 rupaye hai. Hum 5 log hain parivar mein."
    )
    chunks = _make_chunks_for(["apy", "e-shram", "pm-kisan", "pmjay", "sukanya-samriddhi-yojana"])
    svc = EligibilityService()
    results, follow_up, facts = await svc.check(transcript, chunks)
    OUT["case1_rich_transcript"] = {
        "transcript": transcript,
        "facts_extracted": facts.to_dict(),
        "results": [r.to_dict() for r in results],
        "follow_up_question_hi": follow_up,
        "no_unsafe_eligible": all(
            r.status != STATUS_ELIGIBLE
            or scheme_corpus.eligibility_rules(r.scheme_id).get(
                "requires_external_verification"
            )
            is False
            for r in results
        ),
        "statuses": [r.status for r in results],
    }


async def case2_ambiguous_transcript() -> None:
    transcript = "Mujhe kuch scheme batao"
    chunks = _make_chunks_for(["apy", "e-shram", "pm-kisan"])
    svc = EligibilityService()
    results, follow_up, facts = await svc.check(transcript, chunks)
    all_unknown_eligible = all(r.status == STATUS_NEED_MORE_INFO for r in results)
    OUT["case2_ambiguous_transcript"] = {
        "transcript": transcript,
        "facts_extracted": facts.to_dict(),
        "results": [r.to_dict() for r in results],
        "follow_up_question_hi": follow_up,
        "all_need_more_info": all_unknown_eligible,
        "follow_up_present": bool(follow_up),
        "passes": all_unknown_eligible and bool(follow_up),
    }


def case3_violation_direct() -> None:
    """Direct evaluator test: a 65-year-old can't enrol in APY (max age 40)."""
    facts = UserFacts(
        age=65,
        has_aadhaar=True,
        has_bank_account=True,
    )
    result = evaluate(facts, scheme_corpus.get_scheme("apy"))
    OUT["case3_violation_direct"] = {
        "facts": facts.to_dict(),
        "result": result.to_dict(),
        "passes": result.status == STATUS_NOT_ELIGIBLE,
    }


def case4_verification_required() -> None:
    """All deterministic rules pass for PMJAY, but it still needs SECC
    verification -> NEED_MORE_INFO, never ELIGIBLE."""
    facts = UserFacts(
        has_aadhaar=True,
        income_monthly_inr=8000,
    )
    result = evaluate(facts, scheme_corpus.get_scheme("pmjay"))
    OUT["case4_verification_required"] = {
        "facts": facts.to_dict(),
        "result": result.to_dict(),
        "passes": result.status == STATUS_NEED_MORE_INFO,
    }


def case5_clean_eligible() -> None:
    """An APY rule-clean case (no external verification required) -> ELIGIBLE."""
    facts = UserFacts(
        age=30,
        has_aadhaar=True,
        has_bank_account=True,
    )
    result = evaluate(facts, scheme_corpus.get_scheme("apy"))
    OUT["case5_clean_eligible"] = {
        "facts": facts.to_dict(),
        "result": result.to_dict(),
        "passes": result.status == STATUS_ELIGIBLE,
    }


async def main() -> None:
    await case1_rich_transcript()
    await case2_ambiguous_transcript()
    case3_violation_direct()
    case4_verification_required()
    case5_clean_eligible()
    Path("verify_eligibility.json").write_text(
        json.dumps(OUT, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== ELIGIBILITY VERIFY ===")
    ok = True
    for name, payload in OUT.items():
        passed = bool(payload.get("passes")) or (
            name == "case1_rich_transcript" and payload.get("no_unsafe_eligible") is True
        )
        ok = ok and passed
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    # Critical guard: NO ELIGIBLE result for verification-required schemes.
    eligible_schemes = []
    for name, payload in OUT.items():
        results = payload.get("results")
        if not results:
            continue
        for r in results:
            if r["status"] == STATUS_ELIGIBLE:
                meta = scheme_corpus.eligibility_rules(r["scheme_id"])
                if meta.get("requires_external_verification"):
                    eligible_schemes.append(r["scheme_id"])
    if eligible_schemes:
        ok = False
        print(f"  CRITICAL: verification-required schemes returned ELIGIBLE: {eligible_schemes}")
    print(f"OVERALL: {'PASS' if ok else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
