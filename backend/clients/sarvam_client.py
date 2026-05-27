"""Sarvam AI client: Saaras STT, Mayura LLM, Bulbul TTS.

httpx.AsyncClient + tenacity (3 retries, exponential backoff). All methods
raise RuntimeError when SARVAM_API_KEY is missing so callers can fail-soft.
"""
import base64
import os
import re

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Sarvam-m is a reasoning model: it emits its chain-of-thought inside
# <think>...</think> before the final answer. We never want that surfaced
# to the user or pushed into TTS.
_THINK_TAG_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)


def _truncate_for_tts(text: str, limit: int = 450) -> str:
    """Trim TTS input at a sentence boundary <= limit chars.

    Sarvam Bulbul returns 400 on inputs > ~500 chars. We aim for 450 with
    headroom. Prefer to cut at the last `.` / `।` / `\n` so the audio
    doesn't end mid-word.
    """
    if not text or len(text) <= limit:
        return text or ""
    head = text[:limit]
    # Walk back to the most recent sentence terminator.
    for sep in ("\n", "। ", "। ", ". ", "!", "?"):
        idx = head.rfind(sep)
        if idx >= int(limit * 0.6):  # don't cut too early
            return head[: idx + len(sep)].rstrip()
    return head.rstrip() + "…"

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
        raw = choices[0].get("message", {}).get("content", "")
        # Strip reasoning blocks; also handle an unterminated <think> if the
        # model truncated mid-trace.
        cleaned = _THINK_TAG_RE.sub("", raw)
        if "<think>" in cleaned:
            cleaned = cleaned.split("</think>", 1)[-1]
        return cleaned.strip()

    @retry(**_RETRY)
    async def synthesize(
        self,
        text: str,
        voice: str = "anushka",
        target_language_code: str = "hi-IN",
        model: str = "bulbul:v2",
        sample_rate: int = 22050,
    ) -> bytes:
        """sample_rate=8000 is used for the 2G low-bandwidth mode; default
        22050 is the studio-quality setting we use otherwise.

        Sarvam Bulbul has a ~500 char ceiling per `inputs` entry. We
        truncate at the last sentence-ish boundary before that limit so
        long LLM answers don't 400.
        """
        self._require_key()
        text = _truncate_for_tts(text, limit=450)
        body = {
            "inputs": [text],
            "target_language_code": target_language_code,
            "speaker": voice,
            "model": model,
            "speech_sample_rate": sample_rate,
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
