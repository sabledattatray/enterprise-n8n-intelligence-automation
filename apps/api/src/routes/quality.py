import uuid
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.schemas.common import APIEnvelope, APIError
from apps.api.src.services.quality_service import validate_run_batch

router = APIRouter(prefix="/v1/quality", tags=["Data Quality"])


class QualityValidateResponse(BaseModel):
    run_id: str
    source: str
    batch_id: str
    total_records: int
    accepted_rows: int
    duplicate_rows: int
    rejected_rows: int
    quality_score: float
    gate_status: str
    sample_rejections: List[Dict[str, str]]


@router.post(
    "/validate/{run_id}",
    response_model=APIEnvelope[QualityValidateResponse],
    dependencies=[Depends(verify_api_key)],
)
async def validate_batch(
    run_id: str,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}"),
):
    """
    Executes business quality gates for all raw records in a specific run.
    Quarantines rejects with sanitized reasons, marks duplicates, and updates run ledger.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_UUID", "message": f"Malformed run UUID '{run_id}'"},
        )

    try:
        result = validate_run_batch(db, run_uuid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "RUN_NOT_FOUND", "message": str(e)},
        )

    errors = []
    if result["gate_status"] == "BLOCKED":
        errors.append(
            APIError(
                code="QUALITY_GATE_BLOCKED",
                message=f"Quality score {result['quality_score']}% is below the required 50% threshold.",
            )
        )

    return APIEnvelope(
        correlation_id=x_correlation_id,
        status="SUCCESS" if result["gate_status"] == "PASSED" else "PARTIAL_SUCCESS",
        data=QualityValidateResponse(**result),
        errors=errors,
    )

