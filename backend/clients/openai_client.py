"""Embeddings client. Dispatches to OpenAI or a local sentence-transformer
based on EMBED_PROVIDER (default: local).

OpenAIClient.embed / embed_batch is the single public surface used by the
RAG service and the ingest script. EMBED_DIM is read at import time so
PineconeClient sizes the index correctly.
"""
import os

import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from clients.local_embedder import LOCAL_DIM
from clients.local_embedder import embed as local_embed
from clients.local_embedder import embed_batch as local_embed_batch

log = structlog.get_logger()

EMBED_PROVIDER = os.getenv("EMBED_PROVIDER", "local").lower()
OPENAI_EMBED_MODEL = "text-embedding-3-small"
OPENAI_EMBED_DIM = 1536


def _embed_dim() -> int:
    return OPENAI_EMBED_DIM if EMBED_PROVIDER == "openai" else LOCAL_DIM


EMBED_DIM = _embed_dim()
log.info("embed_provider_selected", provider=EMBED_PROVIDER, dim=EMBED_DIM)


class OpenAIClient:
    """Misnomer kept for compatibility - this is the embeddings client and
    transparently falls back to local sentence-transformers when
    EMBED_PROVIDER=local (default while we're on a free tier)."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self._client = None
        if EMBED_PROVIDER == "openai":
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    def _require_openai(self) -> None:
        if self._client is None:
            raise RuntimeError("OPENAI_API_KEY not set (EMBED_PROVIDER=openai)")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def embed(self, text: str) -> list[float]:
        if EMBED_PROVIDER == "openai":
            self._require_openai()
            resp = await self._client.embeddings.create(
                model=OPENAI_EMBED_MODEL, input=[text]
            )
            return resp.data[0].embedding
        return await local_embed(text)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
    )
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if EMBED_PROVIDER == "openai":
            self._require_openai()
            resp = await self._client.embeddings.create(
                model=OPENAI_EMBED_MODEL, input=texts
            )
            return [d.embedding for d in resp.data]
        return await local_embed_batch(texts)
