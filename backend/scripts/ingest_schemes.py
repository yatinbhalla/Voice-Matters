"""One-shot scheme ingestion: processed JSON -> OpenAI embeddings -> Pinecone + schemes_meta.

Usage:
  cd backend
  .venv/Scripts/python.exe scripts/ingest_schemes.py

Reads /scheme-corpus/schemes/processed/*.json. Chunks of ~500 tokens are
embedded with text-embedding-3-small (1536-dim) and upserted to the
Pinecone index. Each scheme's headline metadata is also written to the
schemes_meta Postgres table.

Idempotent: re-running upserts (same ids) and uses INSERT ... ON CONFLICT
DO UPDATE for schemes_meta.
"""
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

import structlog  # noqa: E402
from sqlalchemy import text  # noqa: E402

from clients.openai_client import OpenAIClient  # noqa: E402
from clients.pinecone_client import PineconeClient  # noqa: E402
from models.db import SessionLocal  # noqa: E402

log = structlog.get_logger()

CORPUS_DIR = BACKEND_DIR.parent / "scheme-corpus" / "schemes" / "processed"

# Rough heuristic: a 500-token chunk is ~2000 chars for English/transliterated
# Hindi mixed content. Our authored chunks sit well under this; we only split
# if a chunk exceeds the limit.
SOFT_CHAR_LIMIT = 2000


def _split_long(text_: str, limit: int = SOFT_CHAR_LIMIT) -> list[str]:
    if len(text_) <= limit:
        return [text_]
    # Sentence-greedy split.
    parts: list[str] = []
    current = ""
    for sentence in text_.replace("?", "?.").replace("!", "!.").split(". "):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = (current + ". " + sentence).strip(". ")
        if len(candidate) > limit and current:
            parts.append(current.strip())
            current = sentence
        else:
            current = candidate
    if current:
        parts.append(current.strip())
    return parts


def load_schemes() -> list[dict]:
    out: list[dict] = []
    for path in sorted(CORPUS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            out.append(json.load(f))
    return out


async def upsert_scheme_meta(scheme: dict) -> None:
    if SessionLocal is None:
        log.warning("schemes_meta_skipped_no_db", scheme_id=scheme["scheme_id"])
        return
    sql = text(
        """
        INSERT INTO schemes_meta
          (scheme_id, name, ministry, summary, source_url, tags, updated_at)
        VALUES
          (:scheme_id, :name, :ministry, :summary, :source_url, CAST(:tags AS json), now())
        ON CONFLICT (scheme_id) DO UPDATE SET
          name = EXCLUDED.name,
          ministry = EXCLUDED.ministry,
          summary = EXCLUDED.summary,
          source_url = EXCLUDED.source_url,
          tags = EXCLUDED.tags,
          updated_at = now()
        """
    )
    async with SessionLocal() as session:
        await session.execute(
            sql,
            {
                "scheme_id": scheme["scheme_id"],
                "name": scheme["name_en"],
                "ministry": scheme.get("ministry"),
                "summary": scheme.get("summary_hi"),
                "source_url": scheme.get("source_url"),
                "tags": json.dumps(scheme.get("tags", [])),
            },
        )
        await session.commit()


async def main(reset_index: bool = False) -> int:
    schemes = load_schemes()
    if not schemes:
        log.error("no_schemes_found", path=str(CORPUS_DIR))
        return 1

    oai = OpenAIClient()
    pc = PineconeClient()
    if reset_index:
        await pc.delete_index()
    await pc.ensure_index()

    total_chunks = 0
    for scheme in schemes:
        chunks_to_embed: list[tuple[str, str, dict]] = []
        for chunk in scheme["chunks"]:
            for i, piece in enumerate(_split_long(chunk["text"])):
                chunk_id = f"{scheme['scheme_id']}::{chunk['id']}"
                if i:
                    chunk_id = f"{chunk_id}::p{i}"
                metadata = {
                    "scheme_id": scheme["scheme_id"],
                    "chunk_type": chunk.get("chunk_type", "general"),
                    "source_url": scheme.get("source_url", ""),
                    "scheme_name_hi": scheme["name_hi"],
                    "scheme_name_en": scheme["name_en"],
                    "language": chunk.get("language", "hi-en"),
                    "text": piece,
                }
                chunks_to_embed.append((chunk_id, piece, metadata))

        texts = [c[1] for c in chunks_to_embed]
        log.info("embedding_chunks", scheme=scheme["scheme_id"], n=len(texts))
        vectors_raw = await oai.embed_batch(texts)
        vectors = [
            {"id": chunks_to_embed[i][0], "values": vectors_raw[i],
             "metadata": chunks_to_embed[i][2]}
            for i in range(len(chunks_to_embed))
        ]
        await pc.upsert(vectors)
        await upsert_scheme_meta(scheme)
        total_chunks += len(vectors)
        log.info("scheme_ingested", scheme=scheme["scheme_id"], chunks=len(vectors))

    stats = await pc.index_stats()
    log.info(
        "ingest_complete",
        schemes=len(schemes),
        chunks=total_chunks,
        index_vector_count=stats.get("total_vector_count"),
    )
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reset-index",
        action="store_true",
        help="Delete the Pinecone index before re-creating (use when changing embedding dim).",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(reset_index=args.reset_index)))
