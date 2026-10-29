from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class PowerBIRefreshRequest(BaseModel):
    dataset_id: str = Field(default="ds-default-enterprise-sales", description="Power BI Dataset / Semantic Model GUID or Name")
    workspace_id: Optional[str] = Field(default="ws-prod-analytics", description="Power BI Workspace GUID or Name")
    run_id: Optional[UUID] = Field(default=None, description="Associated Ingestion Run UUID for data lineage")
    simulate_failure: bool = Field(default=False, description="Simulate an upstream Power BI refresh failure (for resilience testing)")
    simulate_timeout: bool = Field(default=False, description="Simulate an upstream Power BI timeout condition")


class PowerBIRefreshResponse(BaseModel):
    refresh_id: str = Field(description="Unique refresh operation tracking ID")
    dataset_id: str = Field(description="Target Power BI Dataset ID")
    workspace_id: Optional[str] = Field(default=None, description="Target Power BI Workspace ID")
    run_id: Optional[UUID] = Field(default=None, description="Associated Ingestion Run UUID")
    status: str = Field(description="Refresh status: QUEUED, IN_PROGRESS, COMPLETED, FAILED, TIMED_OUT")
    submitted_at: datetime = Field(description="Timestamp when refresh was initiated")
    completed_at: Optional[datetime] = Field(default=None, description="Timestamp when refresh finished")
    attempts: int = Field(default=0, description="Number of poll attempts executed")
    idempotent_replay: bool = Field(default=False, description="True if an existing active/recent refresh was reused")
    error_message: Optional[str] = Field(default=None, description="Sanitized failure message if refresh failed")
    adapter_mode: str = Field(default="mock", description="Adapter execution mode: mock or real")

