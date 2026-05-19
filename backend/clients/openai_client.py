import os
import structlog

log = structlog.get_logger()


class OpenAIClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def chat(self, messages: list[dict], model: str = "gpt-4o-mini") -> str:
        log.warning("openai_chat_not_implemented", model=model)
        raise NotImplementedError("OpenAI chat not implemented")

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        log.warning("openai_embed_not_implemented", model=model)
        raise NotImplementedError("OpenAI embed not implemented")
