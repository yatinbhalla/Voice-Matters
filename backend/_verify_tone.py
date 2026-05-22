"""15-query tone verify: 5 queries per persona (Sushila, Ramesh, Pooja).

Per the brief's verify requirements (Prompt 8):
  - 5 queries per persona, 3 personas, 15 responses total
  - Hard assertion: 0 forbidden-pattern hits across all responses
  - Output a human-reviewable report so Yatin / Bhavesh / Aditi can each
    grade tone independently

What's auto-checked vs. human-graded:
  AUTO (this script):
    - forbidden-pattern scan (urgency, condescension, fake intimacy,
      jargon) - must be 0 hits
    - structural compliance: greeting / mirror / source citation / 14434
      where applicable
  HUMAN (Yatin, Bhavesh, Aditi review verify_tone_review.md):
    - warmth, "feels like a real didi/bhaiya?", clarity for an 8th-pass
      reader, accuracy of the next-step instruction
"""
import asyncio
import json
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from services.answer_service import AnswerService  # noqa: E402
from services.rag_service import RAGService  # noqa: E402
from services.voice_pipeline import _all_known_scheme_names  # noqa: E402

# ---------------------------------------------------------------------------
# Personas + queries
# ---------------------------------------------------------------------------

QUERIES = {
    "sushila": [
        "Mere paas chhoti beti hai, uske liye kuch saving scheme batao",
        "Main 35 saal ki hoon, ghar ka kaam karti hoon. Bude hone par koi pension milegi kya?",
        "Mere paas Aadhaar aur bank khaata hai - kya mujhe koi sarkari madad mil sakti hai?",
        "Mujhe sarkari yojanaon ke baare mein kuch nahin pata, kahan se shuru karoon?",
        "Mahine ka 8000 kamati hoon. Pati ki tabiyat thik nahin rehti - ilaaj ke liye koi scheme hai?",
    ],
    "ramesh": [
        "Main kisaan hoon, sarkar se kya paisa milta hai?",
        "Meri umar 65 saal hai aur main kheti karta hoon - PM-KISAN mein register ho sakta hoon kya?",
        "Mere paas Aadhaar hai magar bank khaata Aadhaar se juda nahin - PM-KISAN ke liye kya karoon?",
        "Pichhli baar kisht nahin aayi - kya karoon, kahan jaaoon?",
        "Mere ladke ki shaadi ke liye kuch sarkari madad hai kya?",
    ],
    "pooja": [
        "Main 28 saal ki hoon, domestic worker hoon. Bude hone par pension chahiye - kya scheme hai?",
        "Mere paas Aadhaar hai magar bank khaata nahin hai - kya kar sakti hoon?",
        "Kaam karte waqt chot lag jaaye to koi bima milta hai kya?",
        "Mahine ke 7000 kamati hoon. Aspatal ka kharcha bahut hai - sarkari card mil sakta hai?",
        "Main shaadi-shuda nahin hoon, akeli rehti hoon - mere liye kya scheme hain?",
    ],
}


# ---------------------------------------------------------------------------
# Forbidden patterns
# ---------------------------------------------------------------------------

FORBIDDEN_PATTERNS = {
    "urgency": [
        r"\bjaldi kariye\b",
        r"\bjaldi karein\b",
        r"\bjaldi karen\b",
        r"\babhi hi\b",
        r"\bturant\b",
        r"\bbas aaj ke liye\b",
        r"\bfauran\b",
    ],
    "condescension": [
        r"\baapko samajhna chahiye\b",
        r"\bye basic hai\b",
        r"\byeh basic hai\b",
        r"\byeh to sab jaante hain\b",
        r"\bye to sab jaante hain\b",
        r"\bobvious hai\b",
    ],
    "fake_intimacy": [
        r"\bmain aapki best friend\b",
        r"\bmaa-baap jaisi\b",
        r"\bmain aapki maa\b",
        r"\bbest friend hoon\b",
    ],
    "jargon": [
        # Watch for these as standalone English words in the user-facing text.
        # Source domains and parentheticals are stripped before matching.
        r"\bprocess\b",
        r"\bverification\b",
        r"\bdocumentation\b",
        r"\bprocedure\b",
        r"\bpremium\b",
        r"\bmaturity\b",
    ],
}


def _strip_for_scan(text: str) -> str:
    """Remove URL/domain noise before scanning so 'pmkisan.gov.in' doesn't
    accidentally match anything. Keeps lowercase for regex match."""
    # Remove URLs and parenthetical domain refs like "(india.gov.in)"
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\([^)]*\.gov\.in[^)]*\)", " ", text)
    text = re.sub(r"\([^)]*\.in[^)]*\)", " ", text)
    return text.lower()


def scan_forbidden(text: str) -> dict[str, list[str]]:
    cleaned = _strip_for_scan(text)
    hits: dict[str, list[str]] = {}
    for category, patterns in FORBIDDEN_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, cleaned):
                hits.setdefault(category, []).append(pat)
    return hits


# ---------------------------------------------------------------------------
# Structural compliance
# ---------------------------------------------------------------------------

REQUIRED_GREETING = re.compile(r"\bachha,?\s+samjh[ai]?\b", re.IGNORECASE)
REQUIRED_MIRROR = re.compile(r"\bjaise aapne (kaha|bola|poocha|pucha)\b", re.IGNORECASE)
REQUIRED_SOURCE = re.compile(r"\b(official portal|portal|pmkisan|pmjay|eshram|india\.gov\.in)\b", re.IGNORECASE)
REFUSAL_HINT = re.compile(r"\b14434\b")
PAKKA_NAHIN = re.compile(r"pakka jaankari nahin|koi jaankari nahi", re.IGNORECASE)


