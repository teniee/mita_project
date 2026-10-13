# Deploying the MITA MCP service (Railway)

The MCP service is a **second Railway service** in project "Mita Finance",
built from the same repository and branch as `mita-production`. It does not
replace or change the API service.

| | `mita-production` (API, unchanged) | `mita-mcp` (new) |
|---|---|---|
| Build | Nixpacks + `start.sh` | Dockerfile `deploy/mcp/Dockerfile` |
| Service settings | — | set on the service: Dockerfile `deploy/mcp/Dockerfile`, healthcheck `/health`, 1 replica (Railway deprecated config-as-code; `deploy/mcp/railway.json` is kept only as a record) |
| Start | `bash start.sh` (runs `alembic upgrade head`) | `python -m app.mcp` (never migrates) |
| Health | `GET /health` | `GET /health` → 200 only when the DB and the `mcp_oauth_*` tables are reachable |
| Public host | `mita-production-production.up.railway.app` | `MCP_PUBLIC_URL`, recommended `https://mcp.mitafinance.com` |

## Order of operations (first release)

Full plan with owner steps: `production-readiness.md` (Steps 6–7) and
OWNER_ACTIONS O-6, O-7, O-11.

0. **Give `mita-production` a Railway healthcheck (`/health`) first.** As of
   2026-10-11 it has none, so Railway marks a new deployment Active as soon as
   the container starts and stops the old one — a failed boot migration would
   leave no serving deployment. `/health` answers 200 even when degraded.
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
| `DATABASE_URL` | same database as the API: Railway Postgres 17 `mita-production-db` on the private host `mita-production-db.railway.internal` (docs/owner-dependencies-checklist.md). Railway listed no `DATABASE_URL` variable on that service on 2026-10-11 (only `PG*`/`POSTGRES_*`), so build it the way `mita-production`'s is built — or use the least-privilege role below | yes |
| `MCP_PUBLIC_URL` | `https://mcp.mitafinance.com` (origin only, no path) | |
| `MCP_AUTH_MODE` | `builtin` | |
| `MCP_OAUTH_PRIVATE_KEY` | from `scripts/mcp/generate_keys.py` | yes |
| `MCP_LOGIN_CSRF_SECRET` | from `generate_keys.py` (consent-page CSRF only) | yes |
| `MCP_GRANT_FINGERPRINT_SECRET` | from `generate_keys.py`, independent of the CSRF secret; binds grants to the password hash — rotating it revokes every ChatGPT grant | yes |
| `MCP_DATA_SECRET` | from `generate_keys.py`; keys for opaque expense refs, signed budget drafts and list cursors (rotating it only invalidates outstanding ones) | yes |
| `MCP_ANALYTICS_SECRET` | from `generate_keys.py`; HMAC key for pseudonymous analytics ids — **keep it stable** (rotation splits every user's usage history) | yes |
| `JWT_SECRET`, `SECRET_KEY` | from `generate_keys.py` — **new random values, never the API's**; required only because `app.core.config` refuses to import in production without them; the MCP service never uses them | yes |
| `MCP_METRICS_TOKEN` | from `generate_keys.py` (enables `/metrics`) | yes |
| `OPENAI_APPS_CHALLENGE_TOKEN` | token shown in the OpenAI dashboard for domain verification | |
| `MCP_SUPPORT_URL` | public support page URL (shown on the consent page) | |
| `LOG_LEVEL` | `INFO` | |
| optional | `MCP_ACCESS_TOKEN_TTL_SECONDS` (900), `MCP_REFRESH_TOKEN_TTL_SECONDS` (2592000), `MCP_TOOL_CALLS_PER_MINUTE` (60), `MCP_LOGIN_ATTEMPTS_PER_MINUTE` (10), `MCP_REGISTRATIONS_PER_HOUR` (5), `MCP_TRUSTED_PROXY_HOPS` (1), `MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES` (ChatGPT's two redirect URIs) | |

Never set `OPENAI_API_KEY`, SMTP or IAP variables on `mita-mcp`: it does not
use them.

### Recommended: a least-privilege database role

Since v2 the service writes (sign-up, expenses, plans, obligations, goals,
feedback, analytics) through the canonical domain writers, so the role needs
exactly those writes and nothing else. Run, as the database owner and AFTER
migrations 0037–0039, `scripts/mcp/mcp_service_role.sql`:

```bash
psql "$OWNER_DATABASE_URL" -v mcp_password="$(openssl rand -hex 24)" \
     -f scripts/mcp/mcp_service_role.sql
```

then build `mita-mcp`'s `DATABASE_URL` with user `mita_mcp`. Verified
2026-10-12 by running the full acceptance conversation
(`scripts/mcp/e2e_v2.py`, 70 checks) against a server connected as this role:
0 errors and 0 warnings — including the non-blocking redistribution audit
writes, which need `SELECT` as well as `INSERT` because the ORM inserts with
`RETURNING`. The role cannot run DDL or read any other table.

For product analytics, `scripts/mcp/analytics_reader_role.sql` creates the
separate read-only `mita_analytics_reader` (schema `analytics` only) for
Metabase or `scripts/mcp/analytics_report.py`.

(Production moved from Supabase to Railway Postgres; there is no pooler, so
the role name is used as-is.)

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
  MCP service. `alembic downgrade 0036` drops only the three `mcp_oauth_*` tables.
* **Rolling back the API is different.** Once production is at 0037, a
  pre-merge API deployment cannot boot: its `start.sh` runs
  `alembic upgrade head` with code that does not know 0037 (`Can't locate
  revision identified by '0037'`, reproduced 2026-10-11), and production
  aborts on a failed migration. Fix forward, or run `alembic downgrade 0036`
  from the merged code before rolling the API back.

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
