import structlog

log = structlog.get_logger()


class AnswerService:
    async def answer(self, question: str, context: list[dict] | None = None):
        log.warning("answer_not_implemented")
        raise NotImplementedError
