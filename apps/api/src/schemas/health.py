from datetime import datetime, timezone
from typing import Dict
from pydantic import BaseModel, Field


class HealthLiveResponse(BaseModel):
    status: str = "ALIVE"
    service: str
    version: str
    environment: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DependencyStatus(BaseModel):
    status: str
    latency_ms: float
    details: Dict[str, str] = Field(default_factory=dict)


class HealthReadyResponse(BaseModel):
    status: str = "READY"  # READY, DEGRADED, UNHEALTHY
    service: str
    version: str
    environment: str
    dependencies: Dict[str, DependencyStatus]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

