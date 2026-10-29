#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Disaster Recovery: PostgreSQL Database Backup Script

Performs a consistent, compressed custom-format dump (-Fc) of the primary
`business_analytics` database using pg_dump inside the isolated PostgreSQL container.
Computes SHA-256 checksum, verifies size, and records metadata.
"""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load environment configuration
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
CONTAINER_NAME = "eiap_postgres"
DB_NAME = os.getenv("POSTGRES_DB_ANALYTICS", "business_analytics")
DB_USER = os.getenv("POSTGRES_USER", "eiap_admin")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "eiap_local_secure_pass_2026_x9")



def compute_sha256(filepath: Path) -> str:
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def main():
    print("=" * 80)
    print("EIAP DISASTER RECOVERY: POSTGRESQL BACKUP AUTOMATION")
    print("=" * 80)

    start_time = time.time()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    backup_filename = f"backup_{DB_NAME}_{timestamp}.dump"
    backup_path = BACKUP_DIR / backup_filename
    container_temp_dump = f"/tmp/{backup_filename}"

    print(f"[*] Target Database:   {DB_NAME}")
    print(f"[*] Container:         {CONTAINER_NAME}")
    print(f"[*] Destination Host:  {backup_path}")

    # 1. Execute pg_dump inside container
    print("\n[Step 1] Executing pg_dump inside postgres container...")
    dump_cmd = [
        "docker", "exec",
        "-e", f"PGPASSWORD={DB_PASS}",
        CONTAINER_NAME,
        "pg_dump",
        "-U", DB_USER,
        "-d", DB_NAME,
        "-Fc",  # Custom format (compressed, supports parallel restore & selective restore)
        "-v",
        "-f", container_temp_dump,
    ]

    res = subprocess.run(dump_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] pg_dump failed with returncode {res.returncode}:")
        print(res.stderr)
        sys.exit(1)
    print("  [OK] pg_dump completed successfully inside container.")

    # 2. Copy dump out of container to host
    print("\n[Step 2] Copying backup artifact to host filesystem...")
    cp_cmd = ["docker", "cp", f"{CONTAINER_NAME}:{container_temp_dump}", str(backup_path)]
    res = subprocess.run(cp_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[ERROR] docker cp failed: {res.stderr}")
        sys.exit(1)

    # 3. Clean up container temporary file
    subprocess.run(["docker", "exec", CONTAINER_NAME, "rm", "-f", container_temp_dump], capture_output=True)

    # 4. Verify host file
    if not backup_path.exists():
        print(f"[ERROR] Host backup file {backup_path} does not exist!")
        sys.exit(1)

    file_size_bytes = backup_path.stat().st_size
    file_size_mb = round(file_size_bytes / (1024 * 1024), 2)
    if file_size_bytes == 0:
        print(f"[ERROR] Host backup file {backup_path} is 0 bytes!")
        sys.exit(1)

    sha256_hash = compute_sha256(backup_path)
    elapsed = round(time.time() - start_time, 2)

    # 5. Maintain latest symlink / copy for verification convenience
    latest_path = BACKUP_DIR / f"latest_{DB_NAME}.dump"
    try:
        if latest_path.exists():
            latest_path.unlink()
        import shutil
        shutil.copy2(backup_path, latest_path)
    except Exception as e:
        print(f"  [WARN] Could not update latest alias: {e}")

    # 6. Save metadata manifest
    manifest = {
        "database": DB_NAME,
        "backup_file": backup_filename,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "size_bytes": file_size_bytes,
        "size_mb": file_size_mb,
        "sha256": sha256_hash,
        "duration_seconds": elapsed,
        "format": "PostgreSQL custom dump (-Fc)",
        "pg_version": "16-alpine",
    }
    manifest_path = BACKUP_DIR / f"backup_{DB_NAME}_{timestamp}_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print("\n" + "=" * 80)
    print("BACKUP COMPLETED AND VERIFIED")
    print(f"  File:       {backup_path.name}")
    print(f"  Size:       {file_size_mb} MB ({file_size_bytes:,} bytes)")
    print(f"  SHA-256:    {sha256_hash}")
    print(f"  Duration:   {elapsed}s")
    print(f"  Manifest:   {manifest_path.name}")
    print("=" * 80)


if __name__ == "__main__":
    main()
