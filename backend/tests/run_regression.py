"""Nightly regression runner for Voice Matters.

Usage:
  cd backend
  .venv/Scripts/python.exe tests/run_regression.py                # chat mode (fast, default)
  .venv/Scripts/python.exe tests/run_regression.py --mode voice   # full pipeline w/ Bulbul + Saaras
  .venv/Scripts/python.exe tests/run_regression.py --only persona

Outputs:
  backend/tests/report.html
  backend/tests/report.json
  backend/tests/snapshots/    (voice mode only - response audio)
  backend/tests/synthesized/  (voice mode only - user's audio input)

Pass targets:
  persona category    >= 100%
  adversarial total   >=  95%
"""
import argparse
import asyncio
import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

import httpx  # noqa: E402

from tests.persona_scripts import (  # noqa: E402
    PERSONA_TEST_CASES,
    assertions_for,
    summarize_by_category,
)

API_BASE = os.getenv("VM_API_BASE", "http://127.0.0.1:8000/api/v1")
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"
SARVAM_KEY = os.getenv("SARVAM_API_KEY", "")

TESTS_DIR = Path(__file__).parent
SNAPSHOT_DIR = TESTS_DIR / "snapshots"
SYNTHESIZED_DIR = TESTS_DIR / "synthesized"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SYNTHESIZED_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH = TESTS_DIR / "report.html"
REPORT_JSON = TESTS_DIR / "report.json"


async def synthesize_transcript(text: str, client: httpx.AsyncClient) -> bytes | None:
    if not SARVAM_KEY:
        return None
    body = {
        "inputs": [text[:450]],
        "target_language_code": "hi-IN",
        "speaker": "anushka",
        "model": "bulbul:v2",
        "speech_sample_rate": 16000,
        "enable_preprocessing": True,
    }
    try:
        r = await client.post(
            SARVAM_TTS_URL,
            headers={"api-subscription-key": SARVAM_KEY},
            json=body,
            timeout=30.0,
        )
        if r.status_code != 200:
            return None
        return base64.b64decode(r.json()["audios"][0])
    except Exception:
        return None


async def run_case_chat(case: dict, client: httpx.AsyncClient) -> dict:
    conv_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        r = await client.post(
            f"{API_BASE}/conversation/{conv_id}/chat",
            json={"text": case["transcript_hi"], "language_hint": "hi"},
            timeout=180.0,
        )
        elapsed = time.perf_counter() - start
        if r.status_code != 200:
            return {
                "case_id": case["id"], "category": case["category"],
                "transcript_hi": case["transcript_hi"],
                "elapsed_s": round(elapsed, 2),
                "response": {}, "transport_error": f"HTTP {r.status_code}",
                "assertions": [], "passed": False,
            }
        response = r.json()
    except Exception as e:
        return {
            "case_id": case["id"], "category": case["category"],
            "transcript_hi": case["transcript_hi"],
            "elapsed_s": round(time.perf_counter() - start, 2),
            "response": {}, "transport_error": str(e),
            "assertions": [], "passed": False,
        }

    assertions = assertions_for(case, response, elapsed)
    return {
        "case_id": case["id"], "category": case["category"],
        "transcript_hi": case["transcript_hi"],
        "elapsed_s": round(elapsed, 2),
        "response": {
            "response_text_hi": (response.get("response_text_hi") or "")[:400],
            "top_3": [s.get("scheme_id") for s in response.get("top_3_schemes", [])],
            "confidence": response.get("confidence"),
            "refused": response.get("refused"),
            "follow_up": response.get("follow_up_question_hi"),
        },
        "assertions": assertions,
        "passed": all(a["passed"] for a in assertions),
    }


