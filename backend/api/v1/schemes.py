import structlog
from fastapi import APIRouter

log = structlog.get_logger()
router = APIRouter(tags=["schemes"])


@router.get("/schemes/{scheme_id}")
async def get_scheme(scheme_id: str):
    log.info("get_scheme_stub", scheme_id=scheme_id)
    return {"scheme_id": scheme_id, "status": "not_implemented"}


@router.get("/schemes/{scheme_id}/explain")
async def explain_scheme(scheme_id: str):
    log.info("explain_scheme_stub", scheme_id=scheme_id)
    return {"scheme_id": scheme_id, "explanation": None, "status": "not_implemented"}


@router.get("/schemes/{scheme_id}/apply-steps")
async def apply_steps(scheme_id: str):
    log.info("apply_steps_stub", scheme_id=scheme_id)
    return {"scheme_id": scheme_id, "steps": [], "status": "not_implemented"}
