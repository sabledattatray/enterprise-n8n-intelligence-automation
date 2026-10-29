"""
Deterministic Synthetic Business Data Generator for EIAP.
Generates realistic multi-currency order events spanning 90 days with controlled defect injections.
Produces repeatable outputs using a fixed seed.
"""

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


PRODUCTS = [
    {"code": "PROD-ENT-001", "name": "Enterprise Analytics Suite", "category": "Software", "base_price": 1200.00},
    {"code": "PROD-ENT-002", "name": "Data Integration Pipeline", "category": "Software", "base_price": 850.00},
    {"code": "PROD-ENT-003", "name": "Cloud Observability Agent", "category": "Infrastructure", "base_price": 320.00},
    {"code": "PROD-ENT-004", "name": "AI Workflow Copilot", "category": "AI Services", "base_price": 950.00},
    {"code": "PROD-ENT-005", "name": "Executive KPI Dashboard", "category": "BI Reporting", "base_price": 500.00},
    {"code": "PROD-ENT-006", "name": "Security Audit Module", "category": "Security", "base_price": 650.00},
    {"code": "PROD-ENT-007", "name": "Automated ETL Worker", "category": "Data Engineering", "base_price": 400.00},
    {"code": "PROD-ENT-008", "name": "Incident Alert Gateway", "category": "Operations", "base_price": 280.00},
]

GEOGRAPHIES = [
    {"country": "US", "region": "North America"},
    {"country": "GB", "region": "Europe"},
    {"country": "DE", "region": "Europe"},
    {"country": "SG", "region": "Asia-Pacific"},
    {"country": "JP", "region": "Asia-Pacific"},
    {"country": "AU", "region": "Oceania"},
]

VALID_CURRENCIES = ["USD", "EUR", "GBP", "SGD", "JPY"]
INVALID_CURRENCIES = ["XYZ", "BAD_CURR", "999", "INVALID"]
ORDER_STATUSES = ["COMPLETED", "PROCESSING", "SHIPPED", "CANCELLED", "REFUNDED"]


