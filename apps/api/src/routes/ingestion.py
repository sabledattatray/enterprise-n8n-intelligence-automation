import csv
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.orm import Session
from apps.api.src.auth import verify_api_key
from apps.api.src.database import get_db
from apps.api.src.models.entities import IngestionRun, RawOrder
from apps.api.src.schemas.common import APIEnvelope, APIError
from apps.api.src.schemas.ingestion import (
    IngestionBatchRequest,
    IngestionBatchResponseData,
    IngestionFileRequest,
)

router = APIRouter(prefix="/v1/ingestion", tags=["Ingestion & Quality"])


@router.post(
    "/batches",
    response_model=APIEnvelope[IngestionBatchResponseData],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def receive_batch(
    payload: IngestionBatchRequest,
    response: Response,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}"),
):
    """
    Idempotent batch ingestion intake endpoint.
    Persists batch metadata to ingestion_runs and raw JSON payloads to raw_orders.
    Detects replayed batches by (source, batch_id).
    """
    # 1. Check for duplicate batch (idempotency check)
    existing_run = (
        db.query(IngestionRun)
        .filter(IngestionRun.source == payload.source, IngestionRun.batch_id == payload.batch_id)
        .first()
    )

    if existing_run:
        response.status_code = status.HTTP_200_OK
        # Idempotent replay: return existing run metadata without re-inserting
        return APIEnvelope(
            correlation_id=x_correlation_id,
            status="SUCCESS",
            data=IngestionBatchResponseData(
                run_id=str(existing_run.run_id),
                source=existing_run.source,
                batch_id=existing_run.batch_id,
                status=existing_run.status,
                total_received=existing_run.total_rows,
                accepted=existing_run.accepted_rows,
                rejected=existing_run.rejected_rows,
                duplicates=existing_run.duplicate_rows,
            ),
            errors=[APIError(code="IDEMPOTENT_REPLAY", message="Batch previously ingested; returning existing run.")],
        )

    # 2. Create new Ingestion Run
    run_id = uuid.uuid4()
    new_run = IngestionRun(
        run_id=run_id,
        source=payload.source,
        batch_id=payload.batch_id,
        checksum=payload.checksum,
        schema_version=payload.schema_version,
        status="RECEIVED",
        started_at=datetime.now(timezone.utc),
        total_rows=len(payload.records),
        accepted_rows=0,
        rejected_rows=0,
        duplicate_rows=0,
        correlation_id=x_correlation_id,
    )
    db.add(new_run)

    # 3. Insert raw staging records
    for rec in payload.records:
        rec_json = json.dumps(rec, sort_keys=True)
        content_hash = hashlib.sha256(rec_json.encode("utf-8")).hexdigest()
        ext_id = str(rec.get("external_order_id") or rec.get("id") or "UNKNOWN")

        raw_rec = RawOrder(
            raw_id=uuid.uuid4(),
            run_id=run_id,
            source=payload.source,
            external_id=ext_id,
            payload=rec,
            content_hash=content_hash,
            received_at=datetime.now(timezone.utc),
            status="PENDING",
        )
        db.add(raw_rec)

    db.commit()
    db.refresh(new_run)

    return APIEnvelope(
        correlation_id=x_correlation_id,
        status="SUCCESS",
        data=IngestionBatchResponseData(
            run_id=str(new_run.run_id),
            source=new_run.source,
            batch_id=new_run.batch_id,
            status=new_run.status,
            total_received=new_run.total_rows,
            accepted=0,
            rejected=0,
            duplicates=0,
        ),
    )


@router.get(
    "/runs/{run_id}",
    response_model=APIEnvelope[IngestionBatchResponseData],
    dependencies=[Depends(verify_api_key)],
)
async def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}"),
):
    """Retrieves execution status and audit metrics for an ingestion run."""
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail={"code": "INVALID_UUID", "message": "Malformed run UUID"})

    run = db.query(IngestionRun).filter(IngestionRun.run_id == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail={"code": "RUN_NOT_FOUND", "message": f"Run {run_id} not found"})

    return APIEnvelope(
        correlation_id=x_correlation_id,
        status="SUCCESS",
        data=IngestionBatchResponseData(
            run_id=str(run.run_id),
            source=run.source,
            batch_id=run.batch_id,
            status=run.status,
            total_received=run.total_rows,
            accepted=run.accepted_rows,
            rejected=run.rejected_rows,
            duplicates=run.duplicate_rows,
        ),
    )


