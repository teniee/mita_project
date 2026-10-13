# MITA MCP — staging (observed 2026-10-03, v2 update 2026-10-13)

## What exists

| Item | Value | Status |
|---|---|---|
| Railway project | `mita-mcp-staging` (`497476f2-de93-44b7-b170-2b175c8d5621`) — **separate project**, no access to the production project's variables, services or database | STAGING VERIFIED |
| Environment | `staging` (`0f67cf7a-5ce4-472e-a842-2e5448d64c08`) | STAGING VERIFIED |
| MCP service | `mita-mcp-staging` (`833466fc-f7f2-4d51-8db1-48edfbb46057`), Dockerfile `deploy/mcp/Dockerfile`, healthcheck `/health`, restart ON_FAILURE ×5, **1 replica** (region `asia-southeast1-eqsg3a`), source `teniee/mita_project` @ `feat/chatgpt-plugin` **pinned to commit `461abcf`** (v2.0.0) since 2026-10-13, deployment `174528cf-a617-4ad4-88f1-0562355d4602` (before: `fcd7ae3` from 2026-10-11, `842d365` on which the v1 real-ChatGPT acceptance ran). Pushes do not redeploy it | STAGING VERIFIED |
| Database | Railway Postgres 18 template (18.6), private network only, alembic `0039`. The MCP service connects as the least-privilege role `mita_mcp` (`scripts/mcp/mcp_service_role.sql`) on `postgres.railway.internal`; the read-only `mita_analytics_reader` exists (password not kept — reset before use). Temporary TCP proxies used for migrations (2026-10-03, 2026-10-13) were removed and verified unreachable | STAGING VERIFIED |
| Public URL | `https://mita-mcp-staging-staging.up.railway.app` (Railway-managed TLS) | STAGING VERIFIED |
| Custom domain | none (not needed for staging) | — |

Why one replica: OAuth/tool/login rate limits are in-memory per replica
(`app/mcp/ratelimit.py`). Do not scale `mita-mcp-staging` above 1 until they
move to Redis.

Why pinned: staging must run exactly the reviewed code. To deploy a newer
commit: Railway → mita-mcp-staging → Settings → Source → set the commit, or
`connect-service-source` with `commitSha`.

Note: Railway now reports config-as-code (`railway.json`) as **deprecated**;
the service settings above were set directly on the service.
`deploy/mcp/railway.json` remains only as a record of the intended values.

## Environment variables (complete set read by the code)

From `app/mcp/config.py`, `app/mcp/__main__.py` and `app/core/config.py`.

