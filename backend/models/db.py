"""Async SQLAlchemy engine + session factory (asyncpg).

Lives under /models/ because everything that touches persistence imports
from here — keeps the model package self-contained. Normalizes the Neon
postgres URL: asyncpg driver, drops libpq-only sslmode/channel_binding
query params, sets ssl=True via connect_args.
"""
import os
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .base import Base

log = structlog.get_logger()

_DROP_PARAMS = {"sslmode", "channel_binding"}


def _normalize_url(raw: str, driver: str = "asyncpg") -> tuple[str, dict]:
    if not raw:
        return "", {}
    parts = urlsplit(raw)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = f"postgresql+{driver}"
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k not in _DROP_PARAMS]
    parts = parts._replace(scheme=scheme, query=urlencode(qs))
    connect_args: dict = {}
    if "sslmode=require" in raw or "neon.tech" in raw:
        connect_args["ssl"] = True
    return urlunsplit(parts), connect_args


def get_sync_url(raw: str | None = None) -> str:
    """Return a psycopg2-compatible URL (used by Alembic)."""
    raw = raw or os.getenv("DATABASE_URL", "")
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme
    if scheme in ("postgres", "postgresql"):
        scheme = "postgresql+psycopg2"
    elif scheme.startswith("postgresql+"):
        scheme = "postgresql+psycopg2"
    qs = [(k, v) for k, v in parse_qsl(parts.query) if k != "channel_binding"]
    parts = parts._replace(scheme=scheme, query=urlencode(qs))
    return urlunsplit(parts)


_url, _connect_args = _normalize_url(os.getenv("DATABASE_URL", ""))

engine = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None

if _url:
    engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Lightweight startup check. Schema is managed by Alembic; this just
    verifies the engine can connect."""
    if engine is None:
        log.warning("db_disabled_no_database_url")
        return
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        log.info("db_connected")
    except Exception as e:
        log.error("db_connect_failed", error=str(e))


__all__ = ["Base", "engine", "SessionLocal", "init_db", "get_sync_url"]
