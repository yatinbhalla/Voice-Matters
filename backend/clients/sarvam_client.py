import os
import structlog

log = structlog.get_logger()


class SarvamClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SARVAM_API_KEY")

    async def stt(self, audio_bytes: bytes, language: str = "hi-IN") -> str:
        log.warning("sarvam_stt_not_implemented", language=language)
        raise NotImplementedError("Sarvam STT not implemented")

    async def tts(self, text: str, language: str = "hi-IN") -> bytes:
        log.warning("sarvam_tts_not_implemented", language=language)
        raise NotImplementedError("Sarvam TTS not implemented")
