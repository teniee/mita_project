-- Least-privilege role for MITA's regional ingestion job (app/regional/ingest.py).
--
-- Run ONCE per environment as the database owner, AFTER migration 0044
-- (every statement is idempotent):
--   psql "$DATABASE_URL" -v ingest_password="$(openssl rand -hex 24)" \
--        -f scripts/mcp/regional_ingest_role.sql
-- then give the job (and only the job) a DATABASE_URL with user
-- mita_regional_ingest and that password.
--
-- What the job needs: write the shared statistics and its own run records.
-- Nothing else: no user table, no financial table, no DDL. The MCP service
-- reads regional_observations as mita_mcp (SELECT, mcp_service_role.sql).

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE mita_regional_ingest LOGIN PASSWORD %L', :'ingest_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mita_regional_ingest')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO mita_regional_ingest', current_database())
\gexec

GRANT USAGE ON SCHEMA public TO mita_regional_ingest;
-- SELECT too: the upsert compares with what is stored; no DELETE — a value
-- a provider no longer publishes stays as last confirmed.
GRANT SELECT, INSERT, UPDATE ON regional_observations, regional_ingestion_runs
  TO mita_regional_ingest;
GRANT USAGE ON SEQUENCE regional_observations_id_seq TO mita_regional_ingest;
