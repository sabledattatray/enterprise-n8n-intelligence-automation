import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import ReportDispatch
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.schemas.reports import ReportDispatchRequest, ReportDispatchResponse
from apps.api.src.services.report_service import ReportService

logger = logging.getLogger("eiap.routes.reports")

router = APIRouter(prefix="/v1/reports", tags=["Executive Reporting & Distribution"])


@router.post(
    "/dispatch",
    response_model=APIEnvelope[ReportDispatchResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def dispatch_report(
    payload: ReportDispatchRequest = ReportDispatchRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Renders and dispatches the responsive HTML executive report to Mailpit.
    Enforces dispatch idempotency based on report_id + recipient_hash.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = ReportService(db)

    try:
        data = service.dispatch_report(payload, correlation_id)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SNAPSHOT_NOT_FOUND", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"Report dispatch failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "REPORT_DISPATCH_ERROR", "message": str(exc)},
        )


@router.get(
    "/history",
    response_model=APIEnvelope[List[ReportDispatchResponse]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_report_dispatch_history(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Retrieves the audit log of all report distribution attempts.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    records = db.query(ReportDispatch).order_by(ReportDispatch.created_at.desc()).limit(50).all()

    data = [
        ReportDispatchResponse(
            dispatch_id=r.dispatch_id,
            report_id=r.report_id,
            recipient=(r.metadata_json or {}).get("recipient", "executive-leadership@internal.local"),
            recipient_hash=r.recipient_hash,
            channel=r.channel,
            subject=r.subject or "EIAP Executive Report",
            status=r.status,
            idempotent_replay=False,
            attempts=r.attempts,
            sent_at=r.sent_at,
            smtp_target="Mailpit Local Catcher",
        )
        for r in records
    ]

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data=data,
    )

