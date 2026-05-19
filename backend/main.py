import logging
import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from api.v1 import router as v1_router

load_dotenv()

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
