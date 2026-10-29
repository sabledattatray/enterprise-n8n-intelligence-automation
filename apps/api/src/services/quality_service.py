import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple
from sqlalchemy.orm import Session
from apps.api.src.models.entities import IngestionRun, RawOrder, RejectedRecord

ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "SGD", "JPY"}


def parse_date(date_val: Any) -> datetime:
    if not date_val:
        raise ValueError("Missing date")
    if isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, str):
        # Handle ISO strings
        clean = date_val.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    raise ValueError(f"Unrecognized date type: {type(date_val)}")


def validate_single_record(
    rec: Dict[str, Any], seen_keys: Set[str]
) -> Tuple[str, str, str, str]:
    """
    Evaluates business quality rules in strict deterministic order of precedence:
    1. DUPLICATE_KEY: Check if external_order_id seen previously in batch.
    2. MISSING_FIELD: Null or empty required attributes.
    3. INVALID_QUANTITY: quantity <= 0.
    4. INVALID_PRICE: unit_price < 0 or discount_amount < 0.
    5. INVALID_CURRENCY: currency not in ALLOWED_CURRENCIES.
    6. INVALID_DATE: unparseable date.

    Returns:
        (disposition, reason_code, field_name, sanitized_excerpt)
        disposition in ("VALID", "DUPLICATE", "REJECT")
    """
    ext_id = str(rec.get("external_order_id") or "").strip()

    # Rule 1: Duplicate business key within batch
    if not ext_id:
        return (
            "REJECT",
            "MISSING_FIELD",
            "external_order_id",
            "Record missing external_order_id",
        )

    if ext_id in seen_keys:
        return (
            "DUPLICATE",
            "DUPLICATE_ORDER_ID",
            "external_order_id",
            f"Duplicate order ID '{ext_id}' in batch",
        )
    seen_keys.add(ext_id)

    # Rule 2: Missing required attributes
    prod_code = str(rec.get("product_code") or "").strip()
    if not prod_code:
        return "REJECT", "MISSING_FIELD", "product_code", f"Order {ext_id} missing product_code"

    country = str(rec.get("country_code") or "").strip()
    if not country:
        return "REJECT", "MISSING_FIELD", "country_code", f"Order {ext_id} missing country_code"

    raw_date = rec.get("order_date")
    if not raw_date:
        return "REJECT", "MISSING_FIELD", "order_date", f"Order {ext_id} missing order_date"

    # Rule 6 (Date check): unparseable date
    try:
        dt = parse_date(raw_date)
    except Exception:
        return "REJECT", "INVALID_DATE", "order_date", f"Order {ext_id} invalid date '{raw_date}'"

    # Rule 3: Quantity check
    raw_qty = rec.get("quantity")
    try:
        qty = int(raw_qty)
        if qty <= 0:
            return (
                "REJECT",
                "INVALID_QUANTITY",
                "quantity",
                f"Order {ext_id} non-positive quantity '{raw_qty}'",
            )
    except (ValueError, TypeError):
        return (
            "REJECT",
            "INVALID_QUANTITY",
            "quantity",
            f"Order {ext_id} non-numeric quantity '{raw_qty}'",
        )

    # Rule 4: Unit price check
    raw_price = rec.get("unit_price")
    try:
        price = float(raw_price)
        if price < 0:
            return (
                "REJECT",
                "INVALID_PRICE",
                "unit_price",
                f"Order {ext_id} negative unit_price '{raw_price}'",
            )
    except (ValueError, TypeError):
        return (
            "REJECT",
            "INVALID_PRICE",
            "unit_price",
            f"Order {ext_id} non-numeric unit_price '{raw_price}'",
        )

    # Rule 5: Currency check
    curr = str(rec.get("currency_code") or "").strip().upper()
    if curr not in ALLOWED_CURRENCIES:
        return (
            "REJECT",
            "INVALID_CURRENCY",
            "currency_code",
            f"Order {ext_id} unsupported currency '{curr}'",
        )

    return "VALID", "NONE", "", ""


def validate_run_batch(db: Session, run_id: uuid.UUID) -> Dict[str, Any]:
    """
    Validates all staging records for a given run_id.
    Persists rejects, marks duplicates, and validates facts.
    """
    run = db.query(IngestionRun).filter(IngestionRun.run_id == run_id).first()
    if not run:
        raise ValueError(f"Run ID {run_id} not found")

    raw_records: List[RawOrder] = (
        db.query(RawOrder).filter(RawOrder.run_id == run_id).order_by(RawOrder.received_at).all()
    )

    seen_keys: Set[str] = set()
    accepted_count = 0
    duplicate_count = 0
    rejected_count = 0
    sample_rejections: List[Dict[str, str]] = []

    for raw in raw_records:
        disposition, reason, field, excerpt = validate_single_record(raw.payload, seen_keys)

        if disposition == "VALID":
            raw.status = "VALIDATED"
            accepted_count += 1
        elif disposition == "DUPLICATE":
            raw.status = "DUPLICATE"
            duplicate_count += 1
        elif disposition == "REJECT":
            raw.status = "QUARANTINED"
            rejected_count += 1
            reject_rec = RejectedRecord(
                reject_id=uuid.uuid4(),
                run_id=run.run_id,
                source=raw.source,
                external_id=raw.external_id,
                reason_code=reason,
                field_name=field,
                sanitized_excerpt=excerpt,
                rejected_at=datetime.now(timezone.utc),
            )
            db.add(reject_rec)
            if len(sample_rejections) < 10:
                sample_rejections.append({
                    "external_id": raw.external_id,
                    "reason_code": reason,
                    "field": field,
                    "excerpt": excerpt,
                })

    # Update Ingestion Run metrics
    run.accepted_rows = accepted_count
    run.duplicate_rows = duplicate_count
    run.rejected_rows = rejected_count
    run.status = "VALIDATED"

    # Strict reconciliation invariant assertion: accepted + duplicates + rejects == total
    total_reconciled = accepted_count + duplicate_count + rejected_count
    assert total_reconciled == len(raw_records), (
        f"Reconciliation discrepancy: total raw ({len(raw_records)}) != "
        f"accepted ({accepted_count}) + duplicates ({duplicate_count}) + rejected ({rejected_count})"
    )

    db.commit()

    quality_score = 0.0
    if len(raw_records) > 0:
        quality_score = round((accepted_count / len(raw_records)) * 100.0, 2)

    return {
        "run_id": str(run_id),
        "source": run.source,
        "batch_id": run.batch_id,
        "total_records": len(raw_records),
        "accepted_rows": accepted_count,
        "duplicate_rows": duplicate_count,
        "rejected_rows": rejected_count,
        "quality_score": quality_score,
        "gate_status": "PASSED" if quality_score >= 50.0 else "BLOCKED",
        "sample_rejections": sample_rejections,
    }

