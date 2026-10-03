# MITA repository audit for the ChatGPT app (MCP)

Audited on 2026-10-02 against `origin/main` = `27ed25d` (branch
`feat/chatgpt-plugin` was created from the same SHA: 0 ahead / 0 behind).
Everything below was read in code, not taken from README or older audit
documents. Where a claim could not be checked it says so.

## 1. Existing architecture (mobile path)

```
Flutter app (mobile_app/)
   │  HTTPS, Bearer <MITA HS256 JWT, iss=mita-finance-api, aud=mita-finance-app>
   ▼
FastAPI monolith  app/main.py   (Railway service "mita-production", start.sh → alembic upgrade head → uvicorn)
   │  get_current_user (app/api/dependencies.py) → verify_token (app/services/auth_jwt_service.py)
   ▼
Routers app/api/*/routes.py  ──►  services / engines (mostly SYNC SQLAlchemy, bridged with AsyncSession.run_sync)
   │                                 app/services/core/engine/expense_tracker.py   (ledger, tz helpers, month rebuild)
   │                                 app/services/monthly_plan_service.py          (lazy month materialization — WRITES)
   │                                 app/services/core/engine/budget_forecast_engine.py (pure Decimal)
   │                                 app/services/core/engine/budget_tracker.py    (plan aggregation)
   │                                 app/services/iap/entitlements.py               (premium source of truth)
   ▼
PostgreSQL (Supabase, session pooler) + Redis (Upstash: rate limit, token blacklist)
```

## 2. Target architecture (ChatGPT path)

```
ChatGPT
   │  OAuth 2.1 (Authorization Code + PKCE S256, DCR, resource=https://<MCP_HOST>/mcp)
   ▼
MITA MCP service  (python -m app.mcp; separate Railway service, same repo, same image)
   ├─ /.well-known/oauth-protected-resource/mcp     RFC 9728
   ├─ /.well-known/oauth-authorization-server       RFC 8414 (built-in AS, official MCP SDK handlers)
   ├─ /authorize /token /register /revoke           SDK handlers + MITA provider (app/mcp/auth/provider.py)
   ├─ /oauth/login                                  MITA credential check + consent (app/mcp/auth/login.py)
   ├─ /.well-known/openai-apps-challenge            domain verification token
   ├─ /health                                       liveness/readiness
   └─ /mcp   streamable HTTP, stateless, Bearer RS256 JWT (aud = resource)
          │  JWTTokenVerifier → McpPrincipal(user_id from `sub`, scopes)
          ▼
       read-only tools (app/mcp/tools/*)  — never accept user_id
          │
          ▼
       query layer (app/mcp/queries/*) — READ ONLY transaction, reuses:
          expense_tracker.local_day_of / local_day_utc_window   (timezone)
          budget_forecast_engine.compute_forecast               (forecast + goal projection)
          monthly_plan_service.month_bounds                     (plan month window)
          ▼
       same PostgreSQL (no writes to financial tables)
```

The MCP service does **not** call the REST API over HTTP; it imports the same
Python modules and opens its own pool to the same database.

## 3. What can be reused, and how

| Concern | Canonical code | Reuse in MCP | Notes |
|---|---|---|---|
| User's local day | `expense_tracker.local_day_of`, `local_day_utc_window`, `_safe_zone` | direct import | invalid tz name falls back to UTC (existing behavior) |
| Plan rows (allocation) | `daily_plan` written by onboarding / `ensure_month_plan` / `rebuild_month_plan` | read only | `date` = midnight UTC of the **local** calendar day |
| Spend | `transactions` (ledger, `deleted_at IS NULL`) | read only | `daily_plan.spent_amount` is a cache rebuilt from the ledger by `rebuild_month_plan`; MCP reads spend from the ledger with the same keys so every tool agrees |
| Forecast | `budget_forecast_engine.compute_forecast` (pure, Decimal) | direct call with the user's **local** today | REST route passes server `date.today()` and the UTC month (see data-trust audit) |
| Goals | `goals` table + `_compute_goal_forecast` via `compute_forecast` | direct call | |
| Premium | `users.is_premium` / `premium_until`, maintained by `iap/entitlements.apply_subscription_state` | not used in v1 | v1 exposes no paid-only data |
| Recurring | `scheduled_expenses` (user-declared, `recurrence`), `transactions.is_recurring` (user-flagged) | read only | no inference engine exists; `recurring_expense_handler.inject_recurring_expenses` imports a `RecurringExpense` model that does not exist (dead code) |
| Credential check | `app/api/auth/login.py` (lockout after 5 failures / 30 min) | mirrored in `app/services/credential_verification.py` for the consent page; the mobile route is untouched | same `users` lockout columns, so one counter |

