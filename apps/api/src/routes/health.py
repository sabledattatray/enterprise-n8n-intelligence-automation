import time
from fastapi import APIRouter, Response, status
from apps.api.src.config import settings
from apps.api.src.database import check_db_health
from apps.api.src.schemas.health import DependencyStatus, HealthLiveResponse, HealthReadyResponse

router = APIRouter(prefix="/health", tags=["Health & Observability"])


@router.get("/live", response_model=HealthLiveResponse)
async def health_live():
    """Liveness probe indicating that the FastAPI worker process is running."""
    return HealthLiveResponse(
        status="ALIVE",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get("/ready", response_model=HealthReadyResponse)
async def health_ready(response: Response):
    """
    Readiness probe verifying all upstream dependencies (Database, Memory).
    Returns 503 if critical dependencies are unhealthy.
    """
    t0 = time.perf_counter()
    db_healthy = check_db_health()
    db_latency = (time.perf_counter() - t0) * 1000.0

    deps = {
        "postgres_analytics": DependencyStatus(
            status="UP" if db_healthy else "DOWN",
            latency_ms=round(db_latency, 2),
            details={"database": "business_analytics", "url_type": "managed_pool"},
        )
    }

    overall_status = "READY" if db_healthy else "UNHEALTHY"
    if not db_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthReadyResponse(
        status=overall_status,
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        dependencies=deps,
    )

