"""10-case eligibility test set with known ground-truth answers.

Per the brief's verify requirements (Prompt 7):
  - 10 cases driven by transcripts the LLM must parse
  - Assert ZERO ELIGIBLE on negative ground truth (false-positive guard)
  - Assert correct follow_up_question when fields are missing

Each case is independent of vector search noise: we feed the EligibilityService
a fixed list of "retrieved" scheme_ids so the rule evaluator runs against a
known set. The LLM extractor's behaviour on each transcript is what the test
exercises end-to-end.

Run:
  cd backend
  .venv/Scripts/python.exe _verify_eligibility_10cases.py
"""
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from data import scheme_corpus  # noqa: E402
from services.eligibility_service import (  # noqa: E402
    STATUS_ELIGIBLE,
    EligibilityService,
)
from services.rag_service import Chunk  # noqa: E402


@dataclass
class Case:
    name: str
    transcript: str
    retrieved_scheme_ids: list[str]
    must_not_be_eligible: list[str]  # ground truth: none of these may return ELIGIBLE
    expects_follow_up: bool  # True if at least one required fact is missing
    follow_up_contains: list[str] | None = None  # substrings any of which should appear


CASES: list[Case] = [
    Case(
        name="01_completely_ambiguous",
        transcript="Mujhe scheme batao",
        retrieved_scheme_ids=["apy", "e-shram", "pm-kisan", "pmjay", "sukanya-samriddhi-yojana"],
        must_not_be_eligible=["apy", "e-shram", "pm-kisan", "pmjay", "sukanya-samriddhi-yojana"],
        expects_follow_up=True,
        follow_up_contains=["umar", "kheti", "Aadhaar", "khaata", "aamdani", "kya kaam"],
    ),
    Case(
        name="02_sushila_full_profile",
        # All facts present and self-consistent.
        transcript=(
            "Main Sushila hoon, 35 saal ki hoon, ghar par rehti hoon. "
            "Aadhaar card hai aur bank khaata bhi hai. "
            "Mahine ki aamdani lagbhag 8000 rupaye hai."
        ),
        retrieved_scheme_ids=["apy", "e-shram", "pm-kisan", "pmjay", "sukanya-samriddhi-yojana"],
        # PM-KISAN: housewife is not kisan -> NOT_ELIGIBLE
        # PMJAY: deterministic rules pass but verification needed -> NEED_MORE_INFO
        # SSY: verification needed (daughter) -> NEED_MORE_INFO
        # APY: should be ELIGIBLE; e-Shram: should be ELIGIBLE
        must_not_be_eligible=["pm-kisan", "pmjay", "sukanya-samriddhi-yojana"],
        expects_follow_up=False,  # rule-evaluable fields are all known
    ),
    Case(
        name="03_old_farmer_above_apy_age",
        transcript=(
            "Main 65 saal ka kisaan hoon, kheti karta hoon. "
            "Aadhaar card aur bank khaata hai. Income lagbhag 6000 mahine."
        ),
        retrieved_scheme_ids=["apy", "e-shram", "pm-kisan"],
        # APY: age > 40 -> NOT_ELIGIBLE
        # e-Shram: age > 59 -> NOT_ELIGIBLE
        # PM-KISAN: verification needed (land records) -> NEED_MORE_INFO
        must_not_be_eligible=["apy", "e-shram", "pm-kisan"],
        expects_follow_up=False,
    ),
    Case(
        name="04_no_aadhaar",
        transcript=(
            "Main 22 saal ka hoon, mere paas Aadhaar card nahi hai. "
            "Bank khaata bhi nahi hai."
        ),
        retrieved_scheme_ids=["apy", "e-shram", "pm-kisan"],
        # has_aadhaar=false breaks all three.
        must_not_be_eligible=["apy", "e-shram", "pm-kisan"],
        expects_follow_up=False,
    ),
    Case(
        name="05_government_employee_excluded",
        transcript=(
            "Main 40 saal ka government employee hoon. "
            "Aadhaar aur bank khaata hai. Mahine ki tankhwah 80000 hai."
        ),
        retrieved_scheme_ids=["e-shram", "pm-kisan", "pmjay"],
        # e-Shram: government in not_contains_any -> NOT_ELIGIBLE
        # PM-KISAN: occupation doesn't contain kisan -> NOT_ELIGIBLE (also gov filter would fire)
        # PMJAY: income > 25k -> NOT_ELIGIBLE
        must_not_be_eligible=["e-shram", "pm-kisan", "pmjay"],
        expects_follow_up=False,
    ),
    Case(
        name="06_apy_age_boundary_above",
        transcript="Main 41 saal ka hoon, Aadhaar aur bank khaata hai.",
        retrieved_scheme_ids=["apy"],
        # APY age cap is 40 -> NOT_ELIGIBLE
        must_not_be_eligible=["apy"],
        expects_follow_up=False,
    ),
    Case(
        name="07_apy_age_boundary_below",
        transcript="Main 17 saal ka hoon, Aadhaar aur bank khaata hai.",
        retrieved_scheme_ids=["apy"],
        # APY min age is 18 -> NOT_ELIGIBLE
        must_not_be_eligible=["apy"],
        expects_follow_up=False,
    ),
    Case(
        name="08_pmjay_low_income_needs_verification",
        transcript=(
            "Main 30 saal ki hoon. Mahine ki aamdani 7000 hai. Aadhaar card hai."
        ),
        retrieved_scheme_ids=["pmjay"],
        # All deterministic PMJAY rules pass; SECC verification still needed.
        must_not_be_eligible=["pmjay"],
        expects_follow_up=False,
    ),
    Case(
        name="09_high_income_violation",
        transcript=(
            "Main 30 saal ka hoon, mahine 1 lakh kamata hoon. "
            "Aadhaar aur bank khaata hai. Software engineer hoon."
        ),
        retrieved_scheme_ids=["pmjay", "pm-kisan"],
        # PMJAY: income > 25k -> NOT_ELIGIBLE
        # PM-KISAN: software engineer is not kisan -> NOT_ELIGIBLE
        must_not_be_eligible=["pmjay", "pm-kisan"],
        expects_follow_up=False,
    ),
    Case(
        name="10_kisan_with_facts_but_needs_verification",
        transcript=(
            "Main 35 saal ka kisaan hoon, kheti karta hoon apne khet par. "
            "Aadhaar card hai aur Aadhaar se juda bank khaata bhi hai."
        ),
        retrieved_scheme_ids=["pm-kisan"],
        # All deterministic rules pass; khasra/khatauni verification needed.
        must_not_be_eligible=["pm-kisan"],
        expects_follow_up=False,
    ),
]


