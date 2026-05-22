"""Eligibility checker.

Two stages:
  1. parse_facts(transcript): Sarvam-1 LLM extracts a strict JSON of 8 nullable
     facts (gender, age, income_monthly_inr, state, occupation,
     family_members, has_aadhaar, has_bank_account). Missing or unsure
     fields stay null.
  2. evaluate(facts, scheme): rule-by-rule check returning one of
     ELIGIBLE | NEED_MORE_INFO | NOT_ELIGIBLE with a Hindi reason.

CRITICAL: false-positive target = 0%. Any required field that is null
forces NEED_MORE_INFO. ELIGIBLE only when every required rule passes AND
the scheme does not require external verification (e.g. SECC list,
land records, beti's birth certificate).
"""
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import structlog

from clients.sarvam_client import SarvamClient
from data import scheme_corpus
from services.rag_service import Chunk

log = structlog.get_logger()

STATUS_ELIGIBLE = "ELIGIBLE"
STATUS_NEED_MORE_INFO = "NEED_MORE_INFO"
STATUS_NOT_ELIGIBLE = "NOT_ELIGIBLE"

_STATUS_RANK = {STATUS_ELIGIBLE: 0, STATUS_NEED_MORE_INFO: 1, STATUS_NOT_ELIGIBLE: 2}

FACT_KEYS = (
    "gender",
    "age",
    "income_monthly_inr",
    "state",
    "occupation",
    "family_members",
    "has_aadhaar",
    "has_bank_account",
)


@dataclass
class UserFacts:
    gender: str | None = None
    age: int | None = None
    income_monthly_inr: int | None = None
    state: str | None = None
    occupation: str | None = None
    family_members: int | None = None
    has_aadhaar: bool | None = None
    has_bank_account: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EligibilityResult:
    scheme_id: str
    name: str
    status: str
    reason_hi: str
    confidence: str  # "high" | "medium" | "low"
    source_url: str
    missing_fields: list[str]
    matched_rules: int
    total_rules: int

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------

_EXTRACT_SYSTEM = """\
Aap ek information-extraction assistant hain. User ke Hindi/Hinglish transcript se,
yeh 8 fields nikalein. SIRF valid JSON return karein, koi explanation ya extra text nahin.

{
  "gender": "male" | "female" | "other" | null,
  "age": <integer> | null,
  "income_monthly_inr": <integer> | null,
  "state": "<Indian state name>" | null,
  "occupation": "<short phrase>" | null,
  "family_members": <integer> | null,
  "has_aadhaar": true | false | null,
  "has_bank_account": true | false | null
}

NIYAM:
1. Agar user ne kisi field ke baare mein BILKUL nahin bola, ya unsure hai, to null rakhein.
   Apni taraf se guess MAT karein. False-positive se behtar hai null.
2. age: number of years (jaise "35 saal" -> 35). Age range bole to lower bound use karein.
3. income_monthly_inr: monthly income in INR. Agar "5 lakh saal" bola to 41666. "10 hazaar mahina" -> 10000. Range bole to lower bound.
4. occupation: short phrase jaise "kisan", "construction worker", "teacher", "housewife".
5. family_members: total log parivar mein.
6. has_aadhaar / has_bank_account: agar clearly bola "haan/yes" -> true; "nahi/no" -> false; clear nahin -> null.
"""

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _coerce_int(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _coerce_bool(v: Any) -> bool | None:
    if v is True or v is False:
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "yes", "haan", "1"):
        return True
    if s in ("false", "no", "nahi", "nahin", "0"):
        return False
    return None


def _coerce_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _parse_llm_json(raw: str) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = _JSON_BLOCK_RE.search(raw)
        if not m:
            return {}
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return {}


async def parse_facts(transcript: str, sarvam: SarvamClient | None = None) -> UserFacts:
    if not transcript or not transcript.strip():
        return UserFacts()
    sarvam = sarvam or SarvamClient()
    try:
        raw = await sarvam.generate(
            prompt=f"Transcript:\n{transcript}",
            system_prompt=_EXTRACT_SYSTEM,
            temperature=0.0,
        )
    except Exception as e:
        log.warning("eligibility_extract_failed", error=str(e))
        return UserFacts()

    obj = _parse_llm_json(raw)
    if not isinstance(obj, dict):
        log.warning("eligibility_extract_non_dict", raw=raw[:200])
        return UserFacts()

    facts = UserFacts(
        gender=_coerce_str(obj.get("gender")),
        age=_coerce_int(obj.get("age")),
        income_monthly_inr=_coerce_int(obj.get("income_monthly_inr")),
        state=_coerce_str(obj.get("state")),
        occupation=_coerce_str(obj.get("occupation")),
        family_members=_coerce_int(obj.get("family_members")),
        has_aadhaar=_coerce_bool(obj.get("has_aadhaar")),
        has_bank_account=_coerce_bool(obj.get("has_bank_account")),
    )
    log.info("eligibility_facts_extracted", facts=facts.to_dict())
    return facts


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


