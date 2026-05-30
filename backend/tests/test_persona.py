"""pytest wrapper for the persona + adversarial regression suite.

Run:
  cd backend
  .venv/Scripts/python.exe -m pytest tests/test_persona.py -v

Each case in PERSONA_TEST_CASES becomes one parametrized test. Wires
through the same /chat pipeline that run_regression.py uses, so we get
the same assertion semantics. Voice-mode round-trips are exercised
separately by run_regression.py --mode voice (too slow for pytest).
"""
import os
import time
import uuid

import httpx
import pytest

from tests.persona_scripts import (
    PERSONA_TEST_CASES,
    assertions_for,
)

API_BASE = os.getenv("VM_API_BASE", "http://127.0.0.1:8000/api/v1")

_warmed_up = False


@pytest.fixture(scope="session")
def http_client():
    """One shared httpx client for the whole pytest session."""
    return httpx.Client(timeout=180.0)


def _warmup_once(client: httpx.Client) -> None:
    global _warmed_up
    if _warmed_up:
        return
    try:
        client.post(
            f"{API_BASE}/conversation/{uuid.uuid4()}/chat",
            json={"text": "Namaste", "language_hint": "hi"},
        )
    except Exception:
        pass
    _warmed_up = True


@pytest.mark.parametrize("case", PERSONA_TEST_CASES, ids=lambda c: c["id"])
def test_case(case, http_client):
    """One assertion bundle per case; the test passes only if every
    sub-assertion in `assertions_for` passes."""
    _warmup_once(http_client)
    conv_id = str(uuid.uuid4())
    start = time.perf_counter()
    r = http_client.post(
        f"{API_BASE}/conversation/{conv_id}/chat",
        json={"text": case["transcript_hi"], "language_hint": "hi"},
    )
    elapsed = time.perf_counter() - start
    assert r.status_code == 200, f"backend returned {r.status_code}"
    response = r.json()

    assertions = assertions_for(case, response, elapsed)
    failed = [a for a in assertions if not a["passed"]]
    if failed:
        details = "\n".join(
            f"  - {a['name']}" + (f": {a['detail']}" if a.get("detail") else "")
            for a in failed
        )
        pytest.fail(
            f"{case['id']} [{case['category']}] failed {len(failed)}/{len(assertions)} "
            f"assertions (took {elapsed:.1f}s):\n{details}\n"
            f"response_text_hi: {(response.get('response_text_hi') or '')[:300]}"
        )