def _make_chunks(scheme_ids: list[str]) -> list[Chunk]:
    out: list[Chunk] = []
    for sid in scheme_ids:
        s = scheme_corpus.get_scheme(sid)
        if not s:
            continue
        out.append(
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
    return out


async def run_case(svc: EligibilityService, case: Case) -> dict:
    chunks = _make_chunks(case.retrieved_scheme_ids)
    results, follow_up, facts = await svc.check(case.transcript, chunks)
    results_by_id = {r.scheme_id: r for r in results}

    failures: list[str] = []

    # 1) Zero ELIGIBLE on negative ground truth.
    for sid in case.must_not_be_eligible:
        r = results_by_id.get(sid)
        if r is None:
            failures.append(f"missing result for {sid}")
            continue
        if r.status == STATUS_ELIGIBLE:
            failures.append(
                f"FALSE POSITIVE: {sid} returned ELIGIBLE; "
                f"reason='{r.reason_hi}', matched={r.matched_rules}/{r.total_rules}"
            )

    # 2) follow_up_question expectations.
    if case.expects_follow_up:
        if not follow_up:
            failures.append("expected follow_up_question_hi but got null")
        elif case.follow_up_contains:
            if not any(tok.lower() in follow_up.lower() for tok in case.follow_up_contains):
                failures.append(
                    f"follow_up={follow_up!r} did not contain any of "
                    f"{case.follow_up_contains}"
                )

    return {
        "case": case.name,
        "transcript": case.transcript,
        "facts": facts.to_dict(),
        "follow_up": follow_up,
        "results": [
            {
                "scheme_id": r.scheme_id,
                "status": r.status,
                "reason_hi": r.reason_hi,
                "matched": f"{r.matched_rules}/{r.total_rules}",
            }
            for r in results
        ],
        "must_not_be_eligible": case.must_not_be_eligible,
        "expects_follow_up": case.expects_follow_up,
        "failures": failures,
        "passed": not failures,
    }


async def main() -> None:
    svc = EligibilityService()
    out: list[dict] = []
    for case in CASES:
        out.append(await run_case(svc, case))

    Path("verify_eligibility_10cases.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n=== 10-CASE ELIGIBILITY VERIFY ===")
    n_pass = sum(1 for c in out if c["passed"])
    for c in out:
        marker = "PASS" if c["passed"] else "FAIL"
        print(f"  {c['case']}: {marker}")
        for f in c["failures"]:
            print(f"      - {f}")
    print(f"\n{n_pass}/{len(out)} cases passed")
    print(f"OVERALL: {'PASS' if n_pass == len(out) else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
