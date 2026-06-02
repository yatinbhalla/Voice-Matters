"""Probe the OpenAI key + embeddings endpoint without flipping
EMBED_PROVIDER. Runs a real /embeddings call and prints:
  - whether the key is loaded
  - whether the call succeeded (HTTP/auth)
  - returned vector dimension
  - billing-aware error (insufficient_quota / rate_limit / invalid_key)

Usage:
  cd backend
  .venv/Scripts/python.exe _verify_openai.py
"""
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")


async def main() -> int:
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        print("FAIL · OPENAI_API_KEY not set in .env")
        return 1
    masked = key[:7] + "..." + key[-4:] if len(key) > 12 else "***"
    print(f"key loaded · {masked} ({len(key)} chars)")

    try:
        from openai import AsyncOpenAI
    except ImportError:
        print("FAIL · openai package not installed. Run: pip install openai")
        return 1

    client = AsyncOpenAI(api_key=key)
    probes = [
        "PM-KISAN kisaan ko ₹6000 saal milta hai",   # Hindi-Roman
        "बेटी के लिए सुकन्या समृद्धि योजना",          # Devanagari
        "What schemes are available for farmers?",   # English
    ]
    print(f"calling text-embedding-3-small with {len(probes)} probe inputs...")
    t0 = time.perf_counter()
    try:
        resp = await client.embeddings.create(
            model="text-embedding-3-small", input=probes
        )
    except Exception as e:
        kind = type(e).__name__
        msg = str(e)
        print(f"FAIL · {kind}: {msg[:240]}")
        if "insufficient_quota" in msg or "billing" in msg.lower():
            print("       -> key valid but billing has no credit/quota")
        elif "invalid_api_key" in msg or "401" in msg:
            print("       -> key rejected (typo or revoked)")
        elif "rate_limit" in msg or "429" in msg:
            print("       -> rate-limited; try again in a few seconds")
        return 1
    elapsed = (time.perf_counter() - t0) * 1000
    vecs = [d.embedding for d in resp.data]
    print(
        f"OK · got {len(vecs)} vectors · dim={len(vecs[0])} · {elapsed:.0f}ms "
        f"· model={resp.model}"
    )
    # Cheap sanity: cosine self-similarity should be 1.0 +/- float noise
    import math
    a = vecs[0]
    sim_self = sum(x * x for x in a) ** 0.5
    print(f"sanity · ||v[0]|| = {sim_self:.4f}  (should be ~1.0 for L2-normalized)")
    print()
    print("Next step: set EMBED_PROVIDER=openai in .env, then re-ingest the")
    print("corpus into a 1536-dim Pinecone index. Local index is 384-dim and")
    print("will need to be recreated when switching providers.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
