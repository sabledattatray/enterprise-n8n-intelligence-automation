from datetime import datetime, timezone
from decimal import Decimal
import pytest
from pydantic import ValidationError
from apps.api.src.schemas.common import APIEnvelope, APIError
from apps.api.src.schemas.ingestion import OrderInputRecord


def test_valid_order_record():
    payload = {
        "external_order_id": "ORD-10001",
        "order_date": datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc),
        "product_code": "PROD-ENT-001",
        "product_name": "Enterprise Analytics Suite",
        "product_category": "Software",
        "country_code": "US",
        "region": "North America",
        "currency_code": "usd",  # Tests automatic uppercase normalization
        "quantity": 2,
        "unit_price": Decimal("1200.00"),
        "discount_amount": Decimal("100.00"),
        "revenue": Decimal("2300.00"),
        "cost": Decimal("1320.00"),
        "profit": Decimal("980.00"),
        "order_status": "COMPLETED",
    }
    record = OrderInputRecord(**payload)
    assert record.currency_code == "USD"
    assert record.quantity == 2
    assert record.unit_price == Decimal("1200.00")


def test_invalid_currency_rejected():
    payload = {
        "external_order_id": "ORD-10002",
        "order_date": datetime.now(timezone.utc),
        "product_code": "PROD-ENT-001",
        "product_name": "Enterprise Analytics Suite",
        "product_category": "Software",
        "country_code": "US",
        "region": "North America",
        "currency_code": "XYZ",  # Unsupported currency
        "quantity": 1,
        "unit_price": Decimal("500.00"),
        "revenue": Decimal("500.00"),
        "cost": Decimal("300.00"),
        "profit": Decimal("200.00"),
        "order_status": "COMPLETED",
    }
    with pytest.raises(ValidationError) as excinfo:
        OrderInputRecord(**payload)
    assert "Currency 'XYZ' is not supported" in str(excinfo.value)


def test_negative_quantity_rejected():
    payload = {
        "external_order_id": "ORD-10003",
        "order_date": datetime.now(timezone.utc),
        "product_code": "PROD-ENT-001",
        "product_name": "Enterprise Analytics Suite",
        "product_category": "Software",
        "country_code": "DE",
        "region": "Europe",
        "currency_code": "EUR",
        "quantity": -5,  # Negative quantity violation
        "unit_price": Decimal("500.00"),
        "revenue": Decimal("-2500.00"),
        "cost": Decimal("100.00"),
        "profit": Decimal("-2600.00"),
        "order_status": "CANCELLED",
    }
    with pytest.raises(ValidationError) as excinfo:
        OrderInputRecord(**payload)
    assert "Input should be greater than 0" in str(excinfo.value)


def test_api_envelope_structure():
    envelope = APIEnvelope(
        correlation_id="corr_test123",
        status="ERROR",
        data={"items": 0},
        errors=[APIError(code="INVALID_RECORD", message="Record rejected", field="quantity")],
    )
    dumped = envelope.model_dump()
    assert dumped["correlation_id"] == "corr_test123"
    assert dumped["status"] == "ERROR"
    assert len(dumped["errors"]) == 1
    assert dumped["errors"][0]["code"] == "INVALID_RECORD"
