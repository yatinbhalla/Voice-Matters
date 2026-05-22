"""Local multilingual embeddings via sentence-transformers.

Uses paraphrase-multilingual-MiniLM-L12-v2 (384-dim, 50+ languages including
Hindi). First call downloads ~120 MB to ~/.cache/huggingface; thereafter
fully offline.
"""
import asyncio

import structlog

log = structlog.get_logger()

LOCAL_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LOCAL_DIM = 384

_model = None


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("local_embedder_loading", model=LOCAL_MODEL)
        _model = SentenceTransformer(LOCAL_MODEL)
        log.info("local_embedder_ready", dim=LOCAL_DIM)
    return _model


def _embed_sync(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    vectors = model.encode(
        texts, normalize_embeddings=True, show_progress_bar=False
    )
    return [v.tolist() for v in vectors]


async def embed(text: str) -> list[float]:
    vectors = await asyncio.to_thread(_embed_sync, [text])
    return vectors[0]


async def embed_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)
