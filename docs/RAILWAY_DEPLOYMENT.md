# MITA Backend — Railway Deployment Checklist & Staging Plan

> **Status:** the previous service at `https://mita-production-production.up.railway.app`
> no longer exists (Railway edge returns `{"status":"error","code":404,"message":"Application not found"}`,
> proven from GitHub runners). A **new** Railway service must be created. This document is the
> complete, verified recipe for doing that from an empty Railway project.
>
> **Source of truth for code state:** `docs/PRODUCTION_READINESS.md`.

---

## 1. What Railway needs to know (build & run)

| Item | Value | Verified where |
|------|-------|----------------|
| Repository | `teniee/mita_project` | — |
| Branch | `main` (deploy only main; PR #273 merged 2026-07-07, main CI run #229 green) | GitHub Actions |
| Builder | **Dockerfile at repo root** (multi-stage, Python 3.12-slim, non-root user, tesseract included). Railway auto-detects it. `nixpacks.toml` also exists as a fallback — if Railway ever picks Nixpacks instead, it runs the same `./start.sh`, so behavior is identical. | `Dockerfile`, `nixpacks.toml` |
| Start command | none needed — Dockerfile `CMD ["./start.sh"]` (`scripts/deployment/start.sh`) | `Dockerfile` |
| Port | The app binds `0.0.0.0:$PORT` (default 8000). Railway injects `PORT` automatically — **do not hardcode it**. In service Settings → Networking, generate a public domain; Railway routes it to `$PORT`. | `start.sh` |
| Health check path | `/health` (set in Railway service settings; Dockerfile HEALTHCHECK also probes it) | `app/main.py:456` |
| Migrations | run automatically at boot: `start.sh` executes `python -m alembic upgrade head` **before** uvicorn and **aborts startup in production if migration fails** (fail-closed, no create_all in the prod path). No separate deploy hook needed. Current head: `0034`. | `start.sh`, `alembic/` |
| Workers | `WEB_CONCURRENCY` env var (default 1, validated 1–16). Start with 2 for closed beta on a Hobby plan. | `start.sh` |

### What start.sh does at boot (in order)
1. Validates required env vars when `ENVIRONMENT=production`: `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET`, `OPENAI_API_KEY` — **exits 1 if any is missing**.
2. Warns loudly (but continues, degraded) if no Redis config and if no `SENTRY_DSN`.
3. Runs `alembic upgrade head`; in production a migration failure **aborts startup**.
4. Starts `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers $WEB_CONCURRENCY` (uvloop if available).

Additionally, `app/core/config.py` **crashes on any settings error whenever `RAILWAY_ENVIRONMENT` is set** (Railway always sets it), even if you forget `ENVIRONMENT=production` — the app never silently falls back to dev defaults on Railway.

---

## 2. Environment variables — complete reference

Generate secrets with `openssl rand -hex 32` (or `-base64 32`).

### 2.1 Required — the app will not start in production without these

| Variable | Format / example | Where you get it | What breaks if absent |
|----------|------------------|------------------|-----------------------|
| `ENVIRONMENT` | `production` (use `staging` semantics via a separate service but still set `production` for strict validation, see §4) | you choose | Without it, prod validation and CORS lockdown are off; secrets get auto-generated per process (sessions break across restarts/workers) |
| `DATABASE_URL` | `postgresql://USER:PASSWORD@HOST:6543/postgres?pgbouncer=true` (Supabase transaction pooler) or any PostgreSQL 15/16 URL. `postgres://` and `postgresql://` are both accepted; the app converts to `asyncpg` itself. | Supabase dashboard → Project Settings → Database → Connection string (Transaction pooler), or Railway PostgreSQL plugin (`${{Postgres.DATABASE_URL}}`) | start.sh exits 1 |
| `JWT_SECRET` | ≥32 random chars | generate | start.sh exits 1; tokens unverifiable |
| `SECRET_KEY` | ≥32 random chars, different from JWT_SECRET | generate | start.sh exits 1 |
| `OPENAI_API_KEY` | `sk-...` | platform.openai.com → API keys | start.sh exits 1 (hard-required even though AI features degrade gracefully at runtime) |

### 2.2 Strongly recommended — app starts but runs degraded without them

| Variable | Format / example | Where you get it | What breaks if absent |
|----------|------------------|------------------|-----------------------|
| `REDIS_URL` | `redis://default:PASSWORD@HOST:PORT` (or `rediss://` for TLS) | Railway Redis plugin (`${{Redis.REDIS_URL}}`) or Upstash dashboard | Rate limiting becomes per-process in-memory; **JWT revocation/logout blacklist unavailable**; task queue may drop jobs; cache is per-process |
| `UPSTASH_REDIS_URL` / `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` | Upstash alternatives to `REDIS_URL` — set one family, not all | Upstash console | same as above |
| `SENTRY_DSN` | `https://KEY@oNNN.ingest.sentry.io/NNN` | sentry.io → project → Client Keys | No error monitoring: exceptions happen silently, blind deploys |
| `WEB_CONCURRENCY` | integer 1–16, e.g. `2` | you choose | Defaults to 1 worker (fine, just lower throughput) |

### 2.3 JWT rotation

| Variable | Format | Where you get it | Required? |
|----------|--------|------------------|-----------|
| `JWT_PREVIOUS_SECRET` | the *old* `JWT_SECRET` value during a rotation window | your own records | Optional. Only set while rotating `JWT_SECRET` so tokens signed with the old secret keep validating until they expire. For a brand-new service with no existing users, **leave unset**. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | positive int (default `120`) | you choose | Optional |

### 2.4 Firebase / push notifications (backend side)

| Variable | Format | Where you get it | Required? / what breaks |
|----------|--------|------------------|--------------------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | absolute path to a service-account JSON file *inside the container*, e.g. `/app/secrets/firebase-sa.json`. On Railway put the JSON content in a variable (e.g. `FIREBASE_SA_JSON`) and write it to disk in a pre-start step, or use Railway's file mounts. | Firebase console → Project settings → Service accounts → Generate new private key | Optional for closed beta. Absent → FCM push notifications disabled; everything else works |
| `APNS_KEY`, `APNS_KEY_ID`, `APNS_TEAM_ID` | .p8 key content / 10-char key id / 10-char team id | Apple Developer → Keys | Optional (iOS push only; no iOS build yet) |
| `APNS_TOPIC` | bundle id, default `com.mita.finance` | — | Optional |
| `APNS_USE_SANDBOX` | `false` in production | — | Optional (defaults false) |

### 2.5 OpenAI

| Variable | Format | Required? |
|----------|--------|-----------|
| `OPENAI_API_KEY` | `sk-...` | **Yes** (see §2.1) |
| `OPENAI_MODEL` | default `gpt-4o-mini` | Optional |

### 2.6 SMTP (password-reset emails)

| Variable | Format / example | Where you get it | What breaks if absent |
|----------|------------------|------------------|-----------------------|
| `SMTP_HOST` | `smtp.sendgrid.net` | your email provider | Password-reset emails cannot be sent (endpoint fails gracefully) |
| `SMTP_PORT` | `587` (default) | provider docs | — |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | provider credentials | provider dashboard | — |
| `SMTP_FROM` | default `noreply@mita.finance` | you choose (must be a verified sender) | — |

### 2.7 CORS

| Variable | Format | Required? |
|----------|--------|-----------|
| `ALLOWED_ORIGINS` | comma-separated HTTPS origins. Default already includes `https://mitafinance.com`, `https://www.mitafinance.com`, `https://app.mita.finance`, `https://mita.finance`, `https://mitafinance.app`, `https://admin.mita.finance`. Localhost origins are auto-added **only** outside production. | Optional — default is correct for closed beta. Note: the mobile app is not a browser; CORS does not affect it. |

### 2.8 In-app purchases (fail closed — set before enabling IAP, not before beta)

| Variable | Format | Where you get it | What breaks if absent |
|----------|--------|------------------|-----------------------|
| `IAP_ALLOWED_PRODUCT_IDS` | comma-separated store product ids | your App Store / Play Console product setup | IAP validation refuses all receipts (fail closed — safe) |
| `APPLE_BUNDLE_ID` | `com.mita.finance` | App Store Connect | Apple receipt/webhook verification fails closed |
| `APPLE_ROOT_CA_PATH` | container path to AppleRootCA-G3 PEM bundle | apple.com/certificateauthority | same |
| `APPSTORE_SHARED_SECRET` | 32-hex | App Store Connect → App Information | same |
| `GOOGLE_SERVICE_ACCOUNT` | container path to a Play service-account JSON | Play Console → API access | Google subscription verification fails closed |
| `GOOGLE_PACKAGE_NAME` | `mita.finance` (must match `applicationId`) | Play Console | same |
| `GOOGLE_PUBSUB_AUDIENCE` / `GOOGLE_PUBSUB_SERVICE_ACCOUNT` | OIDC audience URL / SA email | GCP Pub/Sub RTDN setup | RTDN webhooks rejected (fail closed) |
| `IAP_ALLOW_SANDBOX` | must be `false` (default) in production | — | — |

### 2.9 Supabase / PgBouncer specifics (already handled in code — read before choosing a DB)

- The async engine **rewrites** `sslmode=` → `ssl=` and **appends `ssl=require`** if no SSL param is present (`app/core/async_session.py`). You do not need to add SSL params manually, but they are accepted.
- Prepared statements are **disabled** (`statement_cache_size=0`, `prepared_statement_cache_size=0`) — required for PgBouncer/Supabase **transaction-mode** pooler (port 6543). Session-mode (port 5432) also works.
- Alembic (`alembic/env.py`) strips the `pgbouncer=true` query param for psycopg2 and auto-detects the Supabase transaction pooler; migrations run fine through port 6543.
- Pool settings are conservative for pooled providers: `pool_size=5`, `max_overflow=10`, `pool_recycle=1800`, `pool_pre_ping=true`. With `WEB_CONCURRENCY=2` that is at most 30 server connections — fine for Supabase free/pro poolers and Railway PG.
- **Recommendation for closed beta:** Railway's own PostgreSQL plugin is the simplest (no pooler quirks, private networking). Supabase works too via the transaction pooler URL.

---

## 3. Verified: boot from an empty environment with only documented variables

Verified locally on commit `73c1817` (= current main): empty PostgreSQL 16 database +
Redis 7, environment containing **only** `ENVIRONMENT=production`, `DATABASE_URL`,
`JWT_SECRET`, `SECRET_KEY`, `OPENAI_API_KEY` (dummy value — start.sh requires presence,
runtime degrades gracefully), `REDIS_URL`, `PORT`. Result: migrations 0001→0034 applied,
uvicorn started, `GET /` and `GET /health` returned healthy, and the full 19-check smoke
journey (`scripts/remote_smoke_test.py`) passed. See `docs/PRODUCTION_READINESS.md` for
the exact run log summary.

---

## 4. Staging deployment plan — exact steps

Goal: a service named `mita-staging` running current `main`, isolated data, safe to smoke-test.

**Step 0 — prerequisites (owner):**
- Railway account with a payment method (Hobby plan is enough for beta).
- The GitHub app connection Railway ↔ `teniee/mita_project` authorized.

**Step 1 — create project & service:**
1. Railway dashboard → New Project → Deploy from GitHub repo → `teniee/mita_project`.
2. Set the service's **branch to `main`** (Settings → Source). Name the service `mita-staging`.
3. Railway detects the Dockerfile automatically. Leave start command empty.

**Step 2 — add data services (same project):**
1. New → Database → **PostgreSQL**. Note the reference variable `${{Postgres.DATABASE_URL}}`.
2. New → Database → **Redis**. Note `${{Redis.REDIS_URL}}`.
   (Using Railway plugins avoids Supabase/Upstash signup for staging; production can differ.)

**Step 3 — set variables on `mita-staging`** (Settings → Variables → Raw editor):

```bash
ENVIRONMENT=production        # yes, staging too: we want prod-strict validation & CORS
DATABASE_URL=${{Postgres.DATABASE_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
JWT_SECRET=<openssl rand -hex 32>          # owner generates
SECRET_KEY=<openssl rand -hex 32>          # owner generates, different value
OPENAI_API_KEY=<sk-... or a dummy sk-staging-placeholder>  # presence is required; AI features degrade gracefully if invalid
WEB_CONCURRENCY=2
SENTRY_DSN=<optional but recommended>
```
Do **not** set `JWT_PREVIOUS_SECRET`, IAP, APNS, SMTP, or Firebase vars for staging — all
those paths fail closed / degrade gracefully.

**Step 4 — health check & domain:**
1. Settings → Deploy → Health check path: `/health`, timeout 300s (first boot runs 34 migrations).
2. Settings → Networking → Generate Domain → note the URL, e.g. `https://mita-staging-production.up.railway.app`.

**Step 5 — deploy & watch logs.** Expected log sequence: env-check ✅ → `alembic upgrade head`
(0001→0034) → `✅ Migrations completed successfully` → uvicorn on `0.0.0.0:$PORT`.
- If it crashes with `DATABASE_URL is not set` → the reference variable didn't resolve; paste the literal URL.
- If migrations fail → check the DB is empty/reachable; the app **will not start** with a broken schema (by design).

**Step 6 — run the deployed smoke test (19 checks) from GitHub:**
- Actions → **“Deployed Backend Smoke Test”** → Run workflow → `base_url` = the staging URL.
- Alternative (no dispatch permission): push any commit whose message contains `[deployed-smoke]`
  to a `claude/**` branch — it runs against the workflow default URL, so prefer manual dispatch for staging.
- Pass criteria: 19/19 (liveness, register, login, onboarding, budget generation, transaction,
  saved calendar with 31 days / today present / all limits > 0 / spent reflected / YYYY-MM-DD keys,
  day detail, refresh rotation, logout, 404 stays 404, 4xx never 500).

**Step 7 — point a mobile build at staging** (see `docs/ANDROID_RELEASE.md`):
```bash
flutter build apk --release \
  --dart-define=API_BASE_URL=https://<staging-domain> \
  --dart-define=ENV=staging
```

**Promotion to production:** repeat steps 1–6 as `mita-production` with real `OPENAI_API_KEY`,
real `SENTRY_DSN`, SMTP, and (when store setup exists) Firebase + IAP variables. Keep staging
and production JWT secrets different.

---

## 5. Owner-action summary (nothing in this list can be done from the repo)

| # | Action | Blocking for |
|---|--------|--------------|
| 1 | Create Railway project + PG + Redis, set §4 variables, deploy | everything deployed |
| 2 | Provide the staging/production base URL back to engineering | remote E2E, mobile builds |
| 3 | Run (or allow us to run) the Deployed Backend Smoke Test workflow | deployed verification |
| 4 | Real `OPENAI_API_KEY` for production | AI insights quality (not startup) |
| 5 | Sentry project + DSN | error monitoring |
| 6 | SMTP credentials | password-reset emails |
| 7 | Firebase service account + `google-services.json` + FIREBASE_* dart-defines | push notifications, Crashlytics |
| 8 | Play Console + App Store IAP setup (§2.8) | paid subscriptions (not needed for free beta) |
| 9 | Android release keystore (see `docs/ANDROID_RELEASE.md`) | Play internal-testing distribution |
