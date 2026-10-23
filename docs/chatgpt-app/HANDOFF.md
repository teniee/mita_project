# Handoff — MITA in ChatGPT (MCP), 2026-10-23

## Current phase: sign-in / first-impression UI — waiting for owner design approval

| Item | State |
|---|---|
| Branch | `feat/chatgpt-auth-ui`, a child of `feat/chatgpt-plugin` @ `200c34d`: `fc9aeeb` the UI, `8c5116b` import order, `ee388c0` tablet header + owner test, then documentation |
| What changed | the `/oauth/login` sign-in / sign-up / consent page and its error pages (`app/mcp/auth/pages.py`, `browser_errors.py`, self-hosted fonts); `login.py` keeps the verified flow; scopes unchanged |
| Design source | Figma Brand Guidelines `512WdjnhPJXM8jeHKcg4g8` → `docs/brand/AUTH-UI-DESIGN.md` |
| Tests | MCP suite 513 passed (baseline 487 + 26 in `test_auth_ui.py`, now in the CI security gate); CI run `39644016485` green on `ee388c0`; `e2e_v2.py` 77 checks and `e2e_http.py` both phases against a local server; axe-core 0 violations; text contrast ≥ 4.85:1 |
| Screenshots | `docs/chatgpt-app/review/auth-ui/` (12, fictional data) |
| Staging | `ee388c0` live since 2026-10-23 (deployment `33783139`), after the Railway-incident rotation — see below |
| Owner test | `auth-ui-owner-test.md` (≈ 5 minutes) |
| PR #287, `main`, production | untouched: PR head still `200c34d`, `main` `27ed25d`, no production deploy, migration, variable or secret change |

Next: the owner reviews the page on staging. After approval, decide how the
branch joins `feat/chatgpt-plugin` (PR #287); launch preparation follows
`production-readiness.md`. Not started and not to start without the owner:
Plugin Directory submission, production MCP, production migrations, the
analytics dashboard.

### Staging deployment — live since 2026-10-23

Railway paused all builds from 2026-10-21 (~17:00 UTC) until 2026-10-23 and
disclosed a security incident (below); the build ran once Hobby builds were
back, after the staging credentials were rotated.

| Item | Result (2026-10-23) |
|---|---|
| Deployment | `33783139-2cd3-49a8-9ec4-d166c7435404`, SUCCESS at 12:12 UTC (restarted in place 12:16 for the persistence check) |
| Source | `teniee/mita_project` @ `feat/chatgpt-auth-ui`, pinned to `ee388c02cc51883f2cf56bd68ec35571a7cef8df` (later commits are documentation only) |
| Health | `/health` ok, MCP 2.1.0; `/oauth/assets/mita-mark.svg` 200 (404 on the old build) |
| Runtime | 1 replica; connected as `mita_mcp` over the private network; alembic `0039`, no migration ran |
| OAuth metadata | exactly `profile:read finance:read finance:write feedback:write profile:write`; PKCE `S256` only; DCR; exact issuer |
| `e2e_v2.py` | 77/77 through the new sign-up page; account deleted |
| `e2e_http.py` | phase 1 27/27; service restart; phase 2 22/22 (refresh token survives the restart, rotation and reuse, password change revokes access and refresh token, log checks) |
| `staging_failure_modes.py` | 24/24 |
| Auth write smoke | 26/26: two new accounts through DCR, PKCE and the sign-up page; one expense written and read back; the other account cannot see or change it; both deleted |
| Page | 12 states rendered from staging, identical to `review/auth-ui/` except the optional "Need help?" / "Help" link — `MCP_SUPPORT_URL` is not set on staging |
| Logs | 915 lines (app, HTTP, build, Postgres): no secret, token, code, password, e-mail, amount or merchant; none of the rotated values |

Staging data is back to its baseline (3 users, 27 transactions, 2 ChatGPT
clients); no TCP proxy is open.

### Railway security incident — staging recovery (2026-10-23)

Railway's disclosure of 2026-10-21: environment variables may have been read.
For staging (production is the owner's decision and was not touched):

* **Review:** no deployment between 2026-10-18 and the recovery (all by the
  owner's account); no staged change; no TCP proxy; variable names unchanged;
  HTTP 2026-10-20…23 = 3 ChatGPT token refreshes and the owner's checks; no
  failed sign-in; Postgres logs routine. Railway's audit log was not readable
  with the available tools — rotation regardless.
* **Rotated** (names only): `MCP_OAUTH_PRIVATE_KEY`, `MCP_LOGIN_CSRF_SECRET`,
  `MCP_GRANT_FINGERPRINT_SECRET`, `MCP_DATA_SECRET`, `MCP_ANALYTICS_SECRET`,
  `JWT_SECRET`, `SECRET_KEY`, `MCP_METRICS_TOKEN`; the `postgres` password
  (Railway "Regenerate", by the owner); the `mita_mcp` password and
  `DATABASE_URL`. Both old database passwords were verified as rejected.
* **Consequences:** every staging ChatGPT connection and token issued before
  2026-10-23 is invalid — reconnect; analytics pseudonyms restart.
* Procedure and checks: `staging.md` → "Credential rotation".

## Previous phase: staging acceptance — CLOSED (2026-10-19)

`staging-acceptance-v2.md` §11.

| Item | State |
|---|---|
| Staging code | `79efb1d612999339814b02b5220b7cde2a13921d`, MCP 2.1.0 |
| Staging deployment | `87d26668-4051-42c3-99b7-2036d0de42cf` (project `mita-mcp-staging`), `/health` ok, alembic 0039, role `mita_mcp`, 1 replica, database TCP proxy closed |
| Evidence | CI run `39155447750` green; public staging checks §9; real ChatGPT §8 and S-8 §11 |
| `main` | `27ed25d`, not merged |
| Production | untouched: API on `3aa52b7` at alembic 0036, no MCP service, no setting, variable or secret changed |

## PR #287 must not be merged yet

PR #287 (`feat/chatgpt-plugin` → `main`) is open, not a draft and mergeable,
and `main` has no branch protection. `mita-production` follows `main` with no
commit pin, path filter, CI gate or healthcheck, and its `start.sh` runs
`alembic upgrade head` on boot (aborting in production on failure). A merge
therefore deploys the API and applies 0037–0039 to the production database;
a failed boot leaves nothing serving, and a rollback cannot boot against the
migrated database. Merge only as `production-readiness.md` Step 7 — after
Step 1 (credential rotation) and with the healthcheck (O-11a) and pre-flight
(O-11b) done.

## Known limitations (not blockers)

* A repeated, deliberate receipt request is caught by ChatGPT's judgement;
  MITA's idempotency covers retried tool calls, not content duplicates.
* F-2: shown as one line in ChatGPT, but the ledger still books `gas` apart
  from the `transport gas` plan (backend debt).
* F-7: a future scope addition needs existing ChatGPT connections to
  re-register.
* The description on ChatGPT's own developer-mode app object is owner-managed.
* The mobile app still ships the older hand-drawn logo
  (`mobile_app/assets/logo/mitalogo.png`); the Figma guidelines and the new
  sign-in page use the geometric logomark (`docs/brand/AUTH-UI-DESIGN.md`).
