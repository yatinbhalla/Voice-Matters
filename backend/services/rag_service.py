"""RAG service: embed query -> Pinecone similarity search.

Returns chunks whose cosine similarity >= min_score (default 0.75).
If nothing crosses the bar the caller should treat that as low-confidence
and produce a refusal.
"""
from dataclasses import dataclass

import structlog

from clients.openai_client import EMBED_PROVIDER, OpenAIClient
from clients.pinecone_client import PineconeClient

log = structlog.get_logger()

# Cosine-similarity distributions differ between embedders. On our code-mixed
# Hindi-Roman + Devanagari corpus, text-embedding-3-small tops out around
# 0.45-0.55 for clear matches (English-only would be 0.70+); the local
# paraphrase-multilingual-MiniLM-L12-v2 scores 0.30-0.50. Default min_score
# adapts to whichever is active.
DEFAULT_MIN_SCORE = 0.40 if EMBED_PROVIDER == "openai" else 0.30


@dataclass
class Chunk:
    id: str
    score: float
    scheme_id: str
    scheme_name_hi: str
    scheme_name_en: str
    chunk_type: str
    source_url: str
    text: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "score": self.score,
            "scheme_id": self.scheme_id,
            "scheme_name_hi": self.scheme_name_hi,
            "scheme_name_en": self.scheme_name_en,
            "chunk_type": self.chunk_type,
            "source_url": self.source_url,
            "text": self.text,
        }


class RAGService:
    def __init__(self) -> None:
        self.oai = OpenAIClient()
        self.pc = PineconeClient()

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_score: float | None = None,
    ) -> list[Chunk]:
        if min_score is None:
            min_score = DEFAULT_MIN_SCORE
        if not query.strip():
            return []
        try:
            vector = await self.oai.embed(query)
        except Exception as e:
            log.error("rag_embed_failed", error=str(e))
            return []
        try:
            matches = await self.pc.query(vector, top_k=top_k)
        except Exception as e:
            log.error("rag_query_failed", error=str(e))
            return []

        chunks = [
            Chunk(
                id=m["id"],
                score=float(m["score"]),
                scheme_id=m["metadata"].get("scheme_id", ""),
                scheme_name_hi=m["metadata"].get("scheme_name_hi", ""),
                scheme_name_en=m["metadata"].get("scheme_name_en", ""),
                chunk_type=m["metadata"].get("chunk_type", ""),
                source_url=m["metadata"].get("source_url", ""),
                text=m["metadata"].get("text", ""),
            )
            for m in matches
        ]
        # "Top-anchor" retrieval: refuse if the TOP match doesn't clear the
        # query-relevance threshold (filters off-topic queries like Bitcoin).
        # When it does pass, we hand the LLM ALL top_k chunks rather than
        # only those individually above threshold — even chunks at 0.30 are
        # useful context once we know the query is in-scope, and the LLM
        # generates much better answers with 4-5 chunks than with 1.
        # Without this, queries that match a single intent chunk strongly
        # but have weaker supporting chunks cause the LLM to default to the
        # refusal template (it sees only one chunk and gives up).
        if not chunks or chunks[0].score < min_score:
            passing = []
        else:
            passing = [c for c in chunks if c.score >= 0.28][:top_k]
        log.info(
            "rag_retrieve",
            query_chars=len(query),
            returned=len(chunks),
            passing=len(passing),
            top_score=chunks[0].score if chunks else None,
        )
        return passing
