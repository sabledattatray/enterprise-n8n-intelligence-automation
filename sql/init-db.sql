-- ==============================================================================
-- Dual Database Initialization Script for Local PostgreSQL
-- Creates isolated logical databases for Analytics and n8n internal state
-- ==============================================================================

SELECT 'CREATE DATABASE business_analytics'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'business_analytics')\gexec

SELECT 'CREATE DATABASE n8n_internal'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n_internal')\gexec

-- Grant full privileges to default admin user
GRANT ALL PRIVILEGES ON DATABASE business_analytics TO eiap_admin;
GRANT ALL PRIVILEGES ON DATABASE n8n_internal TO eiap_admin;

