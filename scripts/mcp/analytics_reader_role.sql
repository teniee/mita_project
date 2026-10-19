-- Least-privilege read role for product analytics (Metabase or the report script).
--
-- Run ONCE per environment as the database owner, with psql:
--   psql "$DATABASE_URL" -v reader_password="$(openssl rand -hex 24)" \
--        -f scripts/mcp/analytics_reader_role.sql
-- Store the password only in Metabase's connection settings / a secret store.
--
-- The role can read the `analytics` schema (events + aggregate views) and
-- nothing else: no `public` tables (users, password hashes, transactions,
-- OAuth tokens, feedback rows, the identity link). The views that summarise
-- public tables (registrations_daily, feedback, storage) run with their
-- owner's privileges and expose only aggregates or the feedback columns.
-- Not part of a migration on purpose: roles are cluster-wide objects.

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE mita_analytics_reader LOGIN PASSWORD %L', :'reader_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mita_analytics_reader')
\gexec

ALTER ROLE mita_analytics_reader SET default_transaction_read_only = on;
ALTER ROLE mita_analytics_reader SET statement_timeout = '30s';
ALTER ROLE mita_analytics_reader CONNECTION LIMIT 5;

SELECT format('GRANT CONNECT ON DATABASE %I TO mita_analytics_reader', current_database())
\gexec

REVOKE ALL ON SCHEMA public FROM mita_analytics_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM mita_analytics_reader;
GRANT USAGE ON SCHEMA analytics TO mita_analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO mita_analytics_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics GRANT SELECT ON TABLES TO mita_analytics_reader;
-- Thresholds are the team's to tune; the reader may not change them.
REVOKE INSERT, UPDATE, DELETE ON analytics.segment_thresholds FROM mita_analytics_reader;
