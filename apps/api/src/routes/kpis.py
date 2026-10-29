import logging
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import KPISnapshot
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.schemas.kpi import KPIComputeRequest, KPISnapshotData
from apps.api.src.services.kpi_service import KPIService

logger = logging.getLogger("eiap.routes.kpis")

router = APIRouter(prefix="/v1/kpis", tags=["KPIs & Analytics"])


@router.post(
    "/compute",
    response_model=APIEnvelope[KPISnapshotData],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def compute_kpis(
    payload: KPIComputeRequest = KPIComputeRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Computes enterprise revenue, cost, gross profit, margin %, order counts,
    AOV, cancellation rate, and multi-dimensional breakdowns via parameterized SQL.
    Materializes the calculated snapshot into the kpi_snapshots table.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = KPIService(db)

    try:
        data = service.compute_kpis(payload)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )
    except Exception as exc:
        logger.error(f"KPI computation failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "KPI_COMPUTATION_ERROR", "message": str(exc)},
        )


@router.get(
    "/latest",
    response_model=APIEnvelope[KPISnapshotData],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_latest_kpi_snapshot(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Retrieves the most recently computed and materialized KPI snapshot.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    snapshot = db.query(KPISnapshot).order_by(KPISnapshot.computed_at.desc()).first()

    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NO_SNAPSHOT_FOUND", "message": "No KPI snapshots have been materialized yet."},
        )

    # Re-compute detailed view for the snapshot period
    service = KPIService(db)
    data = service.compute_kpis(
        KPIComputeRequest(
            period_start=snapshot.period_start,
            period_end=snapshot.period_end,
            currency_code=snapshot.currency_code,
            source_run_id=snapshot.source_run_id,
        )
    )

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data=data,
    )

