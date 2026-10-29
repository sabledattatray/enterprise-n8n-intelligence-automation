from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "SGD", "JPY"}


class OrderInputRecord(BaseModel):
    external_order_id: str = Field(..., min_length=1, max_length=128)
    order_date: datetime
    product_code: str = Field(..., min_length=1, max_length=64)
    product_name: str = Field(..., min_length=1, max_length=255)
    product_category: str = Field(..., min_length=1, max_length=64)
    country_code: str = Field(..., min_length=2, max_length=8)
    region: str = Field(..., min_length=1, max_length=64)
    currency_code: str = Field(..., min_length=3, max_length=8)
    quantity: int = Field(..., gt=0, description="Quantity must be strictly positive")
    unit_price: Decimal = Field(..., ge=0, description="Unit price cannot be negative")
    discount_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    revenue: Decimal
    cost: Decimal
    profit: Decimal
    order_status: str = Field(..., min_length=1, max_length=32)

    @field_validator("currency_code")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        norm = v.strip().upper()
        if norm not in ALLOWED_CURRENCIES:
            raise ValueError(f"Currency '{v}' is not supported. Allowed: {sorted(ALLOWED_CURRENCIES)}")
        return norm


class IngestionBatchRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=64)
    batch_id: str = Field(..., min_length=1, max_length=128)
    checksum: str = Field(..., min_length=16, max_length=64)
    schema_version: str = Field(default="1.0", max_length=16)
    records: List[Dict[str, Any]] = Field(..., min_length=1, max_length=50000)


class IngestionFileRequest(BaseModel):
    source: str = Field(default="CSV_FILE", min_length=1, max_length=64)
    batch_id: str = Field(..., min_length=1, max_length=128)
    file_path: str = Field(..., min_length=1, max_length=512)
    schema_version: str = Field(default="1.0", max_length=16)


class IngestionBatchResponseData(BaseModel):
    run_id: str
    source: str
    batch_id: str
    status: str
    total_received: int
    accepted: int
    rejected: int
    duplicates: int

