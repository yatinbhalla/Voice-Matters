"""Audio normalization: re-encode any input to wav 16kHz mono via ffmpeg.

ffmpeg is the only realistic option for cross-format transcode on a backend
that accepts mp3/wav/webm. If ffmpeg isn't on PATH we pass the bytes through
unchanged — Sarvam Saaras accepts mp3/wav natively, so this degrades to
"works for mp3/wav, fails for webm" rather than failing outright.
"""
import asyncio
import shutil
import uuid
from pathlib import Path

import structlog

log = structlog.get_logger()

TMP_DIR = Path("/tmp") if Path("/tmp").exists() else Path.cwd() / ".tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)


def _ext_for(content_type: str | None, filename: str | None) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    if content_type:
        ct = content_type.lower()
        if "webm" in ct:
            return "webm"
        if "mpeg" in ct or "mp3" in ct:
            return "mp3"
        if "wav" in ct or "wave" in ct:
            return "wav"
        if "ogg" in ct:
            return "ogg"
    return "bin"


async def save_and_normalize(
    audio_bytes: bytes, content_type: str | None, filename: str | None
) -> tuple[bytes, str, str]:
    """Persist raw upload to /tmp/<uuid>.<ext>; return (normalized_bytes, mime, filename).

    If ffmpeg is available, normalized output is wav 16k mono. Otherwise we
    return the input bytes with their original mime.
    """
    ext = _ext_for(content_type, filename)
    uid = uuid.uuid4().hex
    raw_path = TMP_DIR / f"{uid}.{ext}"
    raw_path.write_bytes(audio_bytes)

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        log.warning("ffmpeg_missing_passthrough", ext=ext)
        return audio_bytes, content_type or "application/octet-stream", raw_path.name

    # Distinct output name so ffmpeg never aliases input (refuses in-place edits)
    wav_path = TMP_DIR / f"{uid}.norm.wav"
    proc = await asyncio.create_subprocess_exec(
        ffmpeg,
        "-y",
        "-i",
        str(raw_path),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        str(wav_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0 or not wav_path.exists():
        log.warning(
            "ffmpeg_failed_passthrough",
            returncode=proc.returncode,
            stderr=stderr.decode(errors="ignore")[-400:],
        )
        return audio_bytes, content_type or "application/octet-stream", raw_path.name

    return wav_path.read_bytes(), "audio/wav", wav_path.name