def structural_checks(response: str) -> dict:
    is_refusal = bool(PAKKA_NAHIN.search(response))
    return {
        "has_greeting_acha_samjha": bool(REQUIRED_GREETING.search(response)),
        "has_mirror_jaise_aapne_kaha": bool(REQUIRED_MIRROR.search(response)),
        "has_source_citation": bool(REQUIRED_SOURCE.search(response)),
        "has_helpline_14434": bool(REFUSAL_HINT.search(response)),
        "is_refusal": is_refusal,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_one(rag: RAGService, ans: AnswerService, query: str) -> dict:
    chunks = await rag.retrieve(query, top_k=5)
    known = await _all_known_scheme_names()
    answer = await ans.answer(query, chunks, all_known_scheme_names=known)
    response_text = answer.response_text_hi
    return {
        "query": query,
        "n_chunks": len(chunks),
        "top_scheme": chunks[0].scheme_id if chunks else None,
        "refused": answer.refused,
        "confidence": answer.confidence,
        "response": response_text,
        "forbidden_hits": scan_forbidden(response_text),
        "structural": structural_checks(response_text),
    }


def render_review_markdown(results: dict[str, list[dict]]) -> str:
    """Generate a human-graded review template for Yatin/Bhavesh/Aditi."""
    out: list[str] = [
        "# Voice Matters - Tone Verify (15 queries)",
        "",
        "**Auto-graded:** forbidden-pattern hits and structural compliance.",
        "**Human-graded (each reviewer fills their column):** warmth, clarity, accuracy.",
        "",
        "Rate each response 1-5 (1=fails our voice, 5=perfect didi/bhaiya).",
        "",
        "| Reviewer | Tone hits target? | Notes |",
        "|---|---|---|",
        "| Yatin   |   |   |",
        "| Bhavesh |   |   |",
        "| Aditi   |   |   |",
        "",
        "---",
        "",
    ]
    for persona, items in results.items():
        out.append(f"## Persona: {persona.capitalize()}")
        out.append("")
        for i, r in enumerate(items, start=1):
            out.append(f"### Q{i}: {r['query']}")
            out.append("")
            out.append("**Response:**")
            out.append("")
            out.append("> " + r["response"].replace("\n", "\n> "))
            out.append("")
            out.append(f"- top scheme: `{r['top_scheme']}` · refused: `{r['refused']}` · confidence: `{r['confidence']}`")
            out.append(f"- structural: `{r['structural']}`")
            forbidden = r["forbidden_hits"]
            out.append(
                f"- forbidden hits: `{'NONE' if not forbidden else forbidden}`"
            )
            out.append("")
            out.append("Grading:")
            out.append("")
            out.append("| Reviewer | Warmth (1-5) | Clarity (1-5) | Accurate next step? | Notes |")
            out.append("|---|---|---|---|---|")
            out.append("| Yatin   |   |   |   |   |")
            out.append("| Bhavesh |   |   |   |   |")
            out.append("| Aditi   |   |   |   |   |")
            out.append("")
        out.append("")
    return "\n".join(out)


async def main() -> None:
    rag = RAGService()
    ans = AnswerService()
    results: dict[str, list[dict]] = {}
    for persona, queries in QUERIES.items():
        results[persona] = []
        for q in queries:
            print(f"  [{persona}] {q[:60]}...")
            results[persona].append(await run_one(rag, ans, q))

    Path("verify_tone.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("verify_tone_review.md").write_text(
        render_review_markdown(results), encoding="utf-8"
    )

    # Roll-up assertions
    total = 0
    forbidden_total = 0
    forbidden_responses: list[tuple[str, int, dict]] = []
    structural_failures: list[tuple[str, int, dict]] = []
    for persona, items in results.items():
        for i, r in enumerate(items):
            total += 1
            if r["forbidden_hits"]:
                forbidden_total += sum(len(v) for v in r["forbidden_hits"].values())
                forbidden_responses.append((persona, i + 1, r["forbidden_hits"]))
            s = r["structural"]
            # For non-refusal answers, expect greeting + source citation + (optionally mirror).
            # For refusals, expect greeting + helpline.
            if r["refused"]:
                if not (s["has_greeting_acha_samjha"] and s["has_helpline_14434"]):
                    structural_failures.append((persona, i + 1, s))
            else:
                if not (s["has_greeting_acha_samjha"] and s["has_source_citation"]):
                    structural_failures.append((persona, i + 1, s))

    print()
    print("=== TONE VERIFY ===")
    print(f"  responses tested        : {total}")
    print(f"  forbidden pattern hits  : {forbidden_total}")
    if forbidden_total:
        for persona, qn, hits in forbidden_responses:
            print(f"    - {persona} Q{qn}: {hits}")
    print(f"  structural failures     : {len(structural_failures)}")
    if structural_failures:
        for persona, qn, s in structural_failures:
            print(f"    - {persona} Q{qn}: {s}")

    overall_pass = forbidden_total == 0 and not structural_failures
    print(f"  OVERALL                 : {'PASS' if overall_pass else 'FAIL'}")
    print()
    print("Review template: verify_tone_review.md")
    print("Raw data       : verify_tone.json")


if __name__ == "__main__":
    asyncio.run(main())
