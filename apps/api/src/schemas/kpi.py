from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CategoryBreakdown(BaseModel):
    category: str
    revenue: float
    cost: float
    profit: float
    margin_pct: float
    order_count: int


class GeographyBreakdown(BaseModel):
    country_code: str
    region: str
    revenue: float
    profit: float
    order_count: int


class DailyTrend(BaseModel):
    date: str
    revenue: float
    orders: int
    profit: float


class KPIBreakdowns(BaseModel):
    by_category: List[CategoryBreakdown] = Field(default_factory=list)
    by_geography: List[GeographyBreakdown] = Field(default_factory=list)
    daily_trends: List[DailyTrend] = Field(default_factory=list)


class KPIComputeRequest(BaseModel):
    period_start: Optional[datetime] = Field(default=None, description="Start date for KPI aggregation window")
    period_end: Optional[datetime] = Field(default=None, description="End date for KPI aggregation window")
    currency_code: str = Field(default="USD", description="Currency filter for safe homogenous aggregation")
    source_run_id: Optional[UUID] = Field(default=None, description="Optional ingestion run to compute quality score from")


class KPISnapshotData(BaseModel):
    snapshot_id: UUID
    period_start: datetime
    period_end: datetime
    currency_code: str
    revenue: float
    cost: float
    profit: float
    margin_pct: float
    orders: int
    average_order_value: float
    cancellation_rate_pct: float
    quality_score: float
    computed_at: datetime
    source_run_id: Optional[UUID] = None
    breakdowns: KPIBreakdowns = Field(default_factory=KPIBreakdowns)


class AnomalyEventData(BaseModel):
    anomaly_id: UUID
    snapshot_id: UUID
    rule_id: str
    metric: str
    observed_value: float
    baseline_value: float
    deviation_pct: float
    severity: str
    status: str
    message: str
    created_at: datetime


class AnomalyEvaluationResult(BaseModel):
    snapshot_id: UUID
    anomalies_detected: int
    anomalies: List[AnomalyEventData] = Field(default_factory=list)
    summary_headline: str
    executive_alert_text: str

