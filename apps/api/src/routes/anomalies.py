import logging
import uuid
from typing import List
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import AnomalyEvent
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.schemas.kpi import AnomalyEvaluationResult, AnomalyEventData
from apps.api.src.services.anomaly_service import AnomalyService

logger = logging.getLogger("eiap.routes.anomalies")

router = APIRouter(prefix="/v1/anomalies", tags=["Anomaly Detection & Alerting"])


@router.post(
    "/evaluate/{snapshot_id}",
    response_model=APIEnvelope[AnomalyEvaluationResult],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def evaluate_anomalies(
    snapshot_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Evaluates rule-based business anomalies against a materialized KPI snapshot.
    Detects revenue spikes, margin drops, and cancellation rate anomalies.
    Persists unsuppressed events into anomaly_events.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = AnomalyService(db)

    try:
        result = service.evaluate_anomalies(snapshot_id)
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=result,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SNAPSHOT_NOT_FOUND", "message": str(exc)},
        )
    except Exception as exc:
        logger.error(f"Anomaly evaluation failed for {snapshot_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "ANOMALY_EVALUATION_ERROR", "message": str(exc)},
        )


@router.get(
    "/open",
    response_model=APIEnvelope[List[AnomalyEventData]],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_open_anomalies(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Lists all unacknowledged OPEN business anomalies.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    rows = (
        db.query(AnomalyEvent)
        .filter(AnomalyEvent.status == "OPEN")
        .order_by(AnomalyEvent.created_at.desc())
        .limit(100)
        .all()
    )

    data = [
        AnomalyEventData(
            anomaly_id=r.anomaly_id,
            snapshot_id=r.snapshot_id,
            rule_id=r.rule_id,
            metric=r.metric,
            observed_value=float(r.observed_value),
            baseline_value=float(r.baseline_value),
            deviation_pct=round(
                ((float(r.observed_value) - float(r.baseline_value)) / float(r.baseline_value) * 100.0)
                if float(r.baseline_value) != 0.0
                else 0.0,
                2,
            ),
            severity=r.severity,
            status=r.status,
            message=f"{r.rule_id}: {r.metric} observed at {float(r.observed_value)} vs baseline {float(r.baseline_value)}",
            created_at=r.created_at,
        )
        for r in rows
    ]

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data=data,
    )
