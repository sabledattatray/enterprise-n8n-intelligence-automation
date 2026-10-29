import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def is_docker_postgres_running() -> bool:
    try:
        r = subprocess.run(["docker", "ps", "--filter", "name=eiap_postgres", "--format", "{{.Names}}"], capture_output=True, text=True)
        return "eiap_postgres" in r.stdout
    except Exception:
        return False


@pytest.mark.skipif(not is_docker_postgres_running(), reason="Requires running eiap_postgres Docker container")
def test_backup_generation():
    """
    Verifies that scripts/backup_database.py creates a valid, non-empty,
    custom-format PostgreSQL dump file and manifest.
    """
    backup_script = ROOT_DIR / "scripts" / "backup_database.py"
    res = subprocess.run([sys.executable, str(backup_script)], capture_output=True, text=True)
    assert res.returncode == 0, f"Backup script failed: {res.stderr}"
    assert "BACKUP COMPLETED AND VERIFIED" in res.stdout
    assert "File:" in res.stdout
    assert "SHA-256:" in res.stdout


@pytest.mark.skipif(not is_docker_postgres_running(), reason="Requires running eiap_postgres Docker container")
def test_restore_and_data_parity_verification():
    """
    Verifies that scripts/verify_restore.py successfully restores the backup
    into an isolated temporary database, checks 100% table and row count parity,
    confirms foreign keys, and cleans up without data loss.
    """
    restore_script = ROOT_DIR / "scripts" / "verify_restore.py"
    res = subprocess.run([sys.executable, str(restore_script)], capture_output=True, text=True)
    assert res.returncode == 0, f"Restore verification failed: {res.stderr}"
    assert "DISASTER RECOVERY VERIFICATION: SUCCESS" in res.stdout
    assert "Zero Data Loss" in res.stdout
    assert "100% Parity Achieved" in res.stdout


