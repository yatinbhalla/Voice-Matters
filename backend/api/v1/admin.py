"""Trust metrics for the live BITSOM dashboard.

Six metrics over the last N assistant turns (default 100):
  hallucination_rate         - % responses where the hallucination guard
                                appended the "purani ho sakti hai" suffix
  eligibility_false_positive - % responses where an ELIGIBLE result
                                landed on a scheme that requires external
                                verification (PMJAY/PM-KISAN/SSY) - should
                                be 0 by design
  comprehension_pass_rate    - % responses that had at least one retrieved
                                scheme (RAG matched something)
  refusal_rate               - % responses on the refusal path (no schemes
                                + helpline-style answer)
  e2e_latency_p95_ms         - p95 of total_ms from telemetry rows
  citation_rate              - % responses with >=1 source URL
  sample_size                - actual number of rows used

Pulls from `messages` (assistant rows) for content-level checks and
`telemetry` (event_type IN ('voice_pipeline','chat_pipeline')) for
latency. Each metric is also returned with its `target` so the
dashboard can render pass/fail without a second config lookup.
"""
import statistics

import structlog
from fastapi import APIRouter, Query
from sqlalchemy import desc, select

from data import scheme_corpus
from models import Message, Role, Telemetry
from models.db import SessionLocal
from services.answer_service import HALLUCINATION_SUFFIX_HI, REFUSAL_HI

log = structlog.get_logger()
router = APIRouter(tags=["admin"])

# Targets (the panel slide promises). Kept here so the dashboard reads
# them straight from the API instead of duplicating in JS.
METRIC_TARGETS = {
    "hallucination_rate":         {"target": 0.02, "direction": "lte"},
    "eligibility_false_positive": {"target": 0.01, "direction": "lte"},
    "comprehension_pass_rate":    {"target": 0.85, "direction": "gte"},
    "refusal_rate":               {"target": 0.25, "direction": "lte"},
    "e2e_latency_p95_ms":         {"target": 6000, "direction": "lte"},
    "citation_rate":              {"target": 0.90, "direction": "gte"},
}


def _is_refusal(text: str) -> bool:
    if not text:
        return False
    # The mechanical refusal opens with this Devanagari phrase, but the
    # LLM-driven refusal also uses "pakka jaankari nahin" / "14434".
    return (
        "पक्की जानकारी नहीं" in text
        or "pakka jaankari nahin" in text.lower()
        or "14434" in text
        or text.startswith(REFUSAL_HI[:30])
    )


def _has_hallucination_flag(text: str) -> bool:
    if not text:
        return False
    return HALLUCINATION_SUFFIX_HI.strip() in text


def _eligibility_false_positive(eligibility_results: list) -> bool:
    """True iff any ELIGIBLE result lands on a scheme that requires
    external verification (PMJAY/SSY/PM-KISAN)."""
    for r in eligibility_results or []:
        if r.get("status") != "ELIGIBLE":
            continue
        sid = r.get("scheme_id")
        if not sid:
            continue
        meta = scheme_corpus.eligibility_rules(sid)
        if meta.get("requires_external_verification"):
            return True
    return False


@router.get("/admin/trust-metrics")
async def trust_metrics(window: int = Query(100, ge=1, le=1000)):
    """Aggregate the last `window` assistant turns into 6 trust metrics."""
    log.info("trust_metrics_compute", window=window)

    if SessionLocal is None:
        return {"error": "DATABASE_URL not configured", "sample_size": 0}

    async with SessionLocal() as session:
        # Most recent N assistant messages.
        msgs_stmt = (
            select(Message)
            .where(Message.role == Role.assistant)
            .order_by(desc(Message.created_at))
            .limit(window)
        )
        messages = (await session.execute(msgs_stmt)).scalars().all()

        # Most recent N telemetry rows for latency. Pull both voice and
        # chat pipeline events; total_ms lives in payload JSONB.
        telemetry_stmt = (
            select(Telemetry)
            .where(Telemetry.event_type.in_(("voice_pipeline", "chat_pipeline")))
            .order_by(desc(Telemetry.created_at))
            .limit(window)
        )
        telemetry_rows = (await session.execute(telemetry_stmt)).scalars().all()

    sample_size = len(messages)

    if sample_size == 0:
        # Empty state - return zeros + targets so the dashboard can render
        # the cards as "no data yet" instead of erroring.
        out = {
            "sample_size": 0,
            "metrics": {
                k: {
                    "value": 0,
                    "target": v["target"],
                    "direction": v["direction"],
                    "pass": True,
                }
                for k, v in METRIC_TARGETS.items()
            },
            "generated_at": None,
        }
        return out

    hallucination_n = 0
    fp_n = 0
    refusal_n = 0
    citation_n = 0
    has_schemes_n = 0

    for m in messages:
        text = m.content_text or ""
        if _has_hallucination_flag(text):
            hallucination_n += 1
        if _eligibility_false_positive(m.eligibility_results or []):
            fp_n += 1
        if _is_refusal(text):
            refusal_n += 1
        if m.sources:
            citation_n += 1
        if m.retrieved_schemes:
            has_schemes_n += 1

    # p95 latency from telemetry. Filter to rows that have total_ms set.
    totals = [
        t.payload.get("total_ms")
        for t in telemetry_rows
        if t.payload and isinstance(t.payload.get("total_ms"), (int, float))
    ]
    if totals:
        totals_sorted = sorted(totals)
        # statistics.quantiles wants n>=2; fall back to max for tiny samples.
        if len(totals_sorted) >= 20:
            p95 = statistics.quantiles(totals_sorted, n=20)[18]  # 95th percentile
        else:
            p95 = totals_sorted[-1]
        p95_ms = int(p95)
    else:
        p95_ms = 0

    raw = {
        "hallucination_rate": hallucination_n / sample_size,
        "eligibility_false_positive": fp_n / sample_size,
        "comprehension_pass_rate": has_schemes_n / sample_size,
        "refusal_rate": refusal_n / sample_size,
        "e2e_latency_p95_ms": p95_ms,
        "citation_rate": citation_n / sample_size,
    }

    metrics = {}
    for k, v in raw.items():
        t = METRIC_TARGETS[k]
        passed = (
            v <= t["target"] if t["direction"] == "lte" else v >= t["target"]
        )
        metrics[k] = {
            "value": (round(v, 4) if isinstance(v, float) else v),
            "target": t["target"],
            "direction": t["direction"],
            "pass": passed,
        }

    return {
        "sample_size": sample_size,
        "metrics": metrics,
        "generated_at": (
            messages[0].created_at.isoformat() if messages and messages[0].created_at else None
        ),
        "telemetry_sample_size": len(totals),
    }
