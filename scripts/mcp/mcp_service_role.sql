-- Least-privilege database role for the MITA MCP service (ChatGPT app).
--
-- Run ONCE per environment as the database owner, AFTER migrations 0037-0040
-- (re-run after a migration adds an MCP table; every statement is idempotent):
--   psql "$DATABASE_URL" -v mcp_password="$(openssl rand -hex 24)" \
--        -f scripts/mcp/mcp_service_role.sql
-- then build the MCP service's DATABASE_URL with user mita_mcp and that
-- password (keep it only in the service's variables).
--
-- What the service needs (verified by running scripts/mcp/e2e_v2.py against
-- a server connected as this role): read the user's financial data; create
-- accounts on the sign-up page; update the lockout counters and the profile
-- fields it saves; write expenses, plans, obligations and goals through the
-- canonical writers (which also write redistribution audit rows); its own
-- OAuth, setup, idempotency, feedback and analytics tables. Nothing else:
-- no DDL, no access to other tables (IAP, notifications, AI snapshots...).

\set ON_ERROR_STOP on

SELECT format('CREATE ROLE mita_mcp LOGIN PASSWORD %L', :'mcp_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mita_mcp')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO mita_mcp', current_database())
\gexec

GRANT USAGE ON SCHEMA public TO mita_mcp;
GRANT SELECT ON alembic_version TO mita_mcp;

-- Accounts: sign-up inserts; consent page lockout; profile fields the tools save.
GRANT SELECT, INSERT ON users TO mita_mcp;
GRANT UPDATE (failed_login_attempts, account_locked_until, monthly_income,
              savings_goal, currency, timezone, has_onboarded, updated_at)
  ON users TO mita_mcp;

-- Financial records, written only through the canonical domain writers.
GRANT SELECT, INSERT, UPDATE ON transactions TO mita_mcp;
GRANT SELECT, INSERT, UPDATE, DELETE ON daily_plan TO mita_mcp;
GRANT SELECT, INSERT ON goals, scheduled_expenses TO mita_mcp;
-- SELECT too: the ORM inserts with RETURNING (server-default columns).
GRANT SELECT, INSERT ON redistribution_events TO mita_mcp;

-- The MCP service's own tables (0037-0040).
GRANT SELECT, INSERT, UPDATE, DELETE ON
  mcp_oauth_clients, mcp_oauth_authorization_codes, mcp_oauth_refresh_tokens,
  mcp_user_profiles, mcp_idempotency_keys, product_feedback, analytics_identities,
  mcp_budget_lines
  TO mita_mcp;
GRANT USAGE ON SCHEMA analytics TO mita_mcp;
GRANT INSERT ON analytics.events TO mita_mcp;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA analytics TO mita_mcp;
