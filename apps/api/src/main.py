import logging
import sys
import time
import uuid
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from apps.api.src.config import settings
from apps.api.src.routes.health import router as health_router
from apps.api.src.routes.ingestion import router as ingestion_router
from apps.api.src.routes.quality import router as quality_router
from apps.api.src.routes.etl import router as etl_router
from apps.api.src.routes.integrations import router as integrations_router
from apps.api.src.routes.kpis import router as kpi_router
from apps.api.src.routes.anomalies import router as anomaly_router
from apps.api.src.routes.ai import router as ai_router
from apps.api.src.routes.reports import router as reports_router
from apps.api.src.routes.operations import router as operations_router
from apps.api.src.schemas.common import APIEnvelope, APIError

# Structured logging configuration
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("eiap.api")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise Intelligence Automation Platform - Data Ingestion, Quality & BI Orchestration API",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_and_timing_middleware(request: Request, call_next):
    """
    Injects a correlation ID into every request context and logs request timing.
    """
    correlation_id = request.headers.get("X-Correlation-ID") or f"corr_{uuid.uuid4().hex[:12]}"
    request.state.correlation_id = correlation_id
    
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    response.headers["X-Correlation-ID"] = correlation_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"

    logger.info(
        f'{{"method":"{request.method}","path":"{request.url.path}","status":{response.status_code},"duration_ms":{duration_ms:.2f},"correlation_id":"{correlation_id}"}}'
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    detail = exc.detail
    code = "HTTP_ERROR"
    message = str(detail)
    field = None

    if isinstance(detail, dict):
        code = detail.get("code", code)
        message = detail.get("message", message)
        field = detail.get("field")

    return JSONResponse(
        status_code=exc.status_code,
        content=APIEnvelope(
            correlation_id=corr_id,
            status="ERROR",
            errors=[APIError(code=code, message=message, field=field)],
        ).model_dump(mode="json"),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    corr_id = getattr(request.state, "correlation_id", "unknown")
    errors = []
    for err in exc.errors():
        field_loc = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append(APIError(code="VALIDATION_ERROR", message=err.get("msg", "Invalid field"), field=field_loc))

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=APIEnvelope(
            correlation_id=corr_id,
            status="ERROR",
            errors=errors,
        ).model_dump(mode="json"),
    )


# Attach routers
app.include_router(health_router)
app.include_router(ingestion_router)
app.include_router(quality_router)
app.include_router(etl_router)
app.include_router(integrations_router)
app.include_router(kpi_router)
app.include_router(anomaly_router)
app.include_router(ai_router)
app.include_router(reports_router)
app.include_router(operations_router)

