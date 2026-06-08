import logging
import os
import re
from pathlib import Path

import structlog
from dotenv import load_dotenv

load_dotenv()  # must run before any local import that reads env vars

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.v1 import router as v1_router  # noqa: E402
from models.db import init_db  # noqa: E402

STATIC_DIR = Path(__file__).resolve().parent / "static"
(STATIC_DIR / "audio").mkdir(parents=True, exist_ok=True)

structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)
log = structlog.get_logger()

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:8000")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

app = FastAPI(title="Voice Matters - Sarkari Saathi", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    await init_db()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# Cache-Control on generated TTS audio files so the service worker (and
# any intermediate proxy) can re-serve them without hitting the backend.
# 24h is a safe ceiling - the filename includes a uuid so we never need
# to invalidate, and the corpus is small enough that disk pressure isn't
# a concern.
@app.middleware("http")
async def add_audio_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/audio/"):
        response.headers["Cache-Control"] = "public, max-age=86400, immutable"
    return response

# CORS: accept localhost (dev), the configured FRONTEND_ORIGIN, AND any
# voice-matters-* domain on render.com. The regex catch-all is the
# resilience layer — if FRONTEND_ORIGIN gets reset or has a typo in the
# Render dashboard, the static site at voice-matters-web.onrender.com
# still works. Doesn't broaden the attack surface meaningfully because
# our endpoints have no auth + the project naming pattern is unique.
_default_allowed = re.escape(FRONTEND_ORIGIN) if FRONTEND_ORIGIN else ""
_cors_regex = (
    r"^https?://("
    r"localhost(:\d+)?"
    r"|127\.0\.0\.1(:\d+)?"
    r"|voice-matters[a-zA-Z0-9_-]*\.onrender\.com"
    + (rf"|{_default_allowed.replace('https://','').replace('http://','')}"
       if _default_allowed else "")
    + r")$"
)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=_cors_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    log.info("health_check")
    return {"status": "ok", "service": "sarkari-saathi", "version": "0.1.0"}


app.include_router(v1_router, prefix="/api/v1")
