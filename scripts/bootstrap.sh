#!/usr/bin/env bash
set -euo pipefail

echo "================================================================="
echo "EIAP Local Development Environment Bootstrap (Linux / macOS)"
echo "================================================================="

# 1. Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[1/5] Creating Python virtual environment in .venv..."
    python3 -m venv .venv
fi

# 2. Dependencies
echo "[2/5] Installing Python dependencies..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r apps/api/requirements.txt

# 3. Data Generation
echo "[3/5] Generating deterministic synthetic datasets..."
.venv/bin/python data/generators/seed_generator.py

# 4. Environment
if [ ! -f ".env" ]; then
    echo "[4/5] Copying .env.example to .env..."
    cp .env.example .env
fi

# 5. Docker Stack
echo "[5/5] Starting Docker Compose stack..."
docker compose up -d --build

echo "Bootstrap complete! Run '.venv/bin/python scripts/smoke_test.py' to verify."

