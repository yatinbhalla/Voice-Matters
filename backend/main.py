import logging
import os
from pathlib import Path

import structlog
from dotenv import load_dotenv

load_dotenv()  # must run before any local import that reads env vars

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from api.v1 import router as v1_router  # noqa: E402
from db import init_db  # noqa: E402

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

app = FastAPI(title="Voice Matters - Sarkari Saathi", version="0.1.0")


@app.on_event("startup")
async def _startup() -> None:
    await init_db()


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    log.info("health_check")
    return {"status": "ok", "service": "sarkari-saathi", "version": "0.1.0"}


app.include_router(v1_router, prefix="/api/v1")
