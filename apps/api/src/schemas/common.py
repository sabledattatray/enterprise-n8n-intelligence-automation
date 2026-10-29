from datetime import datetime, timezone
from typing import Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None


class APIEnvelope(BaseModel, Generic[T]):
    correlation_id: str
    status: str = "SUCCESS"  # SUCCESS, PARTIAL_SUCCESS, ERROR
    data: Optional[T] = None
    errors: List[APIError] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

