import uuid
import pytest
from fastapi.testclient import TestClient
from apps.api.src.config import settings
from apps.api.src.main import app

client = TestClient(app)
AUTH_HEADERS = {"X-API-Key": settings.API_KEY, "X-Correlation-ID": "corr_test_negative"}


def test_unauthenticated_requests():
    """Verify missing API key returns 401."""
    res = client.post("/v1/ingestion/file", json={"file_path": "non_existent.csv", "batch_id": "test_auth"})
    assert res.status_code == 401
    assert res.json()["errors"][0]["code"] == "AUTH_KEY_MISSING"


def test_invalid_api_key():
    """Verify wrong API key returns 403."""
    res = client.post(
        "/v1/ingestion/file",
        json={"file_path": "non_existent.csv", "batch_id": "test_auth"},
        headers={"X-API-Key": "invalid_random_key_value_1234567890"},
    )
    assert res.status_code == 403
    assert res.json()["errors"][0]["code"] == "AUTH_INVALID_KEY"


def test_nonexistent_file_path():
    """Verify 404 for unresolvable CSV file paths."""
    res = client.post(
        "/v1/ingestion/file",
        json={"file_path": "data/fixtures/completely_imaginary_file.csv", "batch_id": f"batch_{uuid.uuid4().hex[:8]}"},
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 404
    assert res.json()["errors"][0]["code"] == "FILE_NOT_FOUND"


def test_quality_validation_nonexistent_run():
    """Verify 404 when validating non-existent run."""
    random_uuid = str(uuid.uuid4())
    res = client.post(f"/v1/quality/validate/{random_uuid}", headers=AUTH_HEADERS)
    assert res.status_code == 404
    assert res.json()["errors"][0]["code"] == "RUN_NOT_FOUND"


def test_quality_validation_malformed_uuid():
    """Verify 400 when UUID is malformed."""
    res = client.post("/v1/quality/validate/not-a-valid-uuid", headers=AUTH_HEADERS)
    assert res.status_code == 400
    assert res.json()["errors"][0]["code"] == "INVALID_UUID"


def test_etl_commit_nonexistent_run():
    """Verify 400 when committing ETL for non-existent run."""
    random_uuid = str(uuid.uuid4())
    res = client.post(f"/v1/etl/commit/{random_uuid}", headers=AUTH_HEADERS)
    assert res.status_code == 400
    assert res.json()["errors"][0]["code"] == "ETL_PRECONDITION_FAILED"


def test_malformed_batch_payload():
    """Verify 422 for malformed batch payload."""
    res = client.post(
        "/v1/ingestion/batches",
        json={"source": "", "batch_id": ""},  # Missing required fields
        headers=AUTH_HEADERS,
    )
    assert res.status_code == 422
    assert res.json()["status"] == "ERROR"

