import structlog
from fastapi import APIRouter

log = structlog.get_logger()
router = APIRouter(tags=["admin"])


@router.get("/admin/trust-metrics")
async def trust_metrics():
    log.info("trust_metrics_stub")
    return {"metrics": {}, "status": "not_implemented"}
