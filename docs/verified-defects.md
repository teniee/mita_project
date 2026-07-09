# MITA Finance — Verified Defects

> Audit date: **2026-07-08 / 2026-07-09** · Auditor: Claude (Opus 4.8), read-only production auditor
> Deployed commit audited: **`d682f3f969a6`** (Railway `mita-production`, matches GitHub `teniee/mita_project@main`)
> Every defect below is backed by **first-hand evidence** (production HTTP response, server traceback from Railway logs, and/or local reproduction). Secrets are redacted everywhere.

## Severity legend
- **P0** — Blocks the defined core MVP journey or is a live security exposure. Fix before closed beta.
- **P1** — Breaks an important feature or a defined core step through a second/independent cause.
- **P2** — Degrades quality/observability; does not block the core journey.

## Summary table

| ID | Sev | Title | Subsystem | Verified how |
|----|-----|-------|-----------|--------------|
| DEF-001 | P0 | Transaction **list / get / delete** return HTTP 500 (`AsyncSession has no attribute 'query'`) | Backend / transactions | Prod HTTP 500 + Railway traceback |
| DEF-002 | P1 | Transaction **update (PUT)** returns HTTP 500 (amount validation `ConversionSyntax`) | Backend / transactions schema | Prod HTTP 500 + Railway traceback + **local repro** |
| DEF-003 | P0 | Live **secrets committed to the PUBLIC repo** (`.mcp.json`: Supabase key + Upstash Redis URL) | Security / secrets | File read + confirmed in public GitHub tree |
| DEF-004 | P1 | **Local working copy is stale** vs deployed (4 files behind PR #275, incl. token-blacklist security fix) | Repo / process | Blob-hash diff local vs GitHub + prod behavior |
| DEF-005 | P1 | **SMTP password not configured** → password-reset / verification email cannot send | Backend / email | Railway var inventory (no `SMTP_PASSWORD`) — *effect unverified* |
| DEF-006 | P2 | `/health` reports **`degraded`** because `SENTRY_DSN` is unset | Observability | Prod `/health` + Railway var inventory |
| DEF-007 | P2 | Mobile app runs in **`development`** env by default (SSL pinning / crash reporting off) | Flutter / build config | `mobile_app/lib/config.dart` |
| DEF-008 | P2 | Flutter transaction calls omit trailing slash → 307 redirect on every txn request | Flutter / transactions | `transaction_service.dart` + FastAPI route defs |

---

## DEF-001 — Transaction list / get / delete return HTTP 500 (async/sync session mismatch)

- **Severity:** P0 (breaks core-journey steps: view transactions, delete transaction)
- **Subsystem:** Backend — `app/api/transactions`
- **Status:** CONFIRMED in production (deployed `d682f3f969a6`)

**Evidence**
- Production request `GET /api/transactions/` → **HTTP 500**, body:
  `{"success":false,"error":{"code":"SYSTEM_8001","message":"Failed to retrieve transactions","error_id":"mita_0a8b3b9ab67f",...}}`
- Railway deploy log (server-side, same request):
  ```
  [ERROR] app.api.transactions.routes: Error retrieving transactions for user ...: 'AsyncSession' object has no attribute 'query'
    File "/app/app/api/transactions/services.py", line 165, in list_user_transactions
      query = db.query(Transaction).filter(
  ```
- `DELETE /api/transactions/{id}` → HTTP 500, traceback at `services.py:288` (`db.query(Transaction)`).

**Reproduction**
1. `POST /api/auth/register` → `POST /api/onboarding/submit` → `POST /api/transactions/` (this succeeds, 201).
2. `GET /api/transactions/` with the access token → **500**.
3. `DELETE /api/transactions/{id}` → **500**.

**Expected result:** `GET` returns the user's transactions (200); `DELETE` soft-deletes and returns `{deleted:true}` (200).
**Actual result:** Both return 500; the app's Transactions screen and delete action fail.

**Probable root cause (high confidence)**
The transaction routes inject an **`AsyncSession`** (`db: AsyncSession = db_dep`) but the service-layer functions are written against the **sync** SQLAlchemy `Session.query(...)` API. The **create** route works because it bridges correctly:
```python
# app/api/transactions/routes.py:130  (POST — WORKS)
result = await db.run_sync(lambda sync_session: add_transaction(user, txn, sync_session))
```
The list/get/update/delete routes instead call the sync services **with the raw AsyncSession** (no `db.run_sync`):
```python
# app/api/transactions/routes.py:285  (GET list — BREAKS)
transactions = list_user_transactions(user, db, ...)   # db is AsyncSession
# app/api/transactions/services.py:165
query = db.query(Transaction).filter(...)              # AsyncSession has no .query
```

**Involved files / lines**
- `app/api/transactions/routes.py` — `get_transactions_standardized` (~L285), `get_transaction` (~L798–826), `update_transaction_endpoint` (~L850), `delete_transaction_endpoint` (~L881)
- `app/api/transactions/services.py` — `list_user_transactions` (L165), `get_transaction_by_id` (L189), `update_transaction` (L209), `delete_transaction` (L288)

**Recommended fix direction (do NOT rewrite the module)**
Mirror the create route's proven pattern: wrap each sync service call in `await db.run_sync(lambda s: <service>(user, ..., s))`. (Alternative: convert the four service functions to native async using `select(...)` + `await db.execute(...)`, matching `app/api/dashboard/routes.py`, which already reads `Transaction` via async and works.) Apply consistently to list, get, update, delete.

**Required tests**
- API/integration: after create, `GET /api/transactions/` returns the created txn (200); `DELETE` returns 200 and the txn no longer lists.
- Regression: `GET /api/transactions/{id}` 200 (this path shares the same bug and is inferred-broken, not independently reproduced).
- Production smoke: extend `scripts/remote_smoke_test.py` to assert list/edit/delete round-trip.

**Production risk of the fix:** Low. Isolated to the transactions router; create path already demonstrates the correct bridge. Verify `apply_transaction_to_plan` (called inside update) also runs under the sync-bridged session.

---

## DEF-002 — Transaction update (PUT) 500: `TxnUpdate.amount` validator raises `ConversionSyntax` for every value

- **Severity:** P1 (independent second cause that blocks *edit transaction* even after DEF-001 is fixed)
- **Subsystem:** Backend — `app/api/transactions/schemas.py`
- **Status:** CONFIRMED in production **and reproduced locally**

**Evidence**
- Production `PUT /api/transactions/{id}` with `{"amount":100.00,"category":"food",...}` → **HTTP 500**.
- Railway deploy log:
  ```
  [ERROR] ...: Unhandled exception in middleware: ValidationError: Invalid transaction amount format: [<class 'decimal.ConversionSyntax'>]
    File "/app/app/api/transactions/schemas.py", line 52, in validate_amount
  ```
- **Local reproduction** (pydantic 2.9.2, this repo):
  ```
  TxnUpdate(amount=100.00)        -> ValidationError: ... [decimal.ConversionSyntax]
  TxnUpdate(amount="100.00")      -> ValidationError: ... [decimal.ConversionSyntax]
  TxnUpdate(amount=100)           -> ValidationError: ... [decimal.ConversionSyntax]
  TxnUpdate(amount=Decimal("100"))-> ValidationError: ... [decimal.ConversionSyntax]
  TxnIn(amount=100.00,...)        -> OK  (Decimal('100.00'))
  ```
  `TxnUpdate` **cannot be constructed with any amount value**; `TxnIn` (create) accepts them all.

**Expected result:** `TxnUpdate(amount=100.00)` yields `Decimal('100.00')`; `PUT` updates the amount (200).
**Actual result:** Body validation fails for any amount → 422/500; editing an amount is impossible.

**Probable root cause (high confidence)**
`TxnUpdate` re-registers `TxnIn`'s already-decorated validator in `before` mode:
```python
# app/api/transactions/schemas.py:271
validate_amount = field_validator("amount", mode="before")(TxnIn.validate_amount)
```
Re-wrapping the already-`@field_validator`-decorated classmethod causes `InputSanitizer.sanitize_amount` (schemas.py:52) to receive a non-numeric object, so `Decimal(str(amount))` raises `InvalidOperation`/`ConversionSyntax`. `TxnIn` works because it uses the validator natively (default `after` mode on the coerced `condecimal`).

**Involved files / lines**
- `app/api/transactions/schemas.py` — `TxnUpdate` (L258–277), reused validators (L271–277); `TxnIn.validate_amount` (L48–57); `InputSanitizer.sanitize_amount` in `app/core/validators.py` (L251+, `Decimal(str(amount))`).

**Recommended fix direction**
Give `TxnUpdate` its own validator that calls `InputSanitizer.sanitize_amount` on the raw value directly (e.g. a standalone module-level function reused by both models, or a fresh `@field_validator("amount")` on `TxnUpdate` that guards `None`). Do not re-decorate an already-decorated validator.

**Required tests**
- Unit: `TxnUpdate(amount=Decimal("100.00")).amount == Decimal("100.00")`; also `100.00`, `"100.00"`, `100`, and `amount=None` (no-op) all valid.
- API: `PUT /api/transactions/{id}` with a new amount returns 200 and dashboard/calendar recalculate.

**Production risk of the fix:** Low; schema-local.

---

## DEF-003 — Live secrets committed to the PUBLIC repository (`.mcp.json`)

- **Severity:** P0 (security exposure, public)
- **Subsystem:** Security / secret hygiene
- **Status:** CONFIRMED — file present in the public GitHub tree at the deployed commit

**Evidence**
- `.mcp.json` (repo root) contains, in plaintext:
  - a **Supabase secret key** (`sb_secret_…`, redacted) in an `Authorization: Bearer` header (project ref `atdcxppfflmiwjwjuqyl`);
  - a full **Upstash Redis URL including password** (`rediss://default:…@integral-jaybird-23463.upstash.io:6379`, redacted).
- The repository `teniee/mita_project` is **public**, and `.mcp.json` is in its tree (blob `ed19b3ad…`) at `d682f3f969a6` — i.e. the secrets are publicly retrievable and are in git history.

**Nuance (verified):** the leaked Upstash host `integral-jaybird-23463` does **not** match either Redis instance configured in Railway production (`wise-bonefish-101993`, `daring-moray-87435`). So the leaked credential is a **different/older** Upstash instance, not the current production Redis. It is still a live-format credential exposed publicly. (Liveness could not be confirmed in-session: the Redis MCP, configured against this instance, timed out.)

**Expected state:** No credentials in the repo; `.mcp.json` git-ignored or templated.
**Actual state:** Two credentials committed and public.

**Recommended remediation (owner — see `owner-actions.md`)**
1. **Rotate** the Supabase secret key (Supabase dashboard → project `atdcxppfflmiwjwjuqyl` → API keys) and the leaked Upstash Redis credential (or delete that Upstash DB if unused).
2. Remove `.mcp.json` from the repo, add to `.gitignore`, replace with a committed `.mcp.json.example` using placeholders.
3. **Purge git history** (e.g. `git filter-repo`) and force-push, or rotate-and-accept if history cleaning is impractical.
4. Consider making the repository private until history is cleaned.

**Production risk:** Rotation of an unused/old instance is low-risk; verify nothing in Railway references the `integral-jaybird` host before/after (it does not, per the variable inventory).

---

## DEF-004 — Local working copy is stale vs the deployed commit (must re-clone before edits)

- **Severity:** P1 (process/integrity — Fable 5 would otherwise edit a divergent base)
- **Subsystem:** Repo / workflow
- **Status:** CONFIRMED by blob-hash comparison + production behavior

**Evidence**
- The audited directory is **not a git checkout** (no `.git`; nested `mita_project-main/mita_project-main` = extracted GitHub ZIP).
- Blob-hash comparison of every local file vs GitHub tree `d682f3f969a6`: **1242/1246 identical**, **4 differ**, and the local versions are the **older** (pre-PR #275) ones:
  - `app/main.py` — local lacks docs-gating, `METRICS_TOKEN` gating, `_check_redis_health`, `get_alembic_revision`.
  - `app/core/async_session.py` — local lacks `get_alembic_revision()`.
  - `app/services/token_blacklist_service.py` — local still caches negative blacklist results (a revocation-masking pattern the deployed version fixed).
  - `scripts/remote_smoke_test.py` — local is the shorter, pre-hardening version.
- Production behavior proves prod runs the **newer** code: `/docs`,`/openapi.json`,`/metrics` → 404; `/health` returns `commit`, `alembic_revision`, and a live redis check — all only present in the deployed `main.py`, not the local one.

**Expected:** Local base == deployed commit.
**Actual:** Local base is behind by PR #275 in 4 files, including a token-revocation security fix.

**Recommended fix direction:** Fable 5 should **discard this local copy and clone fresh** from `teniee/mita_project@main` (`d682f3f969a6` or later) before any edits. Auditing this copy is valid for the other 1242 files (identical to deployed).

**Production risk:** N/A (process guidance).

---

## DEF-005 — Email (password reset / verification) cannot send: no SMTP password configured

- **Severity:** P1 (blocks password-reset flow; owner-config, not code)
- **Subsystem:** Backend / email + owner config
- **Status:** PARTIALLY VERIFIED — config gap confirmed; runtime failure **not** exercised (avoided sending real email)

**Evidence**
- Railway `mita-production` variables include `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`, `SMTP_USERNAME=apikey`, `SMTP_FROM=noreply@mita.finance` — but **no `SMTP_PASSWORD`**. SendGrid SMTP requires the API key as the password when username is `apikey`.

**Expected:** Password-reset / verification emails send successfully.
**Actual (inferred):** Without `SMTP_PASSWORD`, SMTP auth to SendGrid fails → reset/verification emails cannot be delivered.

**Recommended fix direction:** Owner sets `SMTP_PASSWORD` = SendGrid API key in Railway. Then verify the reset endpoint returns success and an email arrives.

**Required tests / verification:** After config, hit the password-reset endpoint with a mailbox you control; confirm delivery and that the reset link works.

**Production risk:** Config-only.

---

## DEF-006 — `/health` reports `degraded` solely due to unconfigured Sentry

- **Severity:** P2 (observability; can be misread as an outage by uptime checks)
- **Subsystem:** Observability / health reporting
- **Status:** CONFIRMED

**Evidence**
- Prod `/health` → `"status":"degraded"`, `"sentry":"unavailable"`, `"sentry_configured":false`; all of `database`,`redis`,`firebase` are healthy.
- Railway vars: `SENTRY_TRACES_SAMPLE_RATE` / `SENTRY_PROFILES_SAMPLE_RATE` are set but **no `SENTRY_DSN`**.

**Expected:** `healthy` when all *core* dependencies are up; optional integrations should not force `degraded`.
**Actual:** Missing `SENTRY_DSN` alone flips the aggregate to `degraded`.

**Recommended fix direction:** Either set `SENTRY_DSN` (owner) or treat Sentry as optional in the health aggregation so its absence does not degrade the top-level status. (Note: the deployed `app/main.py` owns this logic; edit on a fresh clone.)

**Production risk:** Low.

---

## DEF-007 — Mobile app defaults to `development` environment

- **Severity:** P2 (release hardening)
- **Subsystem:** Flutter build config
- **Status:** CONFIRMED (static)

**Evidence:** `mobile_app/lib/config.dart:22` — `environment` defaults to `development` unless `--dart-define=ENV=production`. In `development`: `useSSLPinning=false`, `enableCrashReporting=false`, `enableAnalytics=false`, 30s timeout. Base URL still defaults to prod Railway.

**Recommended fix direction:** Build release artifacts with `--dart-define=ENV=production` (and the `FIREBASE_*` defines — see owner-actions). Document the exact build command.

---

## DEF-008 — Flutter transaction requests omit the trailing slash (307 redirect)

- **Severity:** P2 (latency / redirect-header fragility)
- **Subsystem:** Flutter / transactions
- **Status:** CONFIRMED (static)

**Evidence:** `mobile_app/lib/services/transaction_service.dart` builds `'${AppConfig.fullApiUrl}/transactions'` (no trailing slash), but the FastAPI routes are declared as `/transactions/` and `/transactions/{id}`. FastAPI issues a 307 redirect from the slashless collection path. Every list/create request pays a redirect round-trip; some HTTP clients drop the `Authorization` header or body across redirects.

**Recommended fix direction:** Use the exact route paths (trailing slash for the collection) in the Dart client, or configure the client to preserve auth/body across redirects. Low priority relative to DEF-001/002, but fix alongside the transactions work.
