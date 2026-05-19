import structlog

log = structlog.get_logger()


class EligibilityService:
    async def check(self, scheme_id: str, user_profile: dict):
        log.warning("eligibility_check_not_implemented", scheme_id=scheme_id)
        raise NotImplementedError
