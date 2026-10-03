# Deploying the MITA MCP service (Railway)

The MCP service is a **second Railway service** in project "Mita Finance",
built from the same repository and branch as `mita-production`. It does not
replace or change the API service.

| | `mita-production` (API, unchanged) | `mita-mcp` (new) |
|---|---|---|
| Build | Nixpacks + `start.sh` | Dockerfile `deploy/mcp/Dockerfile` |
| Config file | — | `deploy/mcp/railway.json` |
| Start | `bash start.sh` (runs `alembic upgrade head`) | `python -m app.mcp` (never migrates) |
| Health | `GET /health` | `GET /health` → 200 only when the DB and the `mcp_oauth_*` tables are reachable |
| Public host | `mita-production-production.up.railway.app` | `MCP_PUBLIC_URL`, recommended `https://mcp.mitafinance.com` |

## Order of operations (first release)

1. **Migration 0037 must reach production first.** It ships with the API
   (`start.sh` applies it on deploy). Until it has, `mita-mcp` reports 503 on
   `/health`, which is intended.
2. Create `mita-mcp`, set variables, set the config file path, deploy.
3. Attach the custom domain and DNS (OWNER_ACTIONS O-6, O-7).
4. Verify (below), then register the app with OpenAI.

## Environment variables (`mita-mcp`)

| Variable | Value | Secret |
|---|---|---|
| `ENVIRONMENT` | `production` | |
| `DATABASE_URL` | same database as the API (Railway reference to `mita-production`'s variable, or a dedicated least-privilege role — see below) | yes |
| `MCP_PUBLIC_URL` | `https://mcp.mitafinance.com` (origin only, no path) | |
| `MCP_AUTH_MODE` | `builtin` | |
| `MCP_OAUTH_PRIVATE_KEY` | from `scripts/mcp/generate_keys.py` | yes |
| `MCP_LOGIN_CSRF_SECRET` | from `generate_keys.py` (consent-page CSRF only) | yes |
| `MCP_GRANT_FINGERPRINT_SECRET` | from `generate_keys.py`, independent of the CSRF secret; binds grants to the password hash — rotating it revokes every ChatGPT grant | yes |
| `JWT_SECRET`, `SECRET_KEY` | from `generate_keys.py` — **new random values, never the API's**; required only because `app.core.config` refuses to import in production without them; the MCP service never uses them | yes |
| `MCP_METRICS_TOKEN` | from `generate_keys.py` (enables `/metrics`) | yes |
| `OPENAI_APPS_CHALLENGE_TOKEN` | token shown in the OpenAI dashboard for domain verification | |
| `MCP_SUPPORT_URL` | public support page URL (shown on the consent page) | |
| `LOG_LEVEL` | `INFO` | |
| optional | `MCP_ACCESS_TOKEN_TTL_SECONDS` (900), `MCP_REFRESH_TOKEN_TTL_SECONDS` (2592000), `MCP_TOOL_CALLS_PER_MINUTE` (60), `MCP_LOGIN_ATTEMPTS_PER_MINUTE` (10), `MCP_TRUSTED_PROXY_HOPS` (1), `MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES` (ChatGPT's two redirect URIs) | |

Never set `OPENAI_API_KEY`, SMTP or IAP variables on `mita-mcp`: it does not
use them.

### Recommended: a least-privilege database role

The MCP tools run in `READ ONLY` transactions regardless, but a dedicated role
limits what a compromised MCP process could do. Run as the database owner in
Supabase (SQL editor), then use the role in `mita-mcp`'s `DATABASE_URL`:

```sql
CREATE ROLE mita_mcp LOGIN PASSWORD '<generate>';
GRANT USAGE ON SCHEMA public TO mita_mcp;
GRANT SELECT ON users, transactions, daily_plan, goals, scheduled_expenses TO mita_mcp;
-- consent-page lockout counters (same columns the mobile login updates)
GRANT UPDATE (failed_login_attempts, account_locked_until) ON users TO mita_mcp;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  mcp_oauth_clients, mcp_oauth_authorization_codes, mcp_oauth_refresh_tokens TO mita_mcp;
GRANT SELECT ON alembic_version TO mita_mcp;
```

(Verify against Supabase's pooler role setup before applying; the pooler
username format is `<role>.<project_ref>`.)

## Verification after deploy

```bash
H=https://mcp.mitafinance.com
curl -s $H/health                                   # {"status":"ok",...}
curl -s $H/.well-known/openai-apps-challenge        # exactly the token
curl -s $H/.well-known/oauth-protected-resource/mcp # resource = $H/mcp
curl -s $H/.well-known/oauth-authorization-server   # code_challenge_methods_supported ["S256"]
curl -s -o /dev/null -w '%{http_code}\n' -X POST $H/mcp \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'    # 401
```

Then connect from ChatGPT (developer mode) with the review account and run the
five positive cases in `review/positive-test-cases.md`.

## Rollback

* **Bad MCP release:** Railway → `mita-mcp` → Deployments → previous
  deployment → Redeploy. The API is unaffected.
* **Disable the ChatGPT app immediately:** remove the custom domain from
  `mita-mcp` or scale it to 0 replicas. Existing ChatGPT connections fail
  closed (no tool returns data).
* **Revoke every ChatGPT connection:**
  `UPDATE mcp_oauth_refresh_tokens SET revoked_at = now() WHERE revoked_at IS NULL;`
  Access tokens expire within 15 minutes. To cut them immediately, rotate
  `MCP_OAUTH_PRIVATE_KEY` (all outstanding access tokens fail signature checks).
* **Migration 0037** is additive; it never needs rolling back to roll back the
  service. `alembic downgrade 0036` drops only the three `mcp_oauth_*` tables.

## Key rotation

1. Generate a new key; set the old public key as `MCP_OAUTH_PREVIOUS_PUBLIC_KEY`
   and the new private key as `MCP_OAUTH_PRIVATE_KEY`; deploy.
2. After 15 minutes (access-token lifetime) remove `MCP_OAUTH_PREVIOUS_PUBLIC_KEY`.
Refresh tokens are opaque and survive key rotation.

## Observability

* Logs: one JSON object per line on stdout (`ts`, `level`, `logger`, `msg`,
  `request_id`, and for tool calls `tool`, `outcome`, `duration_ms`,
  `subject_hash`, `client`). No tokens, amounts, merchants, e-mails or tool
  arguments; non-MCP loggers have their message text withheld.
* `X-Request-ID` is echoed on every response (accepted from the caller when it
  matches `[A-Za-z0-9._-]{8,64}`).
* `/metrics` (Prometheus text, bearer `MCP_METRICS_TOKEN`): tool calls by
  outcome, tool latency sum/count, auth failures by reason, HTTP requests by
  path group and status class. Counters are per replica.

## Known operational limits

* Rate limits are per replica (in memory). The shared account lockout in the
  database is what bounds password guessing across replicas.
* `purge_expired()` (expired codes and dead refresh tokens) has no scheduler,
  matching the API's "no periodic jobs" state. Table growth is small (one row
  per authorization/refresh); run it manually or add a cron later.
