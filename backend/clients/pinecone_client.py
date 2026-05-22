"""Pinecone client wrapper.

The Pinecone SDK is sync; we run blocking calls in a thread so the rest of
the request handler stays async-friendly.
"""
import asyncio
import os
from typing import Any

import structlog
from pinecone import Pinecone, ServerlessSpec

from clients.openai_client import EMBED_DIM as _EMBED_DIM


def _dim() -> int:
    return _EMBED_DIM

log = structlog.get_logger()

DEFAULT_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
DEFAULT_REGION = os.getenv("PINECONE_REGION", "us-east-1")


class PineconeClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("PINECONE_API_KEY", "")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "voice-matters-schemes")
        self._pc = Pinecone(api_key=self.api_key) if self.api_key else None
        self._index = None

    def _require(self) -> None:
        if self._pc is None:
            raise RuntimeError("PINECONE_API_KEY not set")

    def _ensure_index_sync(self) -> Any:
        self._require()
        dim = _dim()
        names = [i.name for i in self._pc.list_indexes()]
        if self.index_name in names:
            # If an existing index has a different dimension, refuse and
            # tell the caller to reset — vector dims aren't mutable.
            existing = self._pc.describe_index(self.index_name)
            existing_dim = (
                existing["dimension"] if isinstance(existing, dict) else existing.dimension
            )
            if existing_dim != dim:
                raise RuntimeError(
                    f"Pinecone index '{self.index_name}' has dim={existing_dim}, "
                    f"but EMBED_PROVIDER expects dim={dim}. "
                    "Re-run ingest with --reset-index to drop and recreate."
                )
        else:
            log.info("pinecone_creating_index", name=self.index_name, dim=dim)
            self._pc.create_index(
                name=self.index_name,
                dimension=dim,
                metric="cosine",
                spec=ServerlessSpec(cloud=DEFAULT_CLOUD, region=DEFAULT_REGION),
            )
        if self._index is None:
            self._index = self._pc.Index(self.index_name)
        return self._index

    async def ensure_index(self) -> None:
        await asyncio.to_thread(self._ensure_index_sync)

    def _delete_index_sync(self) -> None:
        self._require()
        names = [i.name for i in self._pc.list_indexes()]
        if self.index_name in names:
            log.info("pinecone_deleting_index", name=self.index_name)
            self._pc.delete_index(self.index_name)
            self._index = None

    async def delete_index(self) -> None:
        await asyncio.to_thread(self._delete_index_sync)

    async def upsert(self, vectors: list[dict]) -> dict:
        """vectors: [{id, values, metadata}, ...]"""
        index = await asyncio.to_thread(self._ensure_index_sync)
        return await asyncio.to_thread(index.upsert, vectors=vectors)

    async def query(
        self,
        vector: list[float],
        top_k: int = 5,
        filter: dict | None = None,
        include_metadata: bool = True,
    ) -> list[dict]:
        index = await asyncio.to_thread(self._ensure_index_sync)
        resp = await asyncio.to_thread(
            index.query,
            vector=vector,
            top_k=top_k,
            include_metadata=include_metadata,
            filter=filter,
        )
        matches = resp.get("matches") if isinstance(resp, dict) else resp.matches
        out: list[dict] = []
        for m in matches or []:
            md = m.metadata if hasattr(m, "metadata") else m.get("metadata", {})
            out.append(
                {
                    "id": m.id if hasattr(m, "id") else m["id"],
                    "score": m.score if hasattr(m, "score") else m["score"],
                    "metadata": md or {},
                }
            )
        return out

    async def index_stats(self) -> dict:
        index = await asyncio.to_thread(self._ensure_index_sync)
        stats = await asyncio.to_thread(index.describe_index_stats)
        return stats if isinstance(stats, dict) else stats.to_dict()
