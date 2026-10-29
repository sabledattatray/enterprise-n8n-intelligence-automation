import logging
import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import OperationalIncident
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.schemas.operations import (
    IncidentRecordRequest,
    IncidentResolutionRequest,
    IncidentResponse,
)
from apps.api.src.services.incident_service import IncidentService

logger = logging.getLogger("eiap.routes.operations")

router = APIRouter(prefix="/v1/operations", tags=["Operations & Resilience"])


@router.post(
    "/incidents",
    response_model=APIEnvelope[IncidentResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def record_incident(
    payload: IncidentRecordRequest,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Records an operational workflow failure, classifies failure category,
    computes bounded backoff with jitter, and logs the incident.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = IncidentService(db)

    try:
        data = service.record_incident(payload, correlation_id)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except Exception as exc:
        logger.error(f"Failed to record incident: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INCIDENT_RECORD_ERROR", "message": str(exc)},
        )


@router.get(
    "/incidents",
    response_model=APIEnvelope[List[IncidentResponse]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def list_incidents(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Lists operational incidents, ordered by most recent.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    records = db.query(OperationalIncident).order_by(OperationalIncident.created_at.desc()).limit(100).all()

    data = [
        IncidentResponse(
            incident_id=r.incident_id,
            workflow_name=r.workflow_name,
            execution_id=r.execution_id,
            correlation_id=r.correlation_id,
            failure_category=r.failure_category,
            severity=r.severity,
            status=r.status,
            error_code=r.error_code,
            error_message=r.error_message,
            retry_count=r.retry_count,
            max_retries=r.max_retries,
            eligible_for_retry=(r.status in ("OPEN", "RETRIED") and r.retry_count < r.max_retries),
            suggested_backoff_seconds=None,
            created_at=r.created_at,
            last_retried_at=r.last_retried_at,
            resolved_at=r.resolved_at,
        )
        for r in records
    ]

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data=data,
    )


@router.post(
    "/incidents/{incident_id}/retry",
    response_model=APIEnvelope[IncidentResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def retry_incident(
    incident_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Triggers an operational retry on an eligible incident with exponential backoff calculation.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = IncidentService(db)

    try:
        data = service.retry_incident(incident_id)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INCIDENT_NOT_FOUND", "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RETRY_NOT_PERMITTED", "message": str(exc)},
        )


@router.post(
    "/incidents/{incident_id}/delayed-retry",
    response_model=APIEnvelope[IncidentResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def delayed_retry_incident(
    incident_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Executes a delayed retry strictly after the scheduled backoff interval has elapsed.
    Rejects premature attempts with HTTP 429 Backoff Active.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = IncidentService(db)

    try:
        data = service.execute_delayed_retry(incident_id, force=False)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INCIDENT_NOT_FOUND", "message": str(exc)},
        )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "BACKOFF_ACTIVE", "message": str(exc)},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "RETRY_NOT_PERMITTED", "message": str(exc)},
        )


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=APIEnvelope[IncidentResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def resolve_incident(
    incident_id: uuid.UUID,
    payload: IncidentResolutionRequest = IncidentResolutionRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Marks an operational incident as RESOLVED.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = IncidentService(db)

    try:
        data = service.resolve_incident(incident_id, payload.resolution_note)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "INCIDENT_NOT_FOUND", "message": str(exc)},
        )


@router.get(
    "/health",
    response_model=APIEnvelope[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_operational_health(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Aggregates operational resilience and health metrics across the platform.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    total_incidents = db.query(OperationalIncident).count()
    open_incidents = db.query(OperationalIncident).filter(OperationalIncident.status == "OPEN").count()
    critical_incidents = (
        db.query(OperationalIncident)
        .filter(OperationalIncident.severity == "CRITICAL", OperationalIncident.status.in_(["OPEN", "RETRIED"]))
        .count()
    )
    dead_letter_count = db.query(OperationalIncident).filter(OperationalIncident.status == "DEAD_LETTER").count()

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data={
            "platform_status": "HEALTHY" if critical_incidents == 0 else "DEGRADED",
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "critical_open_incidents": critical_incidents,
            "dead_letter_incidents": dead_letter_count,
        },
    )

