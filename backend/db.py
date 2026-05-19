"""Async SQLAlchemy engine + session factory.

Normalizes the Neon postgres URL for asyncpg:
- Switches driver to `postgresql+asyncpg`.
- Drops libpq-only query params (sslmode, channel_binding) and passes
  ssl=True via connect_args instead.
"""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from models import Base

log = structlog.get_logger()

_DROP_PARAMS = {"sslmode", "channel_binding"}


def _normalize_url(raw: str) -> tuple[str, dict]:
    if not raw:
        return "", {}
    parts = urlsplit(raw)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+asyncpg"
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in _DROP_PARAMS]
    parts = parts._replace(scheme=scheme, query=urlencode(qs))
    connect_args: dict = {}
    if "sslmode=require" in raw or "neon.tech" in raw:
        connect_args["ssl"] = True
    return urlunsplit(parts), connect_args


_url, _connect_args = _normalize_url(os.getenv("DATABASE_URL", ""))

engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None

if _url:
    engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    if engine is None:
        log.warning("db_disabled_no_database_url")
        return
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log.info("db_initialized")
    except Exception as e:
        log.error("db_init_failed", error=str(e))
