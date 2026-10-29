import logging
import uuid
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import AISummary
from apps.api.src.schemas.ai import (
    AIExecutiveSummaryResponse,
    AIExecutiveSummarySections,
    AIInsightGenerationRequest,
    GroundingCheckResult,
)
from apps.api.src.schemas.common import APIEnvelope
from apps.api.src.services.ai_service import AIService

logger = logging.getLogger("eiap.routes.ai")

router = APIRouter(prefix="/v1/ai", tags=["AI Executive Intelligence"])


@router.post(
    "/generate",
    response_model=APIEnvelope[AIExecutiveSummaryResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def generate_ai_summary(
    payload: AIInsightGenerationRequest = AIInsightGenerationRequest(),
    request: Request = None,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Generates a grounded, hallucination-screened executive briefing from a KPI snapshot.
    Uses deterministic template generation by default (zero cost, zero external API keys).
    Supports optional OpenAI / Gemini integration with safe fallback.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    service = AIService(db)

    try:
        data = service.generate_summary(payload)
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
        logger.error(f"AI insight generation failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "AI_GENERATION_ERROR", "message": str(exc)},
        )


@router.get(
    "/latest",
    response_model=APIEnvelope[AIExecutiveSummaryResponse],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
)
async def get_latest_ai_summary(
    request: Request,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(None, alias="X-Correlation-ID"),
):
    """
    Retrieves the most recently generated and validated AI executive summary.
    """
    correlation_id = x_correlation_id or getattr(request.state, "correlation_id", f"corr_{uuid.uuid4().hex[:12]}")
    record = db.query(AISummary).order_by(AISummary.created_at.desc()).first()

    if not record:
        # If no summary exists yet, generate one on-demand for the latest snapshot
        service = AIService(db)
        data = service.generate_summary(AIInsightGenerationRequest())
        return APIEnvelope(
            correlation_id=correlation_id,
            status="SUCCESS",
            data=data,
        )

    sections = AIExecutiveSummarySections(**record.content_json)
    grounding = [GroundingCheckResult(**c) for c in (record.grounding_checks or [])]

    return APIEnvelope(
        correlation_id=correlation_id,
        status="SUCCESS",
        data=AIExecutiveSummaryResponse(
            summary_id=record.summary_id,
            snapshot_id=record.snapshot_id,
            model_provider=record.model_provider,
            model_name=record.model_name,
            prompt_version=record.prompt_version,
            sections=sections,
            validation_status=record.validation_status,
            grounding_checks=grounding,
            token_count=record.token_count,
            duration_ms=record.duration_ms,
            generated_at=record.created_at,
        ),
    )

