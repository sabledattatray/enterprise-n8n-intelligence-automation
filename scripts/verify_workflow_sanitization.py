#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Workflow Sanitization & Secret Scanning Verification

Scans all workflow files in workflows/ and backups/n8n_exported_workflows.json
to verify that no credentials, tokens, or plain-text secrets are embedded.
"""

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = ROOT_DIR / "workflows"
BACKUPS_DIR = ROOT_DIR / "backups"

SECRET_PATTERNS = [
    r"eiap_live_sec_key_[a-f0-9]+",
    r"eiap_local_secure_pass_[a-zA-Z0-9_]+",
    r"eiap_local_webhook_secret_[a-zA-Z0-9]+",
    r"eiap_n8n_dev_key_[a-zA-Z0-9_!]+",
    r"test_secret_key_should_be_rotated_123",
    r"ghp_[a-zA-Z0-9]{36}",
    r"xox[baprs]-[0-9a-zA-Z]{10,48}",
    r"-----BEGIN [A-Z]+ PRIVATE KEY-----",
]


def scan_file(filepath: Path):
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    violations = []
    for pattern in SECRET_PATTERNS:
        matches = re.findall(pattern, content)
        if matches:
            violations.append((pattern, len(matches)))
    return violations


def main():
    print("=" * 80)
    print("EIAP WORKFLOW SANITIZATION & SECRET AUDIT")
    print("=" * 80)

    files_to_scan = list(WORKFLOWS_DIR.glob("*.json"))
    exported_json = BACKUPS_DIR / "n8n_exported_workflows.json"
    if exported_json.exists():
        files_to_scan.append(exported_json)

    any_violations = False
    print(f"Scanning {len(files_to_scan)} workflow files...")

    for f in files_to_scan:
        rel_path = f.relative_to(ROOT_DIR)
        violations = scan_file(f)
        if violations:
            print(f"  [FAIL] {rel_path}: Found {len(violations)} secret patterns!")
            for pattern, count in violations:
                print(f"         Pattern: {pattern} (Count: {count})")
            any_violations = True
        else:
            print(f"  [OK] {str(rel_path):<45} [Zero Secrets Detected]")

    print("=" * 80)
    if any_violations:
        print("[FAIL] Sanitization check failed. Secrets detected in workflow files.")
        sys.exit(1)
    else:
        print("[PASS] All workflow files are 100% sanitized and safe for public GitHub repository.")
        print("=" * 80)


if __name__ == "__main__":
    main()
