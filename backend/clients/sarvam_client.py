"""Sarvam AI client: Saaras STT, Mayura LLM, Bulbul TTS.

httpx.AsyncClient + tenacity (3 retries, exponential backoff). All methods
raise RuntimeError when SARVAM_API_KEY is missing so callers can fail-soft.
"""
import base64
import os

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

log = structlog.get_logger()

SARVAM_BASE = "https://api.sarvam.ai"
STT_URL = f"{SARVAM_BASE}/speech-to-text"
CHAT_URL = f"{SARVAM_BASE}/v1/chat/completions"
TTS_URL = f"{SARVAM_BASE}/text-to-speech"

_RETRY = dict(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
)


class SarvamClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SARVAM_API_KEY", "")
        self._timeout = httpx.Timeout(30.0, connect=10.0)

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("SARVAM_API_KEY not set")

    def _headers(self) -> dict:
        return {"api-subscription-key": self.api_key}

    @retry(**_RETRY)
    async def transcribe(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        filename: str = "audio.wav",
        content_type: str = "audio/wav",
    ) -> str:
        self._require_key()
        files = {"file": (filename, audio_bytes, content_type)}
        data = {"model": "saarika:v2.5", "language_code": language_code}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                STT_URL, headers=self._headers(), files=files, data=data
            )
            resp.raise_for_status()
            payload = resp.json()
        transcript = payload.get("transcript") or payload.get("text") or ""
        log.info("sarvam_stt_ok", chars=len(transcript))
        return transcript

    @retry(**_RETRY)
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = "sarvam-m",
        temperature: float = 0.2,
    ) -> str:
        self._require_key()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        body = {"model": model, "messages": messages, "temperature": temperature}
        headers = {**self._headers(), "Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(CHAT_URL, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()
        choices = payload.get("choices") or []
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    @retry(**_RETRY)
    async def synthesize(
        self,
        text: str,
        voice: str = "anushka",
        target_language_code: str = "hi-IN",
        model: str = "bulbul:v2",
    ) -> bytes:
        self._require_key()
        body = {
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": voice,
            "model": model,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(TTS_URL, headers=self._headers(), json=body)
            resp.raise_for_status()
            payload = resp.json()
        audios = payload.get("audios") or []
        if not audios:
            raise RuntimeError("Sarvam TTS returned no audio")
        audio_bytes = base64.b64decode(audios[0])
        log.info("sarvam_tts_ok", bytes=len(audio_bytes))
        return audio_bytes
