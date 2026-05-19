import os
import structlog

log = structlog.get_logger()


class PineconeClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.index_name = os.getenv("PINECONE_INDEX_NAME", "voice-matters-schemes")

    async def query(self, vector: list[float], top_k: int = 5, filter: dict | None = None):
        log.warning("pinecone_query_not_implemented", index=self.index_name)
        raise NotImplementedError("Pinecone query not implemented")

    async def upsert(self, records: list[dict]):
        log.warning("pinecone_upsert_not_implemented", index=self.index_name)
        raise NotImplementedError("Pinecone upsert not implemented")
