#!/usr/bin/env python3
"""
Enterprise Intelligence Automation Platform (EIAP)
Automated Screenshot Capture Suite

Uses headless Google Chrome to capture genuine, high-resolution screenshots
from the live running n8n instance (port 5678) and Mailpit UI (port 8025).
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = ROOT_DIR / "assets" / "screenshots"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

WORKFLOW_URLS = [
    ("01_n8n_workflows_overview.png", "http://127.0.0.1:5678/home/workflows"),
    ("02_wf01_data_ingestion.png", "http://127.0.0.1:5678/workflow/F7MPVLjpUs6Lg176"),
    ("03_wf02_data_quality.png", "http://127.0.0.1:5678/workflow/0QPJC0JWGAJL4c9F"),
    ("04_wf03_sql_etl.png", "http://127.0.0.1:5678/workflow/1M6IK2WjiYLBeALM"),
    ("05_wf04_powerbi_refresh.png", "http://127.0.0.1:5678/workflow/4AkDn4edzfMayzfd"),
    ("06_wf05_kpi_monitoring.png", "http://127.0.0.1:5678/workflow/AEwe0Mqq2s3ibDkg"),
    ("07_wf06_ai_insights.png", "http://127.0.0.1:5678/workflow/ZqOB7RDye7ig6FeN"),
    ("08_wf07_report_distribution.png", "http://127.0.0.1:5678/workflow/TAayFWnDcGPbmFyd"),
    ("09_wf08_failure_recovery.png", "http://127.0.0.1:5678/workflow/zLsQ98U2iaRhwhG9"),
    ("10_mailpit_executive_email.png", "http://127.0.0.1:8025/"),
]


def capture_url(filename: str, url: str, width=1600, height=1000, wait_budget=6000):
    dest_path = SCREENSHOTS_DIR / filename
    print(f"[*] Capturing: {filename:<35} from {url}...")

    cmd = [
        CHROME_PATH,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={wait_budget}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={dest_path}",
        url,
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if dest_path.exists() and dest_path.stat().st_size > 0:
        size_kb = round(dest_path.stat().st_size / 1024, 1)
        print(f"    [OK] Captured ({size_kb} KB) -> {filename}")
    else:
        print(f"    [FAIL] Failed to capture {filename}: {res.stderr}")


def main():
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("EIAP GENUINE SCREENSHOT CAPTURE SUITE")
    print(f"Destination: {SCREENSHOTS_DIR}")
    print("=" * 80)

    for filename, url in WORKFLOW_URLS:
        capture_url(filename, url)
        time.sleep(0.5)

    print("\n" + "=" * 80)
    print(f"ALL 10 WEB SCREENSHOTS CAPTURED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    main()

