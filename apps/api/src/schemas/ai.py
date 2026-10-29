from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AIExecutiveSummarySections(BaseModel):
    business_overview: str = Field(description="High-level performance overview against baseline targets")
    revenue_profitability: str = Field(description="Revenue, total cost, gross profit, and margin analysis")
    order_performance: str = Field(description="Order volume, average order value (AOV), and cancellation trends")
    product_geography_insights: str = Field(description="Key category and regional contributors")
    detected_anomalies: str = Field(description="Grounded summary of statistical and rule-based anomaly events")
    operational_observations: str = Field(description="Data quality score, ingestion health, and operational notes")
    investigation_priorities: List[str] = Field(default_factory=list, description="Actionable priorities for leadership")


class GroundingCheckResult(BaseModel):
    metric_name: str
    cited_value: float
    expected_value: float
    is_grounded: bool
    tolerance: float = 0.05


class AIInsightGenerationRequest(BaseModel):
    snapshot_id: Optional[UUID] = Field(default=None, description="Target KPI snapshot UUID (defaults to latest)")
    provider: Optional[str] = Field(default="mock", description="AI provider: mock, openai, or gemini")
    force_fallback: bool = Field(default=False, description="Simulate AI outage or grounding failure to test fallback")


class AIExecutiveSummaryResponse(BaseModel):
    summary_id: UUID
    snapshot_id: UUID
    model_provider: str
    model_name: str
    prompt_version: str
    sections: AIExecutiveSummarySections
    validation_status: str  # VALIDATED, FALLBACK_GENERATED, GROUNDING_BREACH
    grounding_checks: List[GroundingCheckResult] = Field(default_factory=list)
    token_count: Optional[int] = None
    duration_ms: Optional[int] = None
    generated_at: datetime

