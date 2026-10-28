# MITA MCP — staging (observed 2026-10-03, v2 update 2026-10-13, credentials rotated 2026-10-23, `dbdc118` — MCP 2.2.0 — deployed 2026-10-24)

## What exists

| Item | Value | Status |
|---|---|---|
| Railway project | `mita-mcp-staging` (`497476f2-de93-44b7-b170-2b175c8d5621`) — **separate project**, no access to the production project's variables, services or database | STAGING VERIFIED |
| Environment | `staging` (`0f67cf7a-5ce4-472e-a842-2e5448d64c08`) | STAGING VERIFIED |
| MCP service | `mita-mcp-staging` (`833466fc-f7f2-4d51-8db1-48edfbb46057`), Dockerfile `deploy/mcp/Dockerfile`, healthcheck `/health`, restart ON_FAILURE ×5, **1 replica** (region `asia-southeast1-eqsg3a`), source `teniee/mita_project` @ `feat/chatgpt-auth-ui` **pinned to commit `dbdc118`** (MCP 2.2.0: the financial calendar in ChatGPT and the v4 sign-in page) since 2026-10-24 20:10 UTC, deployment `7fd7783b-d910-4c7b-b32b-324fb693a751`. Deploy another commit by connecting the source again with it — not "Redeploy", which rebuilds the current one (before: `de96251` / `b4f6d2fd` from 2026-10-23 20:13 UTC — the v3 sign-in page, not approved, and `opentelemetry-api` 1.45.1 —, `1e24bf4` / `dd8b4894` from 2026-10-23 18:02 UTC, `ee388c0` / `33783139` from 2026-10-23 12:12 UTC, `79efb1d` / `87d26668` 2.1.0 from 2026-10-18 — the re-pin of 2026-10-21 waited for Railway's build pause —, `461abcf` / `174528cf` 2.0.0 from 2026-10-13, `fcd7ae3` from 2026-10-11, `842d365` on which the v1 real-ChatGPT acceptance ran). Pushes do not redeploy it | STAGING VERIFIED |
| Database | Railway Postgres 18 template (18.6), private network only, alembic `0039`. The MCP service connects as the least-privilege role `mita_mcp` (`scripts/mcp/mcp_service_role.sql`) on `postgres.railway.internal`; the read-only `mita_analytics_reader` exists (password not kept — reset before use). Both stored passwords were rotated on 2026-10-23 (see "Credential rotation"). Temporary TCP proxies used for migrations and checks (2026-10-03, 2026-10-13, 2026-10-18, three times on 2026-10-23) were removed and verified no longer serving Postgres; none was opened on 2026-10-24 (no migration; see "Left on staging") | STAGING VERIFIED |
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
| `MCP_WIDGET_DOMAIN` | production: yes (startup refuses without it, since 2026-10-27); staging: set it for the real-ChatGPT acceptance | https origin (no path; a trailing `/` is dropped) for the calendar component's `_meta.ui.domain`; unset = the host's shared sandbox origin | the service's own origin (staging: `https://mita-mcp-staging-staging.up.railway.app`) | no |
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
the local copies were deleted. No production value was used. All of them
were rotated on 2026-10-23 after Railway's security incident (below).

## MCP 2.3.0 — deployed 2026-10-28 (`2817bb6`, deployment `724189ec`)

`MCP_WIDGET_DOMAIN=https://mita-mcp-staging-staging.up.railway.app` set with
`--skip-deploys` before the re-pin; no migration (head `0039`).

## Next deployment: MCP 2.4.0, F-11 (NOT executed — owner approval first)

`user-budget-lines.md`. Needs a migration and a grant, in this order (2.4.0
reads `mcp_budget_lines`):

1. Commit, push, green CI on that SHA.
2. Temporary TCP proxy to the staging Postgres; from the operator machine
   `alembic upgrade head` (`0039 → 0040`, one new table) as the owner.
3. `GRANT SELECT, INSERT, UPDATE, DELETE ON mcp_budget_lines TO mita_mcp;`
   (the line in `scripts/mcp/mcp_service_role.sql`); check it with
   `has_table_privilege`.
4. Remove the proxy; check Postgres no longer answers there.
5. Re-pin `mita-mcp`; `/health` → `2.4.0`; `scripts/mcp/e2e_http.py` and
   `staging_failure_modes.py`.
6. Rollback: re-pin `2817bb6` (it ignores the table; `0040` can stay).

## Credential rotation (done 2026-10-23, after Railway's security incident)

Railway disclosed on 2026-10-21 that environment variables may have been
read. No value is ever printed: secrets go from a 0600 file to the CLI's
stdin, checks print names and booleans, and the files are deleted after.

1. **App secrets:** `scripts/mcp/generate_keys.py --out <0600 file>`, then
   for each name `railway variable set NAME --stdin --skip-deploys -p … -e …
   -s …`. Proof: SHA-256 fingerprints compared under `railway run` (changed /
   unchanged only) and each live value equal to the generated one.
2. **`postgres`:** Railway → Postgres → Database → Config → Connection →
   **Regenerate**, done by the owner. It changes the database password and
   `POSTGRES_PASSWORD` / `PGPASSWORD` / `DATABASE_URL` together and restarts
   Postgres. Never `ALTER USER postgres` or edit the variable by hand.
3. **`mita_mcp`** (Railway cannot regenerate a custom role): open a temporary
   TCP proxy; under `railway run --service Postgres`, `SET log_statement =
   'none'` and `ALTER ROLE mita_mcp WITH PASSWORD '<SCRAM-SHA-256 verifier
   computed locally>'`; write `postgresql://mita_mcp:…@postgres.railway.internal:5432/railway`
   to the 0600 file and set `DATABASE_URL` from it with `--stdin
   --skip-deploys`. Check that the old password is rejected and the new one
   accepted, then remove the proxy and check the endpoint no longer serves
   Postgres.
4. **Deploy** the pinned commit (connect the source again with it); the
   service reads the new values at start.

Consequences: every staging ChatGPT connection, access and refresh token from
before the rotation is invalid (reconnect); analytics pseudonyms restart.
Result 2026-10-23: 8 app secrets, `DATABASE_URL`, the `postgres` and
`mita_mcp` passwords rotated; both old passwords rejected; deployment
`33783139` verified (HANDOFF.md). Production was not touched.

## Left on staging (2026-10-24)

The calendar review (`scripts/mcp/calendar_widget_review.py`) ran against
staging through the public endpoints only, without the database: the TCP
proxy its clean-up needs was not opened that day. Still there:

* one fictional account `calendar-review-<8 hex>@example.com` (password not
  kept; its own month: profile, four regular payments, October and November
  plans, a goal, 26 expenses — 24 in October, 2 in September);
* the DCR client registrations of that run and of the sign-in screenshot
  run (no tokens apart from the review account's).

Remove them the next time a proxy is open, with `e2e_v2.cleanup` per account
(the `users` row alone is not enough: `transactions` has no foreign key to
`users`), then delete OAuth clients that hold no tokens and were registered
on 2026-10-24.

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

Removing the proxy: Railway's `delete-tcp-proxy` can lose its response and
still apply a little later. Confirm with `list-tcp-proxies` (empty) and a
connection attempt through the old endpoint (no Postgres answer) — the
proxy host may still accept a bare TCP handshake on the port.

## Tearing staging down

Railway → project `mita-mcp-staging` → Settings → Danger → Delete project.
Nothing in production depends on it.
