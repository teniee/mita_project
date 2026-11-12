# MITA MCP — staging (observed 2026-10-03, v2 update 2026-10-13, credentials rotated 2026-10-23, MCP 2.4.0 since 2026-10-28, `0af8435` deployed 2026-11-02, MCP 2.5.0 `fad9110` since 2026-11-02 22:39 UTC, MCP 2.6.0 `c5a317c` since 2026-11-03 17:58 UTC; MCP 2.7.0 `2ab2e0f` since 2026-11-04 07:27 UTC; MCP 2.8.0 `601a3d7` since 2026-11-04 23:19 UTC, alembic 0044; MCP 2.8.0 `601a3d7` since 2026-11-04 23:19 UTC; MCP 2.9.0 `789bfb6` since 2026-11-09 18:13 UTC)

## What exists

| Item | Value | Status |
|---|---|---|
| Railway project | `mita-mcp-staging` (`497476f2-de93-44b7-b170-2b175c8d5621`) — **separate project**, no access to the production project's variables, services or database | STAGING VERIFIED |
| Environment | `staging` (`0f67cf7a-5ce4-472e-a842-2e5448d64c08`) | STAGING VERIFIED |
| MCP service | `mita-mcp-staging` (`833466fc-f7f2-4d51-8db1-48edfbb46057`), Dockerfile `deploy/mcp/Dockerfile`, healthcheck `/health`, restart ON_FAILURE ×5, **1 replica** (region `asia-southeast1-eqsg3a`), source `teniee/mita_project` @ `feat/chatgpt-auth-ui` **pinned to commit `789bfb6`** (MCP 2.9.0: regional recommendations) since 2026-11-09 18:13 UTC, deployment `20c1191f-1a0d-45e7-a4a1-90e2289a09be` (before: `601a3d7` / `618cd6d9` 2.8.0 from 2026-11-04 23:19 UTC, `2ab2e0f` / `390805cb` 2.7.0 from 2026-11-04 07:27 UTC, `c5a317c` / `62d3a0d1` 2.6.0 from 2026-11-03 17:58 UTC). Deploy another commit by connecting the source again with it — not "Redeploy", which rebuilds the current one (before: `f59401b` / `148b5467` 2.6.0 from 2026-11-03 17:33 UTC, `fad9110` / `ef108adc` 2.5.0 from 2026-11-02 22:39 UTC, `0af8435` / `ef207e6e` 2.4.0 with V7 from 2026-11-02 18:42 UTC, `73ff153` / `56524faf` 2.4.0 from 2026-10-28 19:10 UTC, `2817bb6` / `724189ec` 2.3.0 from 2026-10-28 02:08 UTC, `dbdc118` / `7fd7783b` 2.2.0 — the financial calendar and the v4 sign-in page — from 2026-10-24 20:10 UTC, `de96251` / `b4f6d2fd` from 2026-10-23 20:13 UTC — the v3 sign-in page, not approved, and `opentelemetry-api` 1.45.1 —, `1e24bf4` / `dd8b4894` from 2026-10-23 18:02 UTC, `ee388c0` / `33783139` from 2026-10-23 12:12 UTC, `79efb1d` / `87d26668` 2.1.0 from 2026-10-18 — the re-pin of 2026-10-21 waited for Railway's build pause —, `461abcf` / `174528cf` 2.0.0 from 2026-10-13, `fcd7ae3` from 2026-10-11, `842d365` on which the v1 real-ChatGPT acceptance ran). Pushes do not redeploy it | STAGING VERIFIED |
| Database | Railway Postgres 18 template (18.6), private network only, alembic `0044` (2.9.0 added no migration, only 1,838 regional observations on 2026-11-09; since 2026-11-04 23:0x UTC: `mcp_setup_answers`, `regional_observations`, `regional_ingestion_runs`; `0042` since 2026-11-04 07:2x; `0040` since 2026-10-28). The MCP service connects as the least-privilege role `mita_mcp` (`scripts/mcp/mcp_service_role.sql`) on `postgres.railway.internal`; the read-only `mita_analytics_reader` exists (password not kept — reset before use). Both stored passwords were rotated on 2026-10-23 (see "Credential rotation"). Temporary TCP proxies used for migrations and checks (2026-10-03, 2026-10-13, 2026-10-18, three times on 2026-10-23, twice on 2026-10-28, once on 2026-11-02) were removed and verified no longer serving Postgres; none was opened on 2026-10-24 (no migration; see "Left on staging") | STAGING VERIFIED |
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
| `MCP_CLIENT_IP_HEADER` | no (`x-real-ip`) | the header Railway's HTTP edge writes the client's address into, over anything the client sent; per-IP limits count by it (`X-Forwarded-For` never: its last hop is a rotating edge address). Empty = count by TCP connection. The service refuses to start with it while it has a TCP proxy (`RAILWAY_TCP_PROXY_PORT`) | literal | no |
| `MCP_SUPPORT_URL` | no | link on the consent page | literal | no |
| `MCP_WIDGET_DOMAIN` | production: yes (startup refuses without it, since 2026-10-27); staging: set it for the real-ChatGPT acceptance | https origin (no path; a trailing `/` is dropped) for the calendar component's `_meta.ui.domain`; unset = the host's shared sandbox origin | the service's own origin (staging: `https://mita-mcp-staging-staging.up.railway.app`) | no |
| `OPENAI_APPS_CHALLENGE_TOKEN` | for OpenAI domain verification only | body of `/.well-known/openai-apps-challenge` | OpenAI dashboard | no |
| `PORT` | no (8080) | listen port (domain targets 8080) | literal | no |
| `LOG_LEVEL` | no | logging | literal | no |

Set on staging (names only): `DATABASE_URL` (role `mita_mcp`), `ENVIRONMENT, JWT_SECRET, LOG_LEVEL,
MCP_ANALYTICS_SECRET, MCP_AUTH_MODE, MCP_DATA_SECRET, MCP_GRANT_FINGERPRINT_SECRET,
MCP_LOGIN_ATTEMPTS_PER_MINUTE, MCP_LOGIN_CSRF_SECRET, MCP_METRICS_TOKEN,
MCP_OAUTH_PRIVATE_KEY, MCP_OAUTH_REQUESTS_PER_MINUTE, MCP_PUBLIC_URL,
MCP_TOOL_CALLS_PER_MINUTE, MCP_TRUSTED_PROXY_HOPS, MCP_WIDGET_DOMAIN, PORT, SECRET_KEY`
(`MCP_TRUSTED_PROXY_HOPS` is not read since `0af8435`; left in place because
deleting a variable redeploys the service). All
secrets were generated fresh for staging with `generate_keys.py --out` and
pushed with the Railway CLI (`--stdin`; the two v2 secrets on 2026-10-13);
the local copies were deleted. No production value was used. All of them
were rotated on 2026-10-23 after Railway's security incident (below).

## MCP 2.3.0 — deployed 2026-10-28 (`2817bb6`, deployment `724189ec`)

`MCP_WIDGET_DOMAIN=https://mita-mcp-staging-staging.up.railway.app` set with
`--skip-deploys` before the re-pin; no migration (head `0039`).

## MCP 2.4.0 — deployed 2026-10-28 (`73ff153`, deployment `56524faf`)

F-11 (`user-budget-lines.md`). CI run 40743607667 green on `73ff153`. Through
a temporary TCP proxy: `alembic upgrade head` `0039 → 0040` (only
`mcp_budget_lines`, 0 rows), then `GRANT SELECT, INSERT, UPDATE, DELETE ON
mcp_budget_lines TO mita_mcp` (checked with `has_table_privilege`; no
TRUNCATE/REFERENCES); proxies removed and verified. `/health` 2.4.0.
`e2e_http.py` 31 + 24 PASS (restart between), `e2e_v2.py` 85/85 incl. the
F-11 steps, F-11 smoke 19/19, isolation 11/11, logs clean. One check failed:
`staging_failure_modes.py` 23/24 — `/authorize` answered a 40-request burst
with 40 × 400, never 429 (V7, next section). Rollback: re-pin `2817bb6` (it
ignores the table; `0040` can stay).

## V7 per-IP limits — deployed 2026-11-02 (`0af8435`, deployment `ef207e6e`)

Cause (`oauth-security-audit.md`, V7): the per-IP limits counted the last
`X-Forwarded-For` hop, which on Railway is a rotating edge address; they now
count the `X-Real-IP` Railway's edge writes (the TCP peer without it), and
uvicorn no longer takes the client from `X-Forwarded-For`. No migration, no
variable change (`MCP_CLIENT_IP_HEADER` unset = `x-real-ip`). CI run
41499645931 green on `0af8435`. The service has no TCP proxy (it refuses to
start with one).

Verified on staging (status codes and counts only):

| Check | Result |
|---|---|
| `/authorize`, 40 requests in a fresh minute | 30 × 400 (normal OAuth validation, no parameters), then 10 × 429 with `Retry-After: 60` |
| forged `X-Real-IP` / `X-Forwarded-For` / `Forwarded`; a new connection per request | 429 every time (same bucket) |
| 15 HTTP/1.1 + 16 HTTP/2 requests in a fresh minute | 30 × 400, then 429 (one bucket) |
| sign-up limit (5 per hour) | 1 account created, 4 refused as taken, then 429 — also with a forged `X-Real-IP` |
| sign-in limit (10 per minute) | 10 × 400, then 429 — also forged |
| lockout | 5 wrong passwords → the right one refused with the generic message, no code; a forged address does not unlock it; database: 5 failures, locked |
| slash redirect behind Railway's TLS | `/authorize/` → 307 to `https://…/authorize` |
| `e2e_http.py` | 31/31, restart, 24/24 (refresh survives, password change revokes both tokens, logs clean) |
| `staging_failure_modes.py` | 25/25 (incl. the 429 and the forged-header check) |
| `e2e_v2.py` / F-11 smoke | 85/85 / 19/19 — F-11 unchanged |
| logs | 441 application lines: no e-mail, token, code, password, amount, client address or budget-line label (the only address is uvicorn's bind `0.0.0.0`); Railway's HTTP log: no query strings |

Every account the checks created was deleted (5 users, as before); the
temporary proxy was removed and Postgres no longer answers there. Rollback:
re-pin `73ff153` (per-IP limits then break again, nothing else changes).

## MCP 2.10.0 — prepared 2026-11-12 (not deployed yet)

A budget is not a schedule (`flexible-envelopes-calendar.md`): the calendar
no longer draws a flexible budget's stored daily share on dates; component
`ui://mita/financial-calendar-v4.html`, month payload version 2. **No
migration (alembic stays `0044`), no new table, grant or environment
variable, no change to any stored row.** The release is the re-pin alone.

| Step | How | Access it needs |
|---|---|---|
| 1. CI | Backend, MCP (incl. the container end-to-end step) and Mobile green on the commit | none |
| 2. Isolation | Name the project `mita-mcp-staging`, environment `staging`, service `mita-mcp-staging` in every command (the working directory is linked to production); confirm no TCP proxy on either service | Railway API (read) |
| 3. Deploy | `connect-service-source` → the commit; wait for the deployment to succeed; `/health` → `"version":"2.10.0"` | Railway API (write, staging service only) |
| 4. Component | `resources/read ui://mita/financial-calendar-v4.html` sha256 = `app/mcp/ui/financial_calendar.html` of the commit; `show_financial_calendar` points at it (checked by the smoke) | public HTTPS |
| 5. Checks (fictional accounts, ≤ 5 sign-ups an hour per IP) | `smoke_envelopes_2100.py` (49 checks), `smoke_behavioral_270.py` (66; its bill checks need a run on or before the 15th), `e2e_v2.py` (85), `calendar_widget_review.py --axe` (81) | public HTTPS |
| 6. Logs | the deployment's log: no error line; no e-mail, token or amount | Railway API (read) |

**Not part of this release, and not authorised for it:** database access.
The temporary SSH key of 2.9.0 was for that release only. Without it:

* the fictional accounts the checks create stay on staging until database
  access is authorised again (they are listed under "Left on staging" once
  created; delete each with `e2e_v2.cleanup`);
* `staging_account_fingerprint.py` cannot be run, so "the owner's account is
  identical" is argued, not measured: the release has no migration and no
  write path of its own; the calendar tools run inside `SET TRANSACTION READ
  ONLY`; the checks sign up their own accounts and never hold a token of the
  owner's. To measure it, authorise a key for a before / after fingerprint.

Rollback: re-pin `789bfb6` (2.9.0). Nothing else changes: 2.9.0 reads the
same rows. A ChatGPT that cached the v4 component keeps it for the cards it
already drew; new cards get v3 again.

## MCP 2.9.0 — deployed 2026-11-09 18:13 UTC (`789bfb6`, deployment `20c1191f`)

Owner-authorised release (owner brief of 2026-11-09: "a temporary ED25519
SSH key named `mita-staging-290` exclusively for completing the MITA MCP
2.9.0 release"); nothing public was opened. Code:
`789bfb63534acea566ec8e9cebedbf47008ce8f3` (CI run 42613420776 green:
Backend, MCP including the container end-to-end step, Mobile). `212e74f`
above it changes a test and docs only (CI run 42616413261 green). There is
no migration; alembic stays `0044`.

| Step | Result |
|---|---|
| isolation | Project `mita-mcp-staging`, environment `staging`: only the services `mita-mcp-staging` and `Postgres`, no staged change, **no TCP proxy on either**. Every command named the project, environment and service, because the working directory is linked to production |
| access | Temporary ED25519 key `mita-staging-290` (`SHA256:uLKiWDa68MfXZtAynGr/1qRnwvs1vL5zFFQvyYiM+qI`) in a dedicated agent in a scratch directory (`~/.ssh` untouched), registered from that agent 18:0x UTC. The agent socket path must stay under macOS's 104-character limit. `railway ssh` and an `ssh -L` tunnel through the Postgres container, bound to 127.0.0.1 |
| target | Database `railway`, PostgreSQL 18.6, system identifier `7692536193956495422`, alembic `0044`, 23 MB, 47 tables. 5 accounts (4 after 2.8.0; one created since then, left alone), 51 expenses, 612 plan rows, 12 saved payments, 11 OAuth clients, 5,209 observations (Eurostat and World Bank), `mita_regional_ingest` NOLOGIN |
| owner's account | Identified read-only by the stated facts (income 2,000; saved payments 30/70/270; a real address): exactly one. The e-mail was kept in a 0600 file and never printed. Fingerprint before: November 180 plan rows, 19 live expenses, 3 saved payments, 5 own lines, 0 links, 0 patterns, 0 setup answers, 2.8 profile fields at their defaults |
| backup | `pg_dump -Fc` onto the volume: `/var/lib/postgresql/data/mita-backups/pre-290-20261109.dump` (299,659 bytes, sha256 `e897fd89d37b82b9…`, 392 entries, 0600). Restore-tested into a temporary database: no errors, identical row counts in all 47 tables; the temporary database dropped |
| deploy | `connect-service-source` → `789bfb6…`; deployment `20c1191f-1a0d-45e7-a4a1-90e2289a09be` SUCCESS 18:13:14 UTC; `/health` 200 `"version":"2.9.0"` at 18:13:20. `618cd6d9` (2.8.0) kept for rollback |
| ingestion | In-region, in the MCP container, as `mita_regional_ingest`: `LOGIN PASSWORD` with a SCRAM verifier computed locally, and the job's `DATABASE_URL` sent on stdin. `--provider eurostat` only (no OECD). Run 1: **1,838 new** (`hbs_str_t211` +119, `hbs_exp_t111` 124, `prc_hicp_aind` 1,536, `hbs_exp_t123b` 59), 0 updated, 0 rejected, 23 s. Run 2: everything unchanged (idempotent). Then `NOLOGIN PASSWORD NULL`; the local secret files deleted |
| data | 7,047 observations; 0 OECD rows, 0 rows without an https source, 0 amounts without a currency, 0 Eurostat rows outside its licence. `hbs_exp_t111` currencies are per country and year (EUR 102; BGN, HRK, RON, PLN, CZK, HUF, DKK, NOK, RSD, TRY 2 each; SEK, MKD 1). Bulgaria's inputs are 4,775 / 246‰ / 116.26 → 180.75 |
| checks (fictional accounts, public HTTPS, paced at ≤ 5 sign-ups an hour per IP) | `smoke_regional_290.py` **56/56** (every domain check, including: groceries 78.00 planned, 152.00 referenced; fuel for buyers; no figure for dining out, with the reason; Varna = Sofia; Fuel 200 kept; statistics off gives the same plan; household of 4 = 289–380; USD in Bulgaria and the US get none; no verified local price) · `smoke_onboarding_280.py --expect-statistics` **77/77** · `e2e_http.py` **32 + 22** across a service restart · `smoke_behavioral_270.py` **66/66** · `e2e_v2.py` **85/85** · `staging_failure_modes.py` **25/25** (the `/authorize` 429 and forged headers staying in one bucket) |
| incidents | (1) The first `e2e_http` phase 2 met a transient connection error at its first request right after the restart. Its clean-up removed that test user, and the whole run was repeated after `/health` was steady for 40 s. (2) The behavioural smoke's checks all passed, but its clean-up failed when the tunnel could not open a new forwarding channel. The tunnel was reopened and both accounts were deleted with `e2e_v2.cleanup` |
| known behaviour, preserved, not fixed | Flexible monthly envelopes still appear as daily amounts in the calendar (the next development task). Fictional account with own lines €320 / €200 / €100, November 2026 (30 days): `planned_per_day` **10.67 / 6.67 / 3.33**; every date's `planned_flexible` is 20.65–20.68 with nothing scheduled; `summary.flexible_per_day` 28.19 from the 9th. 2.9.0 does not change it |
| logs | Deployment `20c1191f`, 18:16–19:22: 501 lines, 494 info, 7 warnings (5 "oauth register rejected redirect", 2 "refresh token reuse": the fail-closed tests). No error line. No e-mail, token, location or amount; the one "password" match is the reason code `invalid_password` of the deliberate wrong-password test |
| clean-up | Every account the checks created was deleted: 5 accounts and 11 OAuth clients, as before the release; 0 orphan expenses |
| owner's account after | **Identical** in every table to the fingerprint before the release |
| revocation | Tunnel closed; key removed (`railway ssh keys list` → "No SSH keys registered with Railway."); agent stopped; the private and public key, SSH config, known_hosts, the e-mail file, state files and helpers deleted. Production (`d4c2547c`, 2026-09-29), `main`, PR #287 and Flutter untouched |

Left on staging: 5 accounts, 11 OAuth clients, the three dumps (delete each
once its release is accepted), the regional data (7,047 observations, still
refreshed by hand until a weekly job is approved), `mita_regional_ingest`
with no login and no password.

Rollback: re-pin `601a3d7`. 2.8.0 ignores the new rows; nothing else
changes.

## MCP 2.8.0 — deployed 2026-11-04 23:19 UTC (`601a3d7`, deployment `618cd6d9`)

Owner-authorised release (decision of 2026-11-04/05: "a new temporary Railway
SSH key exclusively for MITA staging"); nothing public was opened. Code:
`601a3d7d96a86eceb88600cea33f16243d74582b` (CI run 41899516821 green: Backend,
MCP incl. the container end-to-end step, Mobile).

| Step | Result |
|---|---|
| isolation | project `mita-mcp-staging` / environment `staging`: services `Postgres` and `mita-mcp-staging` only, no staged changes, **no TCP proxy on either**; production is the separate project `Mita Finance` (`d44d0580`), never addressed |
| access | temporary ED25519 key `mita-staging-280` (`SHA256:6i1rfRz3ncfO75C7xHVMezYc6w+DV1NneDrHSCCcZOg`) in a dedicated agent on a 0700 scratch socket (`~/.ssh` untouched), registered on the owner's account; `railway ssh` with explicit project/environment/service; `ssh -L` bound to 127.0.0.1. Account keys reach every service, so every command named staging explicitly |
| target | database `railway`, system identifier `7692536193956495422`, alembic `0042`, 4 accounts, 13 MB |
| owner's account | identified read-only by the stated facts (income 2,000, savings 500, saved payments 30/70/270, a real address) — exactly one; e-mail kept in a 0600 file, never printed. Fingerprint (`staging_account_fingerprint.py`, now digesting `mcp_user_profiles` by its pre-0043 columns so a migration's added columns cannot look like a change): November 175 plan rows, 7 live expenses, 3 saved payments, 5 own lines, 0 links, 0 patterns |
| backup | `pg_dump -Fc` onto the volume: `/var/lib/postgresql/data/mita-backups/pre-0043-0044-20261105.dump` (186,415 bytes, sha256 `f0511f8126552c54…`, root-only 0600). Restore-tested into a temporary database: no errors, row counts identical across all 43 tables (4 users, 34 expenses, 369 plan rows, 6 saved payments); temporary database dropped. The 2.7.0 dump is still there |
| migrations | `alembic upgrade 0044` through the tunnel as the owner role: 0042 → 0043 → 0044; 3 new tables, 7 new `mcp_user_profiles` columns; row counts unchanged |
| grants | `mcp_service_role.sql`: `mita_mcp` + DML on `mcp_setup_answers`, `SELECT` (only) on `regional_observations`, `UPDATE (country, region)` added to its `users` columns. `regional_ingest_role.sql`: `mita_regional_ingest` with SELECT/INSERT/UPDATE on the two regional tables and the identity sequence, nothing else (cannot read `users`; not superuser); its password was generated into a 0600 file, never printed, deleted after use, and the role set **NOLOGIN** afterwards |
| OECD | **excluded** from this release (owner rule): its terms page refuses automated reads, the API's dataflow metadata carries no licence and is annotated `NonProductionDataflow: true`. Code unchanged; the job simply ran `--provider eurostat` and `--provider worldbank`. A user in the US gets World Bank yearly inflation only |
| ingestion | run 1 (operator machine, through the tunnel): 6 requests, **5,209 observations** inserted (HICP 3,276, PLI 648, HBS 372, electricity 190, gas 150, World Bank 573), 0 rejected. Idempotency: HICP and PLI confirmed unchanged through the tunnel (slow: one round trip per unchanged row from Bulgaria to Singapore), the rest interrupted twice by tunnel drops (the run records were closed as `failed`, nothing partial stored); then the deployed code inside the MCP container (in-region): all 6 datasets, 5,209 unchanged, 0 new, 0 updated, 0 rejected, 28 s |
| provenance | every row has provider, dataset, series key, period, unit kind, classification, licence, provider update time, retrieval time and its HTTPS request; 0 missing sources, 0 amounts without a currency, 0 OECD rows, 0 Eurostat rows for the US; 193 countries |
| deploy | `connect-service-source` → `601a3d7…`; deployment `618cd6d9-681a-4194-9abe-68487713f512` SUCCESS 23:19 UTC; `/health` 200 `"version":"2.8.0"` (readiness needs `mcp_setup_answers` and `regional_observations` visible to `mita_mcp`) |
| checks (fictional accounts, public HTTPS) | `smoke_onboarding_280.py --expect-statistics` **77/77** (26 tools; onboarding stages, setup answers, country from ChatGPT's hint only as a question, personalized vs preliminary previews, no fuel without a car, no rent with a mortgage, variable income, a preview saves nothing, a returning user never re-asked, another account sees nothing; Bulgaria's statistics from Eurostat incl. the electricity price, the US from the World Bank, never Eurostat) · `smoke_behavioral_270.py` **66/66** · `e2e_v2.py` **85/85** (OAuth sign-up, profile, budgets, F-11 lines, expenses, retries, a new connection, history, goal, feedback, negatives, analytics audit) · `e2e_http.py` phase 1 passed (tools/list exactly the 26 published tools, every read tool) + **22/22** after a service restart · `staging_failure_modes.py` **25/25** (incl. the `/authorize` 429 and V7 per-IP buckets) |
| logs | deployment `618cd6d9`: no error line; 6 warnings — 4 "oauth register rejected redirect", 2 "refresh token reuse": the fail-closed tests; no e-mail, location, token, password or name (filter searches, the filter checked against a known term) |
| clean-up | every account the checks created deleted: 4 accounts and 10 OAuth clients (6 with tokens) as after 2.7.0; no orphan rows |
| owner's account after | after the migration, deploy and every check (2026-11-04 ~23:30): **identical** in every data table. By 2026-11-05 16:45 it held 6 more expenses and 2 more November plan rows, all created at 08:11 UTC in one batch — the owner's own use of 2.8.0 in ChatGPT (7 token refreshes of their connection since); 0 rows created during any release window, none of the 175 earlier plan rows replaced |
| revocation | tunnel closed; key removed (`railway ssh keys list` → "No SSH keys registered with Railway."); agent stopped; key files, private SSH config, known_hosts, the e-mail and password files deleted; production (`d4c2547c`, 2026-09-29), `main`, PR #287 and Flutter untouched |

Left on staging: 4 accounts, 10 OAuth clients, both dumps (delete each once
its release is accepted), the regional data (5,209 observations, refreshed
manually until a weekly job is approved), `mita_regional_ingest` NOLOGIN.

Rollback: re-pin `2ab2e0f` (2.7.0 ignores the new columns and tables), or
restore the dump.

**Weekly refresh — prepared, not created (owner approval needed).** A cron
service in `mita-mcp-staging`, same image and pinned commit, start command
`sh -c "python -m app.regional.ingest --provider eurostat && python -m app.regional.ingest --provider worldbank"`,
cron `0 6 * * 1` (UTC), restart policy never, no domain, no volume, no TCP
proxy; one variable `DATABASE_URL` for `mita_regional_ingest` on
`postgres.railway.internal` (after `ALTER ROLE … LOGIN PASSWORD` with a new
generated password) and `ENVIRONMENT=staging`; no MCP secret. Cost (Railway
pricing page, read 2026-11-05: RAM $0.000231 / GB-minute, CPU $0.000463 /
vCPU-minute, egress $0.05 / GB): measured 28 s in-region per run; assuming 1
minute, 0.25 GB and 0.5 vCPU ≈ $0.0003 a run, **≈ $0.001 a month** at 4.35
runs (pessimistic 3 min × 1 GB × 1 vCPU: ≈ $0.009 a month); requests and
database traffic stay on the private network or are inbound. The workspace's
Hobby plan includes $5 of usage a month.

## MCP 2.7.0 — deployed 2026-11-04 07:27 UTC (`2ab2e0f`, deployment `390805cb`)

Owner-authorised release (brief of 2026-11-04): a temporary Railway SSH key,
the staging migrations, the deploy and the checks; nothing public was opened.
`2ab2e0f4f62348d537bc38ee716fcdc5fe9e301c` is the last code commit (CI run
41767979897 green: Backend, MCP incl. the container end-to-end step, Mobile);
`6ab3fb0` above it changes docs only.

| Step | Result |
|---|---|
| access | temporary ED25519 key `mita-staging-270` (`SHA256:r/CjjCaSQAvEOsh5HqXV460vTQhIGiZzfMhTxZrTiCM`), public half registered on the owner's Railway account; `railway ssh` into the Postgres container and an `ssh -L` tunnel bound to 127.0.0.1 only (private network, no TCP proxy) |
| target | database `railway`, PostgreSQL 18.6, system identifier `7692536193956495422`, project `mita-mcp-staging`; alembic `0040`; the two new tables absent; roles `mita_mcp`, `mita_analytics_reader`, `postgres`; 42 public tables, 14 MB (production is PostgreSQL 17 in another project) |
| backup | Railway volume backups need a Pro workspace (refused), so a full logical dump on the Postgres volume: `/var/lib/postgresql/data/mita-backups/pre-0041-0042-20261104.dump` (275,417 bytes, sha256 `86b49c349fab0249…`, 356 entries, data of all 42 tables). Restore-tested into a temporary database on the same server: 0 errors, identical row counts (18 users, 100 transactions, 2,362 plan rows, 42 saved payments); the temporary database dropped. Restore: `pg_restore -U postgres -d railway --clean --if-exists <file>` from `railway ssh` into Postgres. Delete the file once 2.7.0 is accepted |
| migrations | `alembic upgrade 0042` through the tunnel as the owner role (credentials from the Postgres service's own variables via `railway run`, never printed): `0040 → 0042 (head)` |
| grants | `obligation_payments`: SELECT, INSERT, DELETE (UPDATE, TRUNCATE, REFERENCES, TRIGGER: no); `spending_patterns`: SELECT, INSERT, UPDATE, DELETE; indexes `uq_obligation_payments_transaction`, `ix_obligation_payments_user_due`, `ix_obligation_payments_obligation_due`, both primary keys; foreign keys and checks as in the migrations; both tables owned by `postgres` |
| owner's account | identified read-only by the stated facts (income 2,000, savings 500, saved payments 30/270/70) and a real address — exactly one; the €60 transportation expense present. Per-table digests (users, transactions 7/7 live, November plan 175 rows, 3 saved payments, profile, 5 own lines) **identical** before the migration, after it, after the deploy, after every check and after the clean-up; 0 linked payments and 0 stated patterns (nothing linked or inferred) |
| deploy | `connect-service-source` → `2ab2e0f…`; deployment `390805cb-8188-45ba-9cf6-3d1e4fa3a2e8` SUCCESS 07:27 UTC; `/health` 200 `"version":"2.7.0"` (the readiness check needs both new tables visible to `mita_mcp`) |
| component | `resources/read ui://mita/financial-calendar-v3.html` sha256 `175b2aae26ca8dd3…` = `app/mcp/ui/financial_calendar.html` at `2ab2e0f`; `show_financial_calendar` points at it |
| checks (fictional accounts, public HTTPS) | `smoke_behavioral_270.py` 66/66 (25 tools incl. `save_spending_patterns`; patterns inserted/unchanged/updated; planned Wednesdays; proposed fuel dates; medical insurance left out with the freed money; preview = save; the €60 car part leaves the car loan unpaid; linked, relinked, capped, unlinked; pace flags; calendar = forecast; another account refused the reference) · `e2e_v2.py` 85/85 (OAuth sign-up, profile, rent, preview/save, F-11 own line, expenses, retry, past months, new connection, history, goal, feedback, negatives, analytics audit) · `calendar_widget_review.py --axe` 82/82 (320/360/390/430 px and desktop, light/dark, axe clean ×4, PNG through the host and the fallback, read tools only) · `e2e_http.py` 31 + 21 across a service restart · `staging_failure_modes.py` 25/25 (incl. V7 per-IP limits) |
| logs | 415 lines of `390805cb`: 409 info, 6 warnings (4 "oauth register rejected redirect", 2 "refresh token reuse": the fail-closed tests); no error-level line, no permission error, no e-mail, token, amount or line name |
| clean-up | every account the checks created deleted; the 14 earlier fictional accounts (bills-smoke ×2, calendar-review ×4, personal ×6, v2e2e ×2) deleted in one transaction with the 18 OAuth clients only they used (none shared with a kept account); no orphan rows. Tunnel closed; key revoked (`railway ssh keys` → none registered) and both local key files deleted; no TCP proxy on either service; production (`d4c2547c`, 2026-09-29) and `main` (`27ed25d`) untouched |

Left on staging: 4 accounts (the owner's, one other real address, the seeded
`staging-review@example.test`, one unrecognised `example.*` address — kept),
10 OAuth clients (6 holding tokens, 4 token-less — kept: a client used by a
live ChatGPT connection must never be deleted by guess), the backup file
above.

Rollback: re-pin `c5a317c` (2.6.0 ignores the new tables; any month saved
under 2.7.0 must be saved again under 2.6.0 first), or restore the dump.

## MCP 2.6.0 — deployed 2026-11-03 (`f59401b` 17:33 UTC, then `c5a317c` 17:58 UTC, deployment `62d3a0d1`)

The redesigned calendar on a new component URI, `ui://mita/financial-calendar-v2.html`
(ChatGPT's cache key, so ChatGPT fetches it instead of a cached v1); calendar
lines carry `replaces`. CI green: run 41682268134 (`f59401b`) and 41686073137
(`c5a317c`). No migration, variable or grant change. Verified over public HTTPS
with new fictional accounts:

| Check | Result |
|---|---|
| `/health` | `"version":"2.6.0"`; deployment `62d3a0d1` = `c5a317c2401e74194ebb26e58f42064d5c09099a` |
| the served component | `resources/read ui://mita/financial-calendar-v2.html` sha256 `4cb69f291cad9701…` = the commit's `app/mcp/ui/financial_calendar.html`; `show_financial_calendar` points at it (`_meta.ui.resourceUri` and `openai/outputTemplate`) |
| live, per user | two new accounts with different facts get different calendars (A: plan 1,854.00, held 370.00, 36.44 a day, its three bills and lines; B: plan 2,719.00, held 900.00, 56.26 a day, its rent only); an account without a budget gets "not generated" and no one's data; a Fuel change 200 → 250 shown in the preview, saved, and read back over a new connection |
| calendar harness with axe | 77/77 on `c5a317c` (75/75 and 77/77 on the earlier deployments) |
| bills smoke | all checks pass, the same figures as on 2.5.0 |
| `e2e_v2.py` | 78/78 on `f59401b` (server code identical in `c5a317c`) |
| logs | `148b5467`: 240 + 139 lines, `62d3a0d1`: 195 + 108 lines — no e-mail, token, bill or line name, amount, password, database URL; no error-level line; one 429 (the sign-up limit refusing a 6th new account within the hour, as designed) |

Screens rendered from staging: `review/calendar-v2/` (local MCP Apps host,
not ChatGPT).

## MCP 2.5.0 — deployed 2026-11-02 22:39 UTC (`fad9110`, deployment `ef108adc`)

Bills planned in full on their due dates, a bill's money following its
payment, bill lines never donors, bill states and five-day reminders in the
calendar (`bill-due-dates.md`). CI run 41536239112 green on `fad9110`
(Backend, MCP incl. the container end-to-end step, Mobile). No migration, no
variable change, no new grant (the ledger rebuild reads `scheduled_expenses`,
already granted to `mita_mcp`). Rollback: re-pin `0af8435` (see
`bill-due-dates.md` §10).

Verified over public HTTPS only (the temporary database proxy was not opened
this time — an automated permission check refused it), with new fictional
accounts:

| Check | Result |
|---|---|
| `/health` | `"version":"2.5.0"` |
| bills smoke (scratch script, a fictional copy of the owner's month plus a bill due today and one in two days) | all checks pass: due dates 10/15/25 Nov and today; 15 Nov = everyday + 270.00; 20–24 Nov carry no bill money; states due_today / upcoming (2 days); reminders = those two; before payments plan 2,000.00, held 404.99, left 1,095.01, 40.56 a day; after recording 9.99 on time, 25.00 two days early and 100.00 of the car loan early: held −134.99, left and the daily figure unchanged, no redistribution note; status = forecast = calendar; an everyday overspend still rebalances, bills and the user's lines keep their money — identical figures to the local run |
| `e2e_v2.py` | 78/78 (its analytics audit and clean-up need the database: skipped) |
| `calendar_widget_review.py` with axe | 75/75 (axe 0 violations ×4; 320/360/390 px nothing cut off; reminders, bill marks, the bill date, the bills card; PNG through `ui/download-file` and the fallback; read tools only) |
| logs of `ef108adc` | 212 deploy + 117 HTTP lines: no e-mail, bearer token, JWT, bill name, amount, password, database URL or code/token query string; no error-level line |

**Not run (need database access, owner decision):** the read-only snapshot of
the owner's account before/after, `e2e_http.py` (it creates its user directly
in the database; MCP CI ran it on the built image), `staging_failure_modes.py`,
and deleting the fictional accounts below. No migration or script touched
the owner's rows: their saved November plan changes only through their own
writes (an expense recorded or a budget saved), as `bill-due-dates.md` §8
describes.

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

## Left on staging (2026-11-02/03, MCP 2.5.0 and 2.6.0 checks) — DELETED 2026-11-04

All of the accounts below (and those of 2026-10-24) were deleted on
2026-11-04 over Railway SSH (`MCP 2.7.0` above); kept for the record.

Fictional accounts created over HTTPS, not deleted (no database access):
`bills-smoke-<8 hex>@example.com` (×2), `v2e2e_<10 hex>@example.test` (×2),
`calendar-review-<8 hex>@example.com` (×4) and `personal-<8 hex>@example.com`
(×6), with their DCR clients. Delete them
with `e2e_v2.cleanup` per account the next time a proxy is open, then the
token-less OAuth clients registered on 2026-11-02 after 22:39 UTC.

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
  empty → `0037` on 2026-10-03, `0037 → 0039` on 2026-10-13,
  `0039 → 0040` on 2026-10-28, `0040 → 0042` on 2026-11-04 over Railway
  SSH with a temporary key, no TCP proxy (`alembic current` = `0042 (head)`).
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
# database access only through Railway SSH (no TCP proxy, owner brief
# 2026-11-04): ssh -N -L 15432:postgres.railway.internal:5432 \
#   mita-mcp-staging-staging.up.railway.app@ssh.railway.com   (needs a key)
railway run --service Postgres -- sh -c '…'   # build STAGING_DB_URL on 127.0.0.1:15432
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

Removing a proxy (the pre-2026-11-04 practice, now ruled out): Railway's
`delete-tcp-proxy` can lose its response and still apply a little later.
Confirm with `list-tcp-proxies` (empty) and a connection attempt through the
old endpoint (no Postgres answer) — the proxy host may still accept a bare
TCP handshake on the port.

## Tearing staging down

Railway → project `mita-mcp-staging` → Settings → Danger → Delete project.
Nothing in production depends on it.
