# ==============================================================================
# Enterprise Intelligence Automation Platform (EIAP) - Windows 11 Bootstrap
# ==============================================================================
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "EIAP Local Development Environment Bootstrap (Windows 11)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Check Python
$pyCmd = py -0p 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python 3.12+ not found. Please install Python 3.12+ from python.org"
    exit 1
}
Write-Host "[1/6] Python runtime detected." -ForegroundColor Green

# 2. Virtual Environment
if (!(Test-Path ".venv")) {
    Write-Host "[2/6] Creating Python 3.12 virtual environment in .venv..." -ForegroundColor Yellow
    py -3.12 -m venv .venv
} else {
    Write-Host "[2/6] Virtual environment .venv already exists." -ForegroundColor Green
}

# 3. Install Dependencies
Write-Host "[3/6] Installing Python dependencies..." -ForegroundColor Yellow
.\.venv\Scripts\pip.exe install --upgrade pip
.\.venv\Scripts\pip.exe install -r apps\api\requirements.txt

# 4. Generate Fixtures
Write-Host "[4/6] Generating deterministic synthetic datasets..." -ForegroundColor Yellow
.\.venv\Scripts\python.exe data\generators\seed_generator.py

# 5. Environment File
if (!(Test-Path ".env")) {
    Write-Host "[5/6] Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
} else {
    Write-Host "[5/6] Configuration file .env exists." -ForegroundColor Green
}

# 6. Docker Stack
Write-Host "[6/6] Starting Docker Compose stack..." -ForegroundColor Yellow
docker compose up -d --build

Write-Host "`nBootstrap Complete! Run '.\.venv\Scripts\python.exe scripts\smoke_test.py' to verify." -ForegroundColor Cyan