def _check_rule(rule: dict, facts: UserFacts) -> tuple[str, str]:
    """Return one of ('ok', '') | ('missing', reason) | ('violated', reason).

    Conservative: any missing required input -> 'missing'.
    """
    field = rule["field"]
    op = rule["op"]
    expected = rule.get("value")
    fact_value = getattr(facts, field, None)

    if fact_value is None:
        return ("missing", rule.get("ask_hi", f"{field} ki jaankari chahiye"))

    if op == "eq":
        ok = fact_value == expected
    elif op == "neq":
        ok = fact_value != expected
    elif op == "gte":
        ok = fact_value >= expected
    elif op == "lte":
        ok = fact_value <= expected
    elif op == "between":
        lo, hi = expected
        ok = lo <= fact_value <= hi
    elif op == "in":
        ok = fact_value in expected
    elif op == "not_in":
        ok = fact_value not in expected
    elif op == "contains_any":
        haystack = str(fact_value).lower()
        ok = any(str(t).lower() in haystack for t in expected)
    elif op == "not_contains_any":
        haystack = str(fact_value).lower()
        ok = not any(str(t).lower() in haystack for t in expected)
    else:
        log.warning("eligibility_unknown_op", op=op)
        return ("missing", rule.get("ask_hi", "Aur jaankari chahiye"))

    if ok:
        return ("ok", "")
    return ("violated", rule.get("reason_hi", "Eligibility criteria match nahin karta"))


def evaluate(facts: UserFacts, scheme: dict) -> EligibilityResult:
    rules_block = scheme.get("eligibility_rules") or {}
    rules = rules_block.get("rules", [])
    needs_verify = bool(rules_block.get("requires_external_verification"))
    verify_msg = rules_block.get("external_verification_hi", "")

    missing_fields: list[str] = []
    violations: list[str] = []
    matched = 0
    for rule in rules:
        kind, reason = _check_rule(rule, facts)
        if kind == "ok":
            matched += 1
        elif kind == "missing":
            field = rule.get("field")
            if field and field not in missing_fields:
                missing_fields.append(field)
        elif kind == "violated":
            violations.append(reason)

    total = len(rules)
    name = scheme.get("name_en") or scheme.get("name") or scheme.get("scheme_id")
    source_url = scheme.get("source_url", "")

    # 1) Hard violation wins -- NOT_ELIGIBLE regardless of missing fields.
    if violations:
        return EligibilityResult(
            scheme_id=scheme["scheme_id"],
            name=name,
            status=STATUS_NOT_ELIGIBLE,
            reason_hi=violations[0],
            confidence="high",
            source_url=source_url,
            missing_fields=missing_fields,
            matched_rules=matched,
            total_rules=total,
        )

    # 2) Any missing field -> NEED_MORE_INFO (false-positive guard).
    if missing_fields:
        # Ask about the first missing field of the first missing rule.
        ask_for_first = next(
            (
                r.get("ask_hi")
                for r in rules
                if r.get("field") == missing_fields[0]
            ),
            f"{missing_fields[0]} ki jaankari chahiye",
        )
        return EligibilityResult(
            scheme_id=scheme["scheme_id"],
            name=name,
            status=STATUS_NEED_MORE_INFO,
            reason_hi=ask_for_first,
            confidence="medium",
            source_url=source_url,
            missing_fields=missing_fields,
            matched_rules=matched,
            total_rules=total,
        )

    # 3) All rules pass. If verification needed, still NEED_MORE_INFO.
    if needs_verify:
        return EligibilityResult(
            scheme_id=scheme["scheme_id"],
            name=name,
            status=STATUS_NEED_MORE_INFO,
            reason_hi=verify_msg or "Aage verification zaroori hai",
            confidence="medium",
            source_url=source_url,
            missing_fields=[],
            matched_rules=matched,
            total_rules=total,
        )

    return EligibilityResult(
        scheme_id=scheme["scheme_id"],
        name=name,
        status=STATUS_ELIGIBLE,
        reason_hi="Aap is yojana ke liye eligible hain - aage badhein",
        confidence="high",
        source_url=source_url,
        missing_fields=[],
        matched_rules=matched,
        total_rules=total,
    )


# ---------------------------------------------------------------------------
# Top-level entry
# ---------------------------------------------------------------------------


def _pick_follow_up(results: list[EligibilityResult]) -> str | None:
    """Best next question = first missing field of the highest-priority
    NEED_MORE_INFO scheme that has a missing field (not a verification
    block). If none, return None."""
    for r in results:
        if r.status == STATUS_NEED_MORE_INFO and r.missing_fields:
            return r.reason_hi
    return None


def _dedupe_scheme_ids(chunks: list[Chunk]) -> list[str]:
    seen: list[str] = []
    for c in chunks:
        if c.scheme_id and c.scheme_id not in seen:
            seen.append(c.scheme_id)
    return seen


class EligibilityService:
    def __init__(self, sarvam: SarvamClient | None = None) -> None:
        self.sarvam = sarvam or SarvamClient()

    async def check(
        self, transcript: str, retrieved_chunks: list[Chunk]
    ) -> tuple[list[EligibilityResult], str | None, UserFacts]:
        scheme_ids = _dedupe_scheme_ids(retrieved_chunks)
        if not scheme_ids:
            return [], None, UserFacts()
        facts = await parse_facts(transcript, self.sarvam)

        results: list[EligibilityResult] = []
        for sid in scheme_ids:
            scheme = scheme_corpus.get_scheme(sid)
            if not scheme:
                continue
            results.append(evaluate(facts, scheme))

        results.sort(key=lambda r: (_STATUS_RANK[r.status], -r.matched_rules))
        follow_up = _pick_follow_up(results)
        return results, follow_up, facts
