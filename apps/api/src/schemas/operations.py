from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class IncidentRecordRequest(BaseModel):
    workflow_name: str = Field(description="Name of the failing workflow")
    execution_id: Optional[str] = Field(default=None, description="n8n execution ID")
    correlation_id: Optional[str] = Field(default=None, description="Traceability correlation ID")
    error_code: str = Field(description="Normalized error code, e.g. HTTP_502, AUTH_FORBIDDEN, TIMEOUT")
    error_message: str = Field(description="Sanitized failure description")
    failure_category: Optional[str] = Field(default=None, description="TRANSIENT, PERMANENT, AUTH, VALIDATION, INFRASTRUCTURE")
    error_details: Dict[str, Any] = Field(default_factory=dict, description="Structured failure context")


class IncidentResponse(BaseModel):
    incident_id: UUID
    workflow_name: str
    execution_id: Optional[str]
    correlation_id: str
    failure_category: str
    severity: str
    status: str  # OPEN, RETRIED, RESOLVED, DEAD_LETTER
    error_code: str
    error_message: str
    retry_count: int
    max_retries: int
    eligible_for_retry: bool
    suggested_backoff_seconds: Optional[float] = None
    created_at: datetime
    last_retried_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class IncidentResolutionRequest(BaseModel):
    resolution_note: str = Field(default="Resolved by operator investigation", description="Operational resolution note")

