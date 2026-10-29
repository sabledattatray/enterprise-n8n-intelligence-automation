# Contributing to Enterprise Intelligence Automation Platform (EIAP)

Thank you for your interest in contributing to the **Enterprise Intelligence Automation Platform (EIAP)**! We welcome contributions that improve data quality validation, enhance SQL ETL performance, expand n8n workflows, and strengthen security controls.

---

## 1. Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](file:///d:/Datta%20Sable/N8N%20Project/CODE_OF_CONDUCT.md). Please report unacceptable behavior to the maintainer at [https://dattasable.com/](https://dattasable.com/).

---

## 2. Development Setup & Workflow

Follow our [Zero-Cost Quickstart Guide](file:///d:/Datta%20Sable/N8N%20Project/docs/QUICKSTART.md) to set up your local development environment:

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/enterprise-n8n-intelligence-automation.git
   cd enterprise-n8n-intelligence-automation
   ```
2. **Create a local branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Configure environment:**
   ```bash
   cp .env.example .env
   docker compose up -d --build
   alembic upgrade head
   ```

---

## 3. Strict Contribution Standards

### 1. Zero Plaintext Credentials
Never embed API tokens, database passwords, or private keys in code, configuration, or exported workflow JSON files.
- All HTTP Request nodes in n8n must reference environment variables: `={{ $env.API_KEY }}`.
- Always run the secret scanner before committing:
  ```bash
  python scripts/verify_workflow_sanitization.py
  ```

### 2. Maintain Test Integrity
All pull requests must pass the complete automated test suite with 0 failures and 0 warnings:
```bash
pytest -v
```
When introducing new endpoints or workflows, add corresponding contract and integration tests in `tests/contract/` and `tests/integration/`.

### 3. Dependency Security
Do not add dependencies with known vulnerabilities. Run `pip-audit` prior to submitting changes:
```bash
pip-audit -r apps/api/requirements.txt
```

---

## 4. Pull Request Submission

1. Ensure your branch is rebased on `main`.
2. Commit with clear, conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`).
3. Open a Pull Request referencing the relevant issue using our [Pull Request Template](file:///d:/Datta%20Sable/N8N%20Project/.github/PULL_REQUEST_TEMPLATE.md).