| Variable | Required | Purpose | How to generate | Secret? |
|---|---|---|---|---|
| `ENVIRONMENT` | yes | `staging` or `production`; both are strict (HTTPS-only public URL, no localhost/test Host allowances) | literal | no |
| `MCP_PUBLIC_URL` | yes | public origin (no path); resource = `<origin>/mcp`, issuer = origin | the Railway or custom domain | no |
| `DATABASE_URL` | yes | this environment's PostgreSQL | Railway reference `${{Postgres.DATABASE_URL}}` | yes |
| `MCP_OAUTH_PRIVATE_KEY` | yes (builtin auth) | RS256 signing key for access tokens; `kid` = RFC 7638 thumbprint, derived automatically | `scripts/mcp/generate_keys.py` | yes |
| `MCP_OAUTH_PREVIOUS_PUBLIC_KEY` | no | verify-only key during rotation | public half of the old key | no |
| `MCP_LOGIN_CSRF_SECRET` | yes | consent-page CSRF + pending-request HMAC only | `generate_keys.py` | yes |
| `MCP_GRANT_FINGERPRINT_SECRET` | yes | HMAC binding grants to the password hash; must differ from the CSRF secret; rotating it revokes all ChatGPT grants | `generate_keys.py` | yes |
| `MCP_DATA_SECRET` | yes | keys for opaque transaction references, signed budget drafts and list cursors (HKDF per purpose); rotating it only invalidates outstanding ones | `generate_keys.py` | yes |
| `MCP_ANALYTICS_SECRET` | yes | HMAC key for pseudonymous analytics ids; must stay stable (rotation splits every user's history) | `generate_keys.py` | yes |
| `JWT_SECRET`, `SECRET_KEY` | production: yes; staging: recommended | required by `app.core.config` at import in production; unused by MCP; never the API's values | `generate_keys.py` | yes |
| `MCP_METRICS_TOKEN` | no | enables `/metrics` (bearer) | `generate_keys.py` | yes |
| `MCP_AUTH_MODE` | no (`builtin`) | `builtin` or `external` | literal | no |
| `MCP_EXTERNAL_ISSUER`, `MCP_EXTERNAL_JWKS_URL`, `MCP_EXTERNAL_USER_CLAIM` | external mode only | external IdP | from the IdP | no |
| `MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES` | no | redirect policy (default: ChatGPT's two forms) | literal | no |
| `MCP_ACCESS_TOKEN_TTL_SECONDS` / `MCP_REFRESH_TOKEN_TTL_SECONDS` | no (900 / 2592000) | token lifetimes | literal | no |
| `MCP_TOOL_CALLS_PER_MINUTE` / `MCP_LOGIN_ATTEMPTS_PER_MINUTE` / `MCP_OAUTH_REQUESTS_PER_MINUTE` / `MCP_REGISTRATIONS_PER_HOUR` | no (60 / 10 / 30 / 5) | per-replica rate limits (sign-ups per IP per hour) | literal | no |
| `MCP_TRUSTED_PROXY_HOPS` | no (1) | `X-Forwarded-For` hops (Railway = 1) | literal | no |
| `MCP_SUPPORT_URL` | no | link on the consent page | literal | no |
| `OPENAI_APPS_CHALLENGE_TOKEN` | for OpenAI domain verification only | body of `/.well-known/openai-apps-challenge` | OpenAI dashboard | no |
| `PORT` | no (8080) | listen port (domain targets 8080) | literal | no |
| `LOG_LEVEL`, `FORWARDED_ALLOW_IPS` | no | logging / uvicorn proxy headers | literal | no |

Set on staging (names only): `DATABASE_URL` (role `mita_mcp`), `ENVIRONMENT, JWT_SECRET, LOG_LEVEL,
MCP_ANALYTICS_SECRET, MCP_AUTH_MODE, MCP_DATA_SECRET, MCP_GRANT_FINGERPRINT_SECRET,
MCP_LOGIN_ATTEMPTS_PER_MINUTE, MCP_LOGIN_CSRF_SECRET, MCP_METRICS_TOKEN,
MCP_OAUTH_PRIVATE_KEY, MCP_OAUTH_REQUESTS_PER_MINUTE, MCP_PUBLIC_URL,
MCP_TOOL_CALLS_PER_MINUTE, MCP_TRUSTED_PROXY_HOPS, PORT, SECRET_KEY`. All
secrets were generated fresh for staging with `generate_keys.py --out` and
pushed with the Railway CLI (`--stdin`; the two v2 secrets on 2026-10-13);
the local copies were deleted. No production value was used.

## Database

* Migrated from the operator machine (the MCP container never migrates):
  empty → `0037` on 2026-10-03, `0037 → 0039` on 2026-10-13
  (`alembic current` = `0039 (head)`).
* `mcp_oauth_authorization_codes` and `mcp_oauth_refresh_tokens` include
  `token_version` and `credential_fingerprint`.
* Seeded with `scripts/mcp/seed_staging_db.py` (canonical writers only):
  one account `staging-review@example.test`, Europe/Sofia, EUR, stated income
  4,200, profile-derived October 2026 plan (2,358.00 over 91 rows), 7 live
  expenses totalling 246.94 with merchants prefixed "Staging", one
  soft-deleted 999.99 "Staging DELETED Purchase", one goal, rent (monthly) and
  insurance (once) scheduled. Contents verified: 1 user, 7 live + 1 deleted
  transactions, 0 leftover OAuth clients.

## Re-running the checks

```bash
# from a directory linked to the staging project (railway link …)
railway run --service Postgres -- sh -c '…'   # needs a temporary TCP proxy for local DB access
PYTHONPATH=. .venv-mcp/bin/python scripts/mcp/e2e_http.py \
  --base-url https://mita-mcp-staging-staging.up.railway.app \
  --database-url "$STAGING_DB_URL" --state /tmp/e2e.json --phase first
# restart the service, then --phase after-restart
PYTHONPATH=. .venv-mcp/bin/python scripts/mcp/staging_failure_modes.py \
  --base-url https://mita-mcp-staging-staging.up.railway.app --database-url "$STAGING_DB_URL"
```

Both scripts create a temporary fake user and delete it; neither prints
tokens, codes or passwords; both refuse production hosts. v2 adds
`scripts/mcp/e2e_v2.py --base-url … [--database-url …]` (the acceptance
conversation; results in `staging-acceptance-v2.md`).

## Tearing staging down

Railway → project `mita-mcp-staging` → Settings → Danger → Delete project.
Nothing in production depends on it.
