.PHONY: help setup test lint run down clean db-upgrade db-downgrade smoke

PYTHON ?= ./.venv/Scripts/python.exe
PYTEST ?= ./.venv/Scripts/pytest.exe
ALEMBIC ?= ./.venv/Scripts/alembic.exe

help:
	@echo "Available commands:"
	@echo "  make setup        - Install dependencies and generate synthetic data"
	@echo "  make test         - Run automated pytest suite"
	@echo "  make smoke        - Run end-to-end integration smoke tests"
	@echo "  make run          - Launch Docker Compose development stack"
	@echo "  make down         - Stop Docker Compose services"
	@echo "  make db-upgrade   - Run Alembic database migrations"
	@echo "  make db-downgrade - Roll back database migration by 1 step"
	@echo "  make clean        - Remove caches and temporary test files"

setup:
	$(PYTHON) -m pip install -r apps/api/requirements.txt
	$(PYTHON) data/generators/seed_generator.py

test:
	$(PYTEST) -v

smoke:
	$(PYTHON) scripts/smoke_test.py

run:
	docker compose up -d

down:
	docker compose down

db-upgrade:
	$(ALEMBIC) upgrade head

db-downgrade:
	$(ALEMBIC) downgrade -1

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage

