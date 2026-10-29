import csv
import hashlib
from pathlib import Path
from apps.api.src.services.quality_service import validate_single_record

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"

EXPECTED_SMOKE_HASH = "A01BA50862DA960E72A45084D0AA0145845034869B3904055965597AB4E32885"
EXPECTED_STANDARD_10K_HASH = "997FE672F1FEF389D25F0B381D2673E20E5BCA9E30E7199D0334C7FE076BE452"


def test_dataset_checksums():
    """Verify SHA-256 checksums of deterministic synthetic datasets."""
    smoke_file = FIXTURES_DIR / "smoke_100.csv"
    std_file = FIXTURES_DIR / "standard_10k.csv"

    assert smoke_file.exists(), f"Missing {smoke_file}"
    assert std_file.exists(), f"Missing {std_file}"

    with open(smoke_file, "rb") as f:
        smoke_hash = hashlib.sha256(f.read()).hexdigest().upper()
    with open(std_file, "rb") as f:
        std_hash = hashlib.sha256(f.read()).hexdigest().upper()

    assert smoke_hash == EXPECTED_SMOKE_HASH, f"Smoke hash mismatch: {smoke_hash}"
    assert std_hash == EXPECTED_STANDARD_10K_HASH, f"Standard 10k hash mismatch: {std_hash}"


def test_standard_10k_reconciliation_regression():
    """
    Strict regression test asserting that 10,000 records from standard_10k.csv
    reconcile exactly to 8,564 valid, 499 duplicates, and 937 rejects
    under the documented business rules and precedence.
    """
    std_file = FIXTURES_DIR / "standard_10k.csv"
    seen_keys = set()
    accepted = 0
    duplicates = 0
    quarantined = 0
    reason_counts = {}

    with open(std_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 10000, f"Expected 10,000 records, got {len(rows)}"

    for row in rows:
        disposition, reason, field, excerpt = validate_single_record(row, seen_keys)
        if disposition == "VALID":
            accepted += 1
        elif disposition == "DUPLICATE":
            duplicates += 1
        elif disposition == "REJECT":
            quarantined += 1
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    assert accepted == 8564, f"Expected 8564 accepted, got {accepted}"
    assert duplicates == 499, f"Expected 499 duplicates, got {duplicates}"
    assert quarantined == 937, f"Expected 937 quarantined, got {quarantined}"
    assert (accepted + duplicates + quarantined) == 10000

    # Verify specific defect breakdown
    assert reason_counts.get("MISSING_FIELD") == 365
    assert reason_counts.get("INVALID_CURRENCY") == 288
    assert reason_counts.get("INVALID_QUANTITY") == 284