async def run_case_voice(case: dict, client: httpx.AsyncClient) -> dict:
    audio = await synthesize_transcript(case["transcript_hi"], client)
    if audio is None:
        result = await run_case_chat(case, client)
        result["voice_fallback_chat"] = True
        return result
    syn_path = SYNTHESIZED_DIR / f"{case['id']}.wav"
    syn_path.write_bytes(audio)

    conv_id = str(uuid.uuid4())
    start = time.perf_counter()
    try:
        with open(syn_path, "rb") as f:
            files = {"audio": (f"{case['id']}.wav", f, "audio/wav")}
            r = await client.post(
                f"{API_BASE}/conversation/{conv_id}/voice",
                files=files,
                data={"language_hint": "hi"},
                timeout=120.0,
            )
        elapsed = time.perf_counter() - start
        if r.status_code != 200:
            return {
                "case_id": case["id"], "category": case["category"],
                "transcript_hi": case["transcript_hi"],
                "elapsed_s": round(elapsed, 2),
                "response": {}, "transport_error": f"HTTP {r.status_code}",
                "assertions": [], "passed": False,
            }
        response = r.json()
    except Exception as e:
        return {
            "case_id": case["id"], "category": case["category"],
            "transcript_hi": case["transcript_hi"],
            "elapsed_s": round(time.perf_counter() - start, 2),
            "response": {}, "transport_error": str(e),
            "assertions": [], "passed": False,
        }

    # Save response audio if present.
    audio_url = response.get("response_audio_url")
    if audio_url:
        try:
            audio_host = API_BASE.rsplit("/api/", 1)[0]
            full = audio_url if audio_url.startswith("http") else audio_host + audio_url
            ar = await client.get(full, timeout=30.0)
            if ar.status_code == 200:
                (SNAPSHOT_DIR / f"{case['id']}.mp3").write_bytes(ar.content)
        except Exception:
            pass

    assertions = assertions_for(case, response, elapsed)
    return {
        "case_id": case["id"], "category": case["category"],
        "transcript_hi": case["transcript_hi"],
        "elapsed_s": round(elapsed, 2),
        "response": {
            "transcript_hi_stt": (response.get("transcript_hi") or "")[:120],
            "response_text_hi": (response.get("response_text_hi") or "")[:400],
            "top_3": [s.get("scheme_id") for s in response.get("top_3_schemes", [])],
            "confidence": response.get("confidence"),
            "refused": response.get("refused"),
            "audio_url": audio_url,
        },
        "assertions": assertions,
        "passed": all(a["passed"] for a in assertions),
    }


def render_html_report(results: list[dict], mode: str) -> str:
    by_cat = summarize_by_category(results)
    persona = by_cat.get("persona", {"total": 0, "passed": 0, "rate": 0})
    adv_total = sum(v["total"] for c, v in by_cat.items() if c != "persona")
    adv_passed = sum(v["passed"] for c, v in by_cat.items() if c != "persona")
    adv_rate = (adv_passed / adv_total) if adv_total else 0
    persona_target_hit = persona["rate"] >= 1.0
    adv_target_hit = adv_rate >= 0.95

    style = """
      body{font-family:Inter,system-ui,sans-serif;background:#F0F4F8;color:#1B2A41;margin:0;padding:24px}
      .wrap{max-width:1100px;margin:0 auto}
      h1{margin:0 0 4px;font-size:24px;letter-spacing:-0.02em}
      .sub{color:#6A7787;font-size:13px;margin-bottom:24px}
      .summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:24px}
      .stat{background:#fff;border:1px solid #E1E7ED;border-radius:14px;padding:14px 16px}
      .stat .lbl{font-size:10px;font-weight:700;color:#6A7787;letter-spacing:0.08em;text-transform:uppercase}
      .stat .val{font-size:24px;font-weight:700;margin-top:6px;font-variant-numeric:tabular-nums}
      .stat.pass .val{color:#4CAF50}.stat.fail .val{color:#E53935}
      table{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;border:1px solid #E1E7ED;font-size:13px}
      th,td{padding:10px 12px;text-align:left;vertical-align:top;border-bottom:1px solid #F0F4F8}
      th{background:#F0F4F8;font-weight:700;font-size:11px;letter-spacing:0.06em;text-transform:uppercase;color:#6A7787}
      tr.pass{background:#fff}tr.fail{background:#FFF6F4}
      .pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}
      .pill.pass{background:#E8F5E9;color:#4CAF50;border:1px solid #C6E5C9}
      .pill.fail{background:#FFEBEE;color:#E53935;border:1px solid #F5C4BC}
      .pill.cat{background:#F0F4F8;color:#2A9DB5;border:1px solid #E1E7ED;font-size:10px}
      .assert-list{margin:4px 0 0;padding:0;list-style:none;font-size:11px;color:#6A7787}
      .assert-list li.fail{color:#E53935}
      .resp{font-size:11px;color:#6A7787;max-width:340px}
      .mono{font-family:ui-monospace,monospace;font-size:11px}
    """

    rows = []
    for r in results:
        row_class = "pass" if r["passed"] else "fail"
        assertions_html = "".join(
            f'<li class="{("pass" if a["passed"] else "fail")}">'
            f'{"✓" if a["passed"] else "✗"} {a["name"]}'
            f'{(": " + a["detail"]) if a.get("detail") else ""}</li>'
            for a in r["assertions"]
        )
        resp = r.get("response", {})
        resp_html = (
            f'<div>{(resp.get("response_text_hi","") or "")[:200]}</div>'
            f'<div class="mono">top_3: {resp.get("top_3")}</div>'
            f'<div class="mono">conf: {resp.get("confidence")} · refused: {resp.get("refused")}</div>'
        )
        if r.get("transport_error"):
            resp_html = f'<div class="mono">ERROR: {r["transport_error"]}</div>'
        rows.append(
            f'<tr class="{row_class}">'
            f'<td><strong>{r["case_id"]}</strong><div><span class="pill cat">{r["category"]}</span></div></td>'
            f'<td>{r["transcript_hi"][:120]}</td>'
            f'<td><span class="pill {row_class}">{"PASS" if r["passed"] else "FAIL"}</span> '
            f'<span class="mono">{r["elapsed_s"]}s</span></td>'
            f'<td class="resp">{resp_html}</td>'
            f'<td><ul class="assert-list">{assertions_html}</ul></td>'
            f'</tr>'
        )
    table = "\n".join(rows)

    by_cat_rows = "".join(
        f'<tr><td>{c}</td><td class="mono">{v["passed"]}/{v["total"]}</td>'
        f'<td><span class="pill {("pass" if v["rate"] >= (1.0 if c == "persona" else 0.95) else "fail")}">'
        f'{(v["rate"]*100):.1f}%</span></td></tr>'
        for c, v in by_cat.items()
    )

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Regression Report</title><style>{style}</style></head>
<body><div class="wrap">
<h1>Voice Matters · Regression report</h1>
<div class="sub">Mode: <strong>{mode}</strong> · {len(results)} cases · run at {time.strftime("%Y-%m-%d %H:%M:%S")}</div>
<div class="summary">
  <div class="stat {("pass" if persona_target_hit else "fail")}">
    <div class="lbl">Persona</div>
    <div class="val">{persona["passed"]}/{persona["total"]}</div>
    <div class="mono">target ≥ 100% · {(persona["rate"]*100):.1f}%</div>
  </div>
  <div class="stat {("pass" if adv_target_hit else "fail")}">
    <div class="lbl">Adversarial</div>
    <div class="val">{adv_passed}/{adv_total}</div>
    <div class="mono">target ≥ 95% · {(adv_rate*100):.1f}%</div>
  </div>
