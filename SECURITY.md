# Security Policy

## Reporting a Vulnerability

Security is a foundational pillar of the **Enterprise Intelligence Automation Platform (EIAP)**.
If you discover a security vulnerability or credential exposure risk, please do not open a public issue.
Instead, report findings responsibly to the author via email:
`security@dattasable.com` (or submit via private security advisory on GitHub).

## Supported Versions

| Version | Supported | Security Maintenance |
| :--- | :--- | :--- |
| `1.0.x` | :white_check_mark: | Active patches and container dependency updates |
| `< 1.0` | :x: | Development / pre-release builds |

## Security Architecture & Best Practices

1. **Zero Credential Exposure:**
   - Production secrets, service principals, database passwords, and API keys are never committed to version control.
   - Workflows are exported without embedded credentials; parameters are referenced through environment variables (`{{ $env.VAR_NAME }}`).
2. **Localhost-Only Exposure:**
   - All Docker Compose ports are explicitly bound to `127.0.0.1` (`127.0.0.1:5433`, `127.0.0.1:8000`, `127.0.0.1:5678`, `127.0.0.1:8025`). No container ports are exposed to public interfaces (`0.0.0.0`) by default.
3. **Database Role Partitioning:**
   - The platform strictly enforces least-privilege database roles. The application engine connects using non-superuser credentials. n8n internal metadata tables are hosted in an isolated database (`n8n_internal`) completely separate from curated analytics data.
4. **Input Sanitization & Injection Prevention:**
   - All inbound payloads are validated through Pydantic schemas.
   - All database queries use parameterized SQL via SQLAlchemy ORM; dynamic string concatenation is prohibited.
5. **PII Masking & Data Minimization:**
   - Outbound recipient emails are one-way hashed with SHA-256 (`recipient_hash`) in audit tables.
   - AI summarization modules receive only pre-aggregated, non-sensitive KPI snapshots; raw transactional records are never sent to external LLMs.

