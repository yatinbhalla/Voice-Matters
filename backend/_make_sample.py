"""One-shot helper: synthesize a sample Hindi WAV using Sarvam Bulbul so we
can POST it to /voice and exercise the full pipeline. Not part of the app."""
import asyncio
import base64
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

OUT = Path(__file__).resolve().parent / "sample_hindi.wav"
TXT = "Meri beti ke liye kaun si yojana achi hai?"


async def main() -> None:
    key = os.getenv("SARVAM_API_KEY")
    if not key:
        sys.exit("SARVAM_API_KEY missing")
    body = {
        "inputs": [TXT],
        "target_language_code": "hi-IN",
        "speaker": "anushka",
        "model": "bulbul:v2",
        "speech_sample_rate": 16000,
        "enable_preprocessing": True,
    }
    async with httpx.AsyncClient(timeout=30.0) as c:
        r = await c.post(
            "https://api.sarvam.ai/text-to-speech",
            headers={"api-subscription-key": key},
            json=body,
        )
        r.raise_for_status()
    audio = base64.b64decode(r.json()["audios"][0])
    OUT.write_bytes(audio)
    print(f"wrote {OUT} ({len(audio)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