### Business logic that lives in routes (not reused as-is)

* `/budget/live_status` (`app/api/budget/routes.py:668`) computes `on_track`
  from `monthly_income * day/30` — income treated as budget, 30-day month.
* `/budget/forecast` (`:347`) computes the target month in UTC and lets the
  engine use the server date — wrong near local midnight / month edge.
* `/budget/daily` (`:448`) reports `remaining = 0.0` whenever `spent_amount`
  is 0 (truthiness check on Decimal) — a day with nothing spent shows nothing
  remaining.
* `list_user_transactions` mutates ORM `spent_at` in place to local time; the
  MCP layer converts on serialization instead.

## 4. Writes on read paths

`ensure_month_plan*` (called by `/budget/*`, `/calendar/*`, `/dashboard`)
materializes a month on first read. It is idempotent and canonical, but it
writes. The MCP service runs every tool in a `READ ONLY` database transaction,
so it never materializes a month. A month with no plan is reported as
`plan_status: "not_generated"` — the mobile app (or the first REST read)
creates it. See ADR §"Read-only enforcement".

## 5. Auth as found

* MITA access tokens: HS256, shared `JWT_SECRET`, `iss=mita-finance-api`,
  `aud=mita-finance-app`, scopes from `TokenScope` (basic users get
  `write:*` scopes by default). Revocation = `users.token_version` bump +
  Redis `jti` blacklist (fail-open).
* There is no OAuth authorization endpoint, no PKCE, no client registration,
  no JWKS, no per-resource audience. **The MITA JWT cannot be used by ChatGPT.**
* Google sign-in users get a random password hash
  (`google_auth_service.py:46`): they cannot complete a password login (see
  OWNER_ACTIONS / known limitations).

## 6. Deployment as found

* Railway project "Mita Finance", service `mita-production`, Nixpacks
  (`nixpacks.toml`) + `start.sh`; `Dockerfile` exists but runs
  `scripts/deployment/start.sh`. Auto-deploy from `main`.
* No `railway.json`/`railway.toml` in the repo.
* CI (`.github/workflows/main-ci.yml`) runs on push to `main`/`claude/**` and
  PRs to `main`: black, isort, ruff, alembic upgrade, pytest (`app/tests`),
  bandit, Flutter suite. `feat/**` pushes were not covered.

## 7. Domain and public pages (checked 2026-10-02)

| Host | Result |
|---|---|
| `mita.finance` | **not registered** (Identity Digital RDAP 404; control `google.finance` → 200) |
| `api.mita.finance`, `mcp.mita.finance` | no DNS |
| `mitafinance.com` | registered (IONOS, expires 2027-05-10); **HTTPS fails** (TLS internal error); HTTP serves one landing page for every path — `/privacy`, `/terms`, `/support` are not real pages |
| `mita-production-production.up.railway.app/health` | 200 |

Consequences: every `@mita.finance` address in the policies, the SMTP default
`noreply@mita.finance`, `ALLOWED_ORIGINS` entries and the brief's
`mcp.mita.finance` point at a domain MITA does not own. The MCP host is
configuration (`MCP_PUBLIC_URL`); documentation uses `mcp.mitafinance.com`.

## 8. Other confirmed findings

See `security-findings.md` (secrets), `data-trust-audit.md` (financial data
sources) and `legal-audit.md` (policy claims).