</div>
<h3 style="margin-top:24px">By category</h3>
<table><thead><tr><th>Category</th><th>Passed</th><th>Rate</th></tr></thead>
<tbody>{by_cat_rows}</tbody></table>
<h3 style="margin-top:24px">Per case</h3>
<table><thead><tr><th>Case</th><th>Transcript</th><th>Result</th><th>Response</th><th>Assertions</th></tr></thead>
<tbody>{table}</tbody></table>
</div></body></html>"""


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["chat", "voice"], default="chat")
    p.add_argument("--only", choices=["persona", "adversarial", "all"], default="all")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args()

    cases = list(PERSONA_TEST_CASES)
    if args.only == "persona":
        cases = [c for c in cases if c["category"] == "persona"]
    elif args.only == "adversarial":
        cases = [c for c in cases if c["category"] != "persona"]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} cases in {args.mode} mode...")
    results = []
    async with httpx.AsyncClient() as client:
        # Warmup: hammer the pipeline once so the local embedder loads, the
        # Sarvam connection pool warms up, and the first real case isn't
        # an outlier. Result discarded.
        print("  [warmup] priming pipeline... ", end="", flush=True)
        warmup_start = time.perf_counter()
        try:
            await client.post(
                f"{API_BASE}/conversation/{uuid.uuid4()}/chat",
                json={"text": "Namaste", "language_hint": "hi"},
                timeout=180.0,
            )
        except Exception:
            pass
        print(f"done in {time.perf_counter() - warmup_start:.1f}s")
        for i, case in enumerate(cases, 1):
            print(f"  [{i}/{len(cases)}] {case['id']}...", end=" ", flush=True)
            if args.mode == "voice":
                r = await run_case_voice(case, client)
            else:
                r = await run_case_chat(case, client)
            results.append(r)
            print("PASS" if r["passed"] else "FAIL", f"({r['elapsed_s']}s)")

    REPORT_PATH.write_text(render_html_report(results, args.mode), encoding="utf-8")
    REPORT_JSON.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    by_cat = summarize_by_category(results)
    persona = by_cat.get("persona", {"passed": 0, "total": 0, "rate": 0})
    adv_total = sum(v["total"] for c, v in by_cat.items() if c != "persona")
    adv_passed = sum(v["passed"] for c, v in by_cat.items() if c != "persona")
    adv_rate = (adv_passed / adv_total) if adv_total else 0
    print()
    print("=== SUMMARY ===")
    print(f"  persona     : {persona['passed']}/{persona['total']} ({persona['rate']*100:.1f}%)  target >= 100%")
    print(f"  adversarial : {adv_passed}/{adv_total} ({adv_rate*100:.1f}%)  target >= 95%")
    for c, v in by_cat.items():
        print(f"    {c:18s} {v['passed']}/{v['total']} ({v['rate']*100:.1f}%)")
    print(f"  report: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