@router.post(
    "/file",
    response_model=APIEnvelope[IngestionBatchResponseData],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_api_key)],
)
async def ingest_from_file(
    payload: IngestionFileRequest,
    response: Response,
    db: Session = Depends(get_db),
    x_correlation_id: str = Header(default_factory=lambda: f"corr_{uuid.uuid4().hex[:12]}"),
):
    """
    Ingests records directly from a local CSV file fixture.
    Enforces idempotency, calculates SHA-256 checksum, and batch-loads staging.
    """
    # 1. Idempotency Check
    existing_run = (
        db.query(IngestionRun)
        .filter(IngestionRun.source == payload.source, IngestionRun.batch_id == payload.batch_id)
        .first()
    )
    if existing_run:
        response.status_code = status.HTTP_200_OK
        return APIEnvelope(
            correlation_id=x_correlation_id,
            status="SUCCESS",
            data=IngestionBatchResponseData(
                run_id=str(existing_run.run_id),
                source=existing_run.source,
                batch_id=existing_run.batch_id,
                status=existing_run.status,
                total_received=existing_run.total_rows,
                accepted=existing_run.accepted_rows,
                rejected=existing_run.rejected_rows,
                duplicates=existing_run.duplicate_rows,
            ),
            errors=[APIError(code="IDEMPOTENT_REPLAY", message="Batch previously ingested; returning existing run.")],
        )

    # 2. Locate CSV file
    file_path = Path(payload.file_path)
    if not file_path.exists():
        # Try relative to container app root
        file_path = Path("/app") / payload.file_path
    if not file_path.exists():
        # Try relative to workspace
        file_path = Path(__file__).resolve().parent.parent.parent.parent / payload.file_path

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "FILE_NOT_FOUND", "message": f"Fixture file not found at '{payload.file_path}'"},
        )

    # 3. Read and compute checksum
    hasher = hashlib.sha256()
    records = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
            hasher.update(str(row).encode("utf-8"))

    checksum = hasher.hexdigest()
    run_id = uuid.uuid4()

    new_run = IngestionRun(
        run_id=run_id,
        source=payload.source,
        batch_id=payload.batch_id,
        checksum=checksum,
        schema_version=payload.schema_version,
        status="RECEIVED",
        started_at=datetime.now(timezone.utc),
        total_rows=len(records),
        accepted_rows=0,
        rejected_rows=0,
        duplicate_rows=0,
        correlation_id=x_correlation_id,
    )
    db.add(new_run)

    # 4. Bulk insert raw staging records
    raw_objects = []
    for rec in records:
        rec_json = json.dumps(rec, sort_keys=True)
        content_hash = hashlib.sha256(rec_json.encode("utf-8")).hexdigest()
        ext_id = str(rec.get("external_order_id") or "UNKNOWN")

        raw_objects.append(
            RawOrder(
                raw_id=uuid.uuid4(),
                run_id=run_id,
                source=payload.source,
                external_id=ext_id,
                payload=rec,
                content_hash=content_hash,
                received_at=datetime.now(timezone.utc),
                status="PENDING",
            )
        )

    # Insert in 1000-row chunks
    chunk_size = 1000
    for i in range(0, len(raw_objects), chunk_size):
        db.add_all(raw_objects[i : i + chunk_size])
        db.flush()

    db.commit()
    db.refresh(new_run)

    return APIEnvelope(
        correlation_id=x_correlation_id,
        status="SUCCESS",
        data=IngestionBatchResponseData(
            run_id=str(new_run.run_id),
            source=new_run.source,
            batch_id=new_run.batch_id,
            status=new_run.status,
            total_received=new_run.total_rows,
            accepted=0,
            rejected=0,
            duplicates=0,
        ),
    )


