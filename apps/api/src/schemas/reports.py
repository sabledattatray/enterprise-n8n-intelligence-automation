from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ReportDispatchRequest(BaseModel):
    snapshot_id: Optional[UUID] = Field(default=None, description="Target KPI snapshot UUID (defaults to latest)")
    recipient_email: str = Field(default="executive-leadership@internal.local", description="Recipient email address")
    channel: str = Field(default="EMAIL", description="Dispatch channel: EMAIL, WEBHOOK, or SLACK")
    force_resend: bool = Field(default=False, description="Bypass dispatch deduplication")


class ReportDispatchResponse(BaseModel):
    dispatch_id: UUID
    report_id: str
    recipient: str
    recipient_hash: str
    channel: str
    subject: str
    status: str  # SENT, DELIVERED, FAILED
    idempotent_replay: bool
    attempts: int
    sent_at: Optional[datetime] = None
    smtp_target: str

