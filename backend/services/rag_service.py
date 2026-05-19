import structlog

log = structlog.get_logger()


class RAGService:
    async def retrieve(self, query: str, top_k: int = 5):
        log.warning("rag_retrieve_not_implemented")
        raise NotImplementedError
