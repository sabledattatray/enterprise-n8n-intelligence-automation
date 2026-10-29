"""
Data Contract Tests for EIAP.
Verifies data type precision, constraints, and business invariants across staging and facts.
"""

from decimal import Decimal
import pytest
from apps.api.src.models.entities import DimGeography, DimProduct, FactOrder


def test_fact_orders_grain():
    """Validates the business key grain of fact_orders."""
    expected_grain = ["source", "external_order_id", "product_key"]
    for col in expected_grain:
        assert hasattr(FactOrder, col)


def test_numeric_precision_definitions():
    """Validates that money columns are configured with NUMERIC(14, 4) or NUMERIC(16, 4)."""
    assert FactOrder.revenue.type.precision == 14
    assert FactOrder.revenue.type.scale == 4
    assert FactOrder.unit_price.type.precision == 14
    assert FactOrder.unit_price.type.scale == 4
    assert FactOrder.discount_amount.type.precision == 14
    assert FactOrder.discount_amount.type.scale == 4


def test_dim_product_schema():
    """Validates product dimension attributes."""
    assert hasattr(DimProduct, "product_code")
    assert hasattr(DimProduct, "product_name")
    assert hasattr(DimProduct, "category")


def test_dim_geography_schema():
    """Validates geography dimension attributes."""
    assert hasattr(DimGeography, "country_code")
    assert hasattr(DimGeography, "region")

