# Technical Documentation Index: EIAP

**Project:** Enterprise Intelligence Automation Platform (EIAP)  
**Author:** Datta Sable ([https://dattasable.com/](https://dattasable.com/))  
**Repository:** [https://github.com/sabledattatray/enterprise-n8n-intelligence-automation](https://github.com/sabledattatray/enterprise-n8n-intelligence-automation)  

Welcome to the technical documentation library for the Enterprise Intelligence Automation Platform. All architecture specifications, data schemas, API contracts, security audits, and operational runbooks are indexed below.

---

## Documentation Directory

```
docs/
├── QUICKSTART.md                     # Zero-cost local developer setup and verification
├── WORKFLOW_CATALOG.md               # Complete specifications for Workflows 01 through 08
├── API_REFERENCE.md                  # REST API endpoints, schemas, headers, envelopes
├── CONFIGURATION.md                  # Environment variables, ports, mock vs real flags
├── TROUBLESHOOTING.md                # Diagnostic checklists and resolution procedures
├── PERFORMANCE.md                    # Measured latencies, throughput, and query benchmarks
├── SECURITY.md                       # Security architecture, controls, and standards
├── DISASTER_RECOVERY.md              # High-level disaster recovery architecture and SLAs
├── PORTFOLIO_CASE_STUDY.md           # In-depth architectural case study for recruiters/leads
├── RELEASE_CHECKLIST.md              # 12-point release gate verification matrix
│
├── architecture/
│   ├── PLATFORM_ARCHITECTURE.md      # Microservices topology and integration boundaries
│   ├── DATA_PIPELINE.md              # End-to-end data processing lifecycle and stages
│   ├── FAILURE_RECOVERY.md           # Incident state machine, backoff, and retry logic
│   └── DATA_MODEL.md                 # Relational star schema, dimensions, and grain
│
├── security/
│   ├── STRIDE_THREAT_MODEL.md        # Comprehensive STRIDE threat model
│   ├── SECURITY_AUDIT.md             # Automated vulnerability scan and audit report
│   ├── CREDENTIAL_MANAGEMENT.md      # Secret hierarchy, parameterization, and key rotation
│   └── HARDENING_CHECKLIST.md        # 25-point operational hardening checklist
│
├── operations/
│   └── DISASTER_RECOVERY_RUNBOOK.md  # Automated backup and isolated restore runbook
│
└── audits/
    └── DATABASE_INTEGRITY_AUDIT.md   # 15-table deep data parity and reconciliation audit
```

---

## Recommended Reading Order

1. **Recruiters & Engineering Managers:**
   - [Portfolio Case Study](PORTFOLIO_CASE_STUDY.md)
   - [Platform Architecture](architecture/PLATFORM_ARCHITECTURE.md)
2. **Developers & Reviewers:**
   - [Developer Quickstart](QUICKSTART.md)
   - [Workflow Catalog](WORKFLOW_CATALOG.md)
   - [API Reference](API_REFERENCE.md)
3. **Data Engineers & Architects:**
   - [Data Pipeline Architecture](architecture/DATA_PIPELINE.md)
   - [Data Architecture & Star Schema Model](architecture/DATA_MODEL.md)
   - [Performance Benchmarks](PERFORMANCE.md)
4. **DevOps & Security Engineers:**
   - [STRIDE Threat Model](security/STRIDE_THREAT_MODEL.md)
   - [Security Audit Report](security/SECURITY_AUDIT.md)
   - [Disaster Recovery Runbook](operations/DISASTER_RECOVERY_RUNBOOK.md)
   - [Operational Troubleshooting](TROUBLESHOOTING.md)
