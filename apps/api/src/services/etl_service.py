import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from apps.api.src.models.entities import (
    DimDate,
    DimGeography,
    DimProduct,
    IngestionRun,
    RawOrder,
    WorkflowExecution,
)
from apps.api.src.services.quality_service import parse_date


def commit_etl_run(db: Session, run_id: uuid.UUID, correlation_id: str) -> Dict[str, Any]:
    """
    Executes atomic transactional ETL for validated raw orders of a specific run_id.
    Loads dimensions (date, product, geography) and performs idempotent upserts into fact_orders.
    """
    t0 = time.perf_counter()

    run = db.query(IngestionRun).filter(IngestionRun.run_id == run_id).first()
    if not run:
        raise ValueError(f"Ingestion run {run_id} not found")

    if run.status not in ("VALIDATED", "RECEIVED"):
        raise ValueError(f"Run {run_id} is in status '{run.status}'; must be 'VALIDATED' before ETL commit")

    # Fetch validated records
    validated_raw: List[RawOrder] = (
        db.query(RawOrder)
        .filter(RawOrder.run_id == run_id, RawOrder.status == "VALIDATED")
        .all()
    )

    if not validated_raw:
        # If no validated records, mark run as committed with 0 facts
        run.status = "COMMITTED"
        run.ended_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "run_id": str(run_id),
            "status": "COMMITTED",
            "facts_upserted": 0,
            "dimensions_loaded": 0,
            "duration_ms": int((time.perf_counter() - t0) * 1000),
        }

    # --------------------------------------------------------------------------
    # 1. Dimension Loading: dim_date
    # --------------------------------------------------------------------------
    dates_to_insert = set()
    for r in validated_raw:
        dt = parse_date(r.payload["order_date"])
        d = dt.date()
        date_key = d.year * 10000 + d.month * 100 + d.day
        quarter = (d.month - 1) // 3 + 1
        dates_to_insert.add((date_key, d, d.year, quarter, d.month, d.day))

    if dates_to_insert:
        date_values = [
            f"({dk}, '{fd}', {y}, {q}, {m}, {dy})"
            for (dk, fd, y, q, m, dy) in dates_to_insert
        ]
        sql_date = f"""
        INSERT INTO dim_date (date_key, full_date, year, quarter, month, day)
        VALUES {", ".join(date_values)}
        ON CONFLICT (full_date) DO NOTHING;
        """
        db.execute(text(sql_date))

    # --------------------------------------------------------------------------
    # 2. Dimension Loading: dim_product
    # --------------------------------------------------------------------------
    prods_to_insert = {}
    for r in validated_raw:
        code = str(r.payload["product_code"]).strip()
        name = str(r.payload.get("product_name") or code).replace("'", "''")
        category = str(r.payload.get("product_category") or "General").replace("'", "''")
        prods_to_insert[code] = (name, category)

    if prods_to_insert:
        prod_values = [
            f"('{code}', '{name}', '{cat}', clock_timestamp())"
            for code, (name, cat) in prods_to_insert.items()
        ]
        sql_prod = f"""
        INSERT INTO dim_product (product_code, product_name, category, created_at)
        VALUES {", ".join(prod_values)}
        ON CONFLICT (product_code) DO NOTHING;
        """
        db.execute(text(sql_prod))

    # --------------------------------------------------------------------------
    # 3. Dimension Loading: dim_geography
    # --------------------------------------------------------------------------
    geos_to_insert = set()
    for r in validated_raw:
        country = str(r.payload["country_code"]).strip()
        region = str(r.payload.get("region") or "Unknown").replace("'", "''")
        geos_to_insert.add((country, region))

    if geos_to_insert:
        geo_values = [
            f"('{c}', '{reg}', clock_timestamp())"
            for (c, reg) in geos_to_insert
        ]
        sql_geo = f"""
        INSERT INTO dim_geography (country_code, region, created_at)
        VALUES {", ".join(geo_values)}
        ON CONFLICT (country_code, region) DO NOTHING;
        """
        db.execute(text(sql_geo))

    db.commit()

    # --------------------------------------------------------------------------
    # 4. Lookup Dimension Keys
    # --------------------------------------------------------------------------
    prod_rows = db.query(DimProduct.product_code, DimProduct.product_key).all()
    prod_map = {row.product_code: row.product_key for row in prod_rows}

    geo_rows = db.query(DimGeography.country_code, DimGeography.region, DimGeography.geography_key).all()
    geo_map = {(row.country_code, row.region): row.geography_key for row in geo_rows}

    # --------------------------------------------------------------------------
    # 5. Atomic Upsert into fact_orders
    # --------------------------------------------------------------------------
    fact_batch = []
    for r in validated_raw:
        p = r.payload
        dt = parse_date(p["order_date"])
        date_key = dt.year * 10000 + dt.month * 100 + dt.day
        prod_key = prod_map[p["product_code"]]
        geo_key = geo_map[(p["country_code"], p.get("region") or "Unknown")]
        ext_id = str(p["external_order_id"]).replace("'", "''")
        status = str(p["order_status"]).replace("'", "''")
        curr = str(p["currency_code"]).replace("'", "''")
        source = str(r.source).replace("'", "''")

        fact_batch.append(
            f"('{str(uuid.uuid4())}', '{source}', '{ext_id}', {date_key}, {prod_key}, {geo_key}, "
            f"{int(p['quantity'])}, {Decimal(str(p['unit_price']))}, {Decimal(str(p.get('discount_amount', 0.0)))}, "
            f"{Decimal(str(p['revenue']))}, {Decimal(str(p['cost']))}, {Decimal(str(p['profit']))}, "
            f"'{curr}', '{status}', clock_timestamp(), clock_timestamp())"
        )

    # Execute in chunks of 1000 to keep SQL parameters bounded
    chunk_size = 1000
    for i in range(0, len(fact_batch), chunk_size):
        chunk = fact_batch[i : i + chunk_size]
        sql_fact = f"""
        INSERT INTO fact_orders (
            order_key, source, external_order_id, order_date_key, product_key, geography_key,
            quantity, unit_price, discount_amount, revenue, cost, profit,
            currency_code, order_status, source_updated_at, loaded_at
        )
        VALUES {", ".join(chunk)}
        ON CONFLICT (source, external_order_id, product_key) DO UPDATE SET
            quantity = EXCLUDED.quantity,
            unit_price = EXCLUDED.unit_price,
            discount_amount = EXCLUDED.discount_amount,
            revenue = EXCLUDED.revenue,
            cost = EXCLUDED.cost,
            profit = EXCLUDED.profit,
            order_status = EXCLUDED.order_status,
            source_updated_at = EXCLUDED.source_updated_at,
            loaded_at = clock_timestamp();
        """
        db.execute(text(sql_fact))

    # Mark raw records and run as COMMITTED
    db.execute(
        text("UPDATE raw_orders SET status = 'COMMITTED' WHERE run_id = :rid AND status = 'VALIDATED'"),
        {"rid": run_id},
    )
    run.status = "COMMITTED"
    run.ended_at = datetime.now(timezone.utc)

    duration_ms = int((time.perf_counter() - t0) * 1000)

    # Audit in workflow_executions
    exec_audit = WorkflowExecution(
        execution_id=uuid.uuid4(),
        correlation_id=correlation_id,
        workflow_name="WF03-SQL-ETL",
        run_id=run.run_id,
        status="SUCCESS",
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
        duration_ms=duration_ms,
    )
    db.add(exec_audit)

    db.commit()

    return {
        "run_id": str(run_id),
        "status": "COMMITTED",
        "facts_upserted": len(validated_raw),
        "dimensions_loaded": len(dates_to_insert) + len(prods_to_insert) + len(geos_to_insert),
        "duration_ms": duration_ms,
    }
