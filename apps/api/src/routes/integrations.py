import logging
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.adapters.powerbi_adapter import get_powerbi_adapter
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.schemas.common import APIEnvelope, APIError
from apps.api.src.schemas.integrations import PowerBIRefreshRequest, PowerBIRefreshResponse

logger = logging.getLogger("eiap.integrations")

router = APIRouter(prefix="/v1/integrations", tags=["Integrations & BI Orchestration"])


@router.post(
    "/powerbi/refresh",
    response_model=APIEnvelope[PowerBIRefreshResponse],
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(verify_api_key)],
)
async def trigger_powerbi_refresh(
    payload: PowerBIRefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Submits a Power BI dataset refresh request.
    In development and CI mode, executes via deterministic Mock adapter.
    In production mode with credentials, delegates to Microsoft Power BI REST API.
    Supports idempotent deduplication on active refreshes.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    adapter = get_powerbi_adapter()

    try:
        result = await adapter.trigger_refresh(payload, correlation_id, db)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=result,
        )
    except Exception as exc:
        logger.error(f"Failed to submit Power BI refresh: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "POWERBI_INTEGRATION_ERROR", "message": str(exc)},
        )


@router.get(
    "/powerbi/refresh/{refresh_id}",
    response_model=APIEnvelope[PowerBIRefreshResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_powerbi_refresh_status(
    refresh_id: str,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Polls the current status of an asynchronous Power BI dataset refresh operation.
    Transitions through IN_PROGRESS to COMPLETED or FAILED.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    adapter = get_powerbi_adapter()

    try:
        result = await adapter.get_refresh_status(refresh_id, correlation_id, db)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=result,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REFRESH_NOT_FOUND", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"Failed to poll Power BI refresh {refresh_id}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "POWERBI_POLL_ERROR", "message": str(exc)},
        )

