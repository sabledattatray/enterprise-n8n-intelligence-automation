import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.services.etl_service import commit_etl_run

router = APIRouter(prefix="/v1/etl", tags=["Transactional ETL"])


class ETLCommitResponse(BaseModel):
    run_id: str
    status: str
    facts_upserted: int
    dimensions_loaded: int
    duration_ms: int


@router.post(
    "/commit/{run_id}",
    response_model=APIEnvelope[ETLCommitResponse],
    dependencies=[Depends(verify_api_key)],
)
async def commit_batch(
    run_id: str,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}"),
):
    """
    Executes atomic transactional dimension loading and fact_orders upserts for a validated run.
    """
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_UUID", "message": f"Malformed run UUID '{run_id}'"},
        )

    try:
        result = commit_etl_run(db, run_uuid, x_correlation_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "ETL_PRECONDITION_FAILED", "message": str(e)},
        )

    return APIEnvelope(
        correlation_id=x_correlation_id,
        status="SUCCESS",
        data=ETLCommitResponse(**result),
    )

