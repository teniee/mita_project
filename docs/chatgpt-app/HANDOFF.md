# Handoff — MITA in ChatGPT (MCP), 2026-10-21

## Current phase: sign-in / first-impression UI — waiting for owner design approval

| Item | State |
|---|---|
| Branch | `feat/chatgpt-auth-ui`, a child of `feat/chatgpt-plugin` @ `200c34d`; head `8c5116b` (`fc9aeeb` the UI, `8c5116b` import order) plus this documentation |
| What changed | the `/oauth/login` sign-in / sign-up / consent page and its error pages (`app/mcp/auth/pages.py`, `browser_errors.py`, self-hosted fonts); `login.py` keeps the verified flow; scopes unchanged |
| Design source | Figma Brand Guidelines `512WdjnhPJXM8jeHKcg4g8` → `docs/brand/AUTH-UI-DESIGN.md` |
| Tests | MCP suite 513 passed (baseline 487 + 26 in `test_auth_ui.py`, now in the CI security gate); `e2e_v2.py` 77 checks and `e2e_http.py` both phases against a local server; axe-core 0 violations; text contrast ≥ 4.85:1 |
| Screenshots | `docs/chatgpt-app/review/auth-ui/` (12, fictional data) |
| Staging | see "Staging deployment" below |
| Owner test | `auth-ui-owner-test.md` (≈ 5 minutes) |
| PR #287, `main`, production | untouched: PR head still `200c34d`, `main` `27ed25d`, no production deploy, migration, variable or secret change |

Next: the owner reviews the page on staging. After approval, decide how the
branch joins `feat/chatgpt-plugin` (PR #287); launch preparation follows
`production-readiness.md`. Not started and not to start without the owner:
Plugin Directory submission, production MCP, production migrations, the
analytics dashboard.

### Staging deployment

Pending — Railway paused all builds and deployments (incident "Dashboard and
API unavailable, builds paused", 2026-10-21 from ~17:00 UTC). The staging
service source was re-pinned to `feat/chatgpt-auth-ui` @ `fc9aeeb` before the
pause refused the build; staging still runs `87d26668` (`79efb1d`, MCP 2.1.0).

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
