# MITA MCP — staging (observed 2026-10-03, v2 update 2026-10-13, credentials rotated 2026-10-23, MCP 2.4.0 since 2026-10-28, `0af8435` deployed 2026-11-02, MCP 2.5.0 `fad9110` since 2026-11-02 22:39 UTC, MCP 2.6.0 `c5a317c` since 2026-11-03 17:58 UTC; MCP 2.7.0 prepared 2026-11-04, not deployed: needs a secure database path for 0041/0042)

## What exists

| Item | Value | Status |
|---|---|---|
| Railway project | `mita-mcp-staging` (`497476f2-de93-44b7-b170-2b175c8d5621`) — **separate project**, no access to the production project's variables, services or database | STAGING VERIFIED |
| Environment | `staging` (`0f67cf7a-5ce4-472e-a842-2e5448d64c08`) | STAGING VERIFIED |
| MCP service | `mita-mcp-staging` (`833466fc-f7f2-4d51-8db1-48edfbb46057`), Dockerfile `deploy/mcp/Dockerfile`, healthcheck `/health`, restart ON_FAILURE ×5, **1 replica** (region `asia-southeast1-eqsg3a`), source `teniee/mita_project` @ `feat/chatgpt-auth-ui` **pinned to commit `c5a317c`** (MCP 2.6.0: the redesigned calendar on `ui://mita/financial-calendar-v2.html`; bills on their due dates since 2.5.0) since 2026-11-03 17:58 UTC, deployment `62d3a0d1-7377-4a30-95ad-fa65183a9267`. Deploy another commit by connecting the source again with it — not "Redeploy", which rebuilds the current one (before: `f59401b` / `148b5467` 2.6.0 from 2026-11-03 17:33 UTC, `fad9110` / `ef108adc` 2.5.0 from 2026-11-02 22:39 UTC, `0af8435` / `ef207e6e` 2.4.0 with V7 from 2026-11-02 18:42 UTC, `73ff153` / `56524faf` 2.4.0 from 2026-10-28 19:10 UTC, `2817bb6` / `724189ec` 2.3.0 from 2026-10-28 02:08 UTC, `dbdc118` / `7fd7783b` 2.2.0 — the financial calendar and the v4 sign-in page — from 2026-10-24 20:10 UTC, `de96251` / `b4f6d2fd` from 2026-10-23 20:13 UTC — the v3 sign-in page, not approved, and `opentelemetry-api` 1.45.1 —, `1e24bf4` / `dd8b4894` from 2026-10-23 18:02 UTC, `ee388c0` / `33783139` from 2026-10-23 12:12 UTC, `79efb1d` / `87d26668` 2.1.0 from 2026-10-18 — the re-pin of 2026-10-21 waited for Railway's build pause —, `461abcf` / `174528cf` 2.0.0 from 2026-10-13, `fcd7ae3` from 2026-10-11, `842d365` on which the v1 real-ChatGPT acceptance ran). Pushes do not redeploy it | STAGING VERIFIED |
| Database | Railway Postgres 18 template (18.6), private network only, alembic `0040` (since 2026-10-28: `mcp_budget_lines`, granted to `mita_mcp`). The MCP service connects as the least-privilege role `mita_mcp` (`scripts/mcp/mcp_service_role.sql`) on `postgres.railway.internal`; the read-only `mita_analytics_reader` exists (password not kept — reset before use). Both stored passwords were rotated on 2026-10-23 (see "Credential rotation"). Temporary TCP proxies used for migrations and checks (2026-10-03, 2026-10-13, 2026-10-18, three times on 2026-10-23, twice on 2026-10-28, once on 2026-11-02) were removed and verified no longer serving Postgres; none was opened on 2026-10-24 (no migration; see "Left on staging") | STAGING VERIFIED |
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

## MCP 2.7.0 — release prepared 2026-11-04, stopped before the migration (database access)

2.7.0 needs migrations 0041 (`obligation_payments`) and 0042
(`spending_patterns`) and their `mita_mcp` grants **before** the service runs
it: every bill, calendar and budget read touches those tables. So the order
is backup → migrate → grant → verify → pin → public checks, and nothing after
the backup has been done. Staging still runs 2.6.0 (`c5a317c`).

Verified without database access (2026-11-04):

| Check | Result |
|---|---|
| target | project `mita-mcp-staging` (`497476f2…`), environment `staging` (`0f67cf7a…`): exactly two services — `mita-mcp-staging` (`833466fc…`, pinned `c5a317c`, deployment `62d3a0d1` SUCCESS) and `Postgres` (`0d97d1f6…`, `ghcr.io/railwayapp-templates/postgres-ssl:18`, volume `postgres-volume` 5,000 MB at `/var/lib/postgresql/data`); nothing of the production project |
| public exposure | `Postgres` has no TCP proxy (`list-tcp-proxies` empty) |
| ordering | `0039 → 0040 → 0041 → 0042`, one head; staging recorded at `0040` since 2026-10-28; env.py runs the whole upgrade in ONE transaction (both tables or neither) |
| DDL | rendered offline from the two migrations' own operations: two `CREATE TABLE`, two `CREATE INDEX` on the new table, foreign keys to `users`, `scheduled_expenses`, `transactions` (a brief SHARE ROW EXCLUSIVE lock on those three while the keys are created); no existing table, column or row changes |
| grants | `scripts/mcp/mcp_service_role.sql`: `SELECT, INSERT, DELETE ON obligation_payments`, `SELECT, INSERT, UPDATE, DELETE ON spending_patterns` (the file is idempotent; only those two lines are new) |
| rollback, code | re-pin `c5a317c`: 2.6.0 never reads the new tables. Safe until someone saves a month under 2.7.0; after that 2.6.0 would show its `bill:<digest>` lines as unknown categories, so that month is saved again under 2.6.0 first |
| rollback, schema | `alembic downgrade 0040` drops only the two new tables (links and stated patterns are lost; expenses and plans are untouched); then the code must be 2.6.0 |
| least privilege, locally | a fresh local database at `0042`, `mcp_service_role.sql` applied as written, the 2.7.0 server connected as `mita_mcp`: `e2e_v2.py` 85/85 and `smoke_behavioral_270.py` 66/66 (patterns inserted / unchanged / updated; an expense linked, relinked, capped at a paid due date and unlinked; another account refused the payment reference); no privilege error or warning in the server log, no e-mail, token, amount or line name in it; clean-up left no row. `/health` is 503 while a required table is missing or not granted (revoking the `spending_patterns` grant: 200 → 503 → 200), so a 2.7.0 deployment without its migrations or grants never becomes healthy and Railway keeps 2.6.0 serving (`tests_mcp/test_readiness.py`) |
| the owner's account | nothing in the release writes to it: 2.7.0 changes no stored row on deploy; the payment rule (only a linked expense pays a bill) applies to every figure from then on, and the owner's next recorded expense re-derives November's in-month adjustments under it (`acceptance-2.7.0-chatgpt.md` → E). The saved November is replaced only if the owner says "save" after a preview |

**Blocker — no secure database path from the operator machine.** The
migration runs online (env.py refuses offline SQL for the chain) as the
table owner. A TCP proxy is ruled out (owner brief 2026-11-04: never expose
PostgreSQL publicly to work around tooling). Railway's private path is SSH
through `ssh.railway.com` (`railway ssh`, `ssh -L` into the project's private
network), and it needs an SSH key registered on the Railway account: none is
(`railway ssh keys` → "No SSH keys registered with Railway"), and this
machine has none. Registering one adds a credential to the owner's account
(account keys reach every service the account can, production included;
removing one asks for the owner's 2FA) — the owner's decision, not taken.
2.7.0 is therefore not deployed: it would fail without the tables.

Once a key exists (owner registers one, or authorizes a dedicated
`mita-staging-2.7.0` key and removes it afterwards):

```bash
P=497476f2-de93-44b7-b170-2b175c8d5621; E=staging
# 0. tunnel into the private network through the MCP service (no public port)
ssh -N -L 15432:postgres.railway.internal:5432 \
  mita-mcp-staging-staging.up.railway.app@ssh.railway.com &
# 1. the owner's account before (counts and digests only; e-mail in a 0600 file)
railway run -p $P -e $E -s Postgres -- .venv-api/bin/python \
  scripts/mcp/staging_account_fingerprint.py --email-file ~/.mita/owner-email \
  --host-port 127.0.0.1:15432
# 2. backup (Railway volume backup; needs CLI >= 5.33 — `brew upgrade railway`)
railway postgres pitr backup create -p $P -e $E -s Postgres --name pre-0041-0042
railway postgres pitr backup list -p $P -e $E -s Postgres --json
# 3. migrate, as the owner role from the Postgres service's own variables
railway run -p $P -e $E -s Postgres -- sh -c \
  'DATABASE_URL="postgresql://$PGUSER:$PGPASSWORD@127.0.0.1:15432/$PGDATABASE" \
   .venv-api/bin/alembic upgrade 0042'
# 4. grants (psql is in the database container; local socket, no password)
railway ssh -p $P -e $E -s Postgres -- sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "GRANT SELECT, INSERT, DELETE ON obligation_payments TO mita_mcp; GRANT SELECT, INSERT, UPDATE, DELETE ON spending_patterns TO mita_mcp;"'
# 5. verify: alembic 0042; has_table_privilege('mita_mcp', …) for each grant
#    and nothing more; step 1 again → identical digests
# 6. pin: connect-service-source commitSha=<2.7.0 commit>; wait for SUCCESS;
#    /health "2.7.0"; tools/list 25 incl. save_spending_patterns;
#    resources/read ui://mita/financial-calendar-v3.html sha256 = the commit's file
# 7. public checks with fictional accounts: e2e_http.py and
#    staging_failure_modes.py (through the tunnel), e2e_v2.py,
#    smoke_behavioral_270.py, calendar_widget_review.py --axe; clean up with
#    --database-url / e2e_v2.cleanup (and the accounts listed under "Left on
#    staging"); step 1 again → identical
# 8. log scan; close the tunnel; remove the key (railway.com/account/ssh-keys)
```

Then the owner's run in real ChatGPT: `acceptance-2.7.0-chatgpt.md`.

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

## Left on staging (2026-11-02/03, MCP 2.5.0 and 2.6.0 checks)

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
  `0039 → 0040` on 2026-10-28 (`alembic current` = `0040 (head)`).
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