def generate_dataset(
    num_rows: int = 100,
    seed: int = 42,
    base_date: datetime = None,
    duplicate_rate: float = 0.05,
    negative_qty_rate: float = 0.03,
    invalid_currency_rate: float = 0.03,
    missing_fields_rate: float = 0.04,
    anomaly_spike: bool = True,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Generates a deterministic dataset with controlled defect rates.
    Returns:
        (records, summary_stats)
    """
    random.seed(seed)
    if base_date is None:
        base_date = datetime(2026, 7, 1, 0, 0, 0, tzinfo=timezone.utc)

    records: List[Dict[str, Any]] = []
    
    # Tracking counts
    stats = {
        "seed": seed,
        "total_records": num_rows,
        "valid_expected": 0,
        "duplicates_injected": 0,
        "negative_quantity_injected": 0,
        "invalid_currency_injected": 0,
        "missing_fields_injected": 0,
        "anomaly_spikes_injected": 0,
    }

    # Generate normal records first
    for i in range(1, num_rows + 1):
        order_num = 10000 + i
        external_order_id = f"ORD-{order_num}"
        day_offset = random.randint(0, 90)
        hour_offset = random.randint(0, 23)
        minute_offset = random.randint(0, 59)
        order_time = base_date + timedelta(days=day_offset, hours=hour_offset, minutes=minute_offset)
        
        prod = random.choice(PRODUCTS)
        geo = random.choice(GEOGRAPHIES)
        currency = random.choice(VALID_CURRENCIES)
        status = random.choices(ORDER_STATUSES, weights=[0.70, 0.15, 0.08, 0.05, 0.02])[0]
        
        qty = random.randint(1, 10)
        unit_price = prod["base_price"]
        discount = round(unit_price * qty * (random.uniform(0.0, 0.15) if random.random() < 0.25 else 0.0), 2)
        revenue = round((qty * unit_price) - discount, 2)
        cost = round(revenue * 0.55, 2)
        profit = round(revenue - cost, 2)

        # Defect Injection based on target rates
        rand_defect = random.random()
        defect_type = "NONE"

        if i <= int(num_rows * duplicate_rate) and i > 1:
            # Duplicate external_order_id of previous record
            defect_type = "DUPLICATE"
            external_order_id = records[-1]["external_order_id"]
            stats["duplicates_injected"] += 1

        elif rand_defect < negative_qty_rate:
            defect_type = "NEGATIVE_QUANTITY"
            qty = -1 * random.randint(1, 5)
            revenue = round((qty * unit_price) - discount, 2)
            profit = round(revenue - cost, 2)
            stats["negative_quantity_injected"] += 1

        elif rand_defect < (negative_qty_rate + invalid_currency_rate):
            defect_type = "INVALID_CURRENCY"
            currency = random.choice(INVALID_CURRENCIES)
            stats["invalid_currency_injected"] += 1

        elif rand_defect < (negative_qty_rate + invalid_currency_rate + missing_fields_rate):
            defect_type = "MISSING_FIELD"
            field_to_drop = random.choice(["product_code", "order_date", "external_order_id"])
            if field_to_drop == "product_code":
                prod = {"code": None, "name": None, "category": None}
            elif field_to_drop == "order_date":
                order_time = None
            elif field_to_drop == "external_order_id":
                external_order_id = None
            stats["missing_fields_injected"] += 1

        # Anomaly Spike injection (e.g. Day 85 has an extreme 15x bulk purchase)
        if anomaly_spike and day_offset == 85 and defect_type == "NONE" and stats["anomaly_spikes_injected"] < 2:
            qty = 150  # Huge enterprise bulk order
            revenue = round((qty * unit_price) - discount, 2)
            cost = round(revenue * 0.50, 2)
            profit = round(revenue - cost, 2)
            defect_type = "REVENUE_SPIKE_ANOMALY"
            stats["anomaly_spikes_injected"] += 1

        if defect_type in ["NONE", "REVENUE_SPIKE_ANOMALY"]:
            stats["valid_expected"] += 1

        record = {
            "external_order_id": external_order_id,
            "order_date": order_time.isoformat() if order_time else None,
            "product_code": prod["code"],
            "product_name": prod["name"],
            "product_category": prod["category"],
            "country_code": geo["country"],
            "region": geo["region"],
            "currency_code": currency,
            "quantity": qty,
            "unit_price": unit_price,
            "discount_amount": discount,
            "revenue": revenue,
            "cost": cost,
            "profit": profit,
            "order_status": status,
            "defect_type": defect_type,
        }
        records.append(record)

    return records, stats


def write_fixtures(fixtures_dir: Path, expected_dir: Path):
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    # 1. 100-row Smoke Fixture
    smoke_records, smoke_stats = generate_dataset(num_rows=100, seed=42)
    
    smoke_json_path = fixtures_dir / "smoke_100.json"
    with open(smoke_json_path, "w", encoding="utf-8") as f:
        json.dump(smoke_records, f, indent=2)

    smoke_csv_path = fixtures_dir / "smoke_100.csv"
    with open(smoke_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=smoke_records[0].keys())
        writer.writeheader()
        writer.writerows(smoke_records)

    smoke_expected_path = expected_dir / "smoke_100_summary.json"
    with open(smoke_expected_path, "w", encoding="utf-8") as f:
        json.dump(smoke_stats, f, indent=2)

    # 2. 10,000-row Standard Fixture
    standard_records, standard_stats = generate_dataset(num_rows=10000, seed=1337)
    
    standard_csv_path = fixtures_dir / "standard_10k.csv"
    with open(standard_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=standard_records[0].keys())
        writer.writeheader()
        writer.writerows(standard_records)

    standard_expected_path = expected_dir / "standard_10k_summary.json"
    with open(standard_expected_path, "w", encoding="utf-8") as f:
        json.dump(standard_stats, f, indent=2)

    print(f"[OK] Generated smoke fixture: {smoke_csv_path} ({len(smoke_records)} rows)")
    print(f"     Smoke stats: {smoke_stats}")
    print(f"[OK] Generated standard fixture: {standard_csv_path} ({len(standard_records)} rows)")
    print(f"     Standard stats: {standard_stats}")


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parent.parent
    write_fixtures(base_dir / "fixtures", base_dir / "expected")

