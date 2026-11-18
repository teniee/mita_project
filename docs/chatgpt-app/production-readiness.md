# Production readiness — MITA ChatGPT app (2026-10-11, v2 update 2026-10-13, re-checked 2026-10-26)

v1 (8 read-only tools) passed real-ChatGPT staging acceptance
(staging-acceptance.md §5). v2 — free v1 read/write, 22 tools, migrations
0038–0039 — is verified over public staging HTTPS and, by the owner, in real
ChatGPT (staging-acceptance-v2.md §8, 2026-10-18). The issues that run found
are fixed in MCP 2.1.0 (`79efb1d`), deployed to staging as `87d26668`,
verified over public HTTPS (§9) and in the owner's final real-ChatGPT smoke
test S-8 (§11). **Staging is closed (2026-10-19). Production remains
untouched. The next stage is launch/production preparation**, starting from
the steps below; `HANDOFF.md` has the state and the merge warning.
Production is untouched: no deploy, no variable or setting change, `main` not
merged. **Every production step below needs the owner's explicit
authorization**; owner click-paths and commands are in `OWNER_ACTIONS.md`
under the same step numbers.

**A** = autonomous preparation (done in the repo, no production change).
**B** = owner action (credentials, DNS, legal, billing, verification or
production access).

## State on 2026-11-17 and the 2.11.0 deploy plan (supersedes everything below)

Gate 1 (financial safety, migration 0045): `scheduled-obligations-safety.md`.
Every step in this section needs the owner's explicit go-ahead. Nothing here
has been executed.

### Production as observed on 2026-11-17 (read-only: Railway, public `/health`)

| Fact | Evidence |
|---|---|
| Project `Mita Finance` holds exactly two services, `mita-production` and `mita-production-db`. There is **no MCP service**. | Railway `list-services` |
| **No TCP proxy** on `mita-production-db` or on `mita-production`. The public database proxy recorded on 2026-10-27 is gone. | Railway `list-tcp-proxies`: `[]` for both |
| `mita-production` builds from `main` with `checkSuites: false` and starts with `bash start.sh` (1 replica, us-east4). It still has **no healthcheck**. | Railway `get-service-config`: no healthcheck in `deploy` |
| The active deployment is `d4c2547c` (2026-09-29) of `3aa52b7`, and it can be rolled back. `main` HEAD `27ed25d` (#286, merged 2026-09-29 18:00 UTC, mobile files only) **was never deployed**. | Railway `list-deployments`; `git diff --stat 3aa52b7 27ed25d` touches only `mobile_app/` |
| `/health`: HTTP 200, `"status":"degraded"` (Sentry not configured; database, Redis and Firebase connected), commit `3aa52b78a0e1`, `alembic_revision` `0036` | `GET https://mita-production-production.up.railway.app/health` |
| `mita-production-db`: image `postgres-ssl:17`, one replica, one volume. Railway applies **automatic vulnerability image updates** on Saturdays 10–24 and Sundays 0–18 UTC. | Railway `get-service-config` |
| API image (`requirements.txt`, unchanged by PR #288 since 2026-07-15): `pip-audit` finds **214** entries (143 distinct advisories) in 9 pinned packages. MCP lock: 0. | `pip-audit` 2.10.1, 2026-11-17 (review G4-02/G4-03) |

### What merging PR #288 does to production

`main` auto-deploys and `start.sh` runs `alembic upgrade head` before uvicorn,
aborting in production if that fails. The merge therefore applies **0037 → 0045
in one transaction** (`alembic/env.py`: no `transaction_per_migration`).

* **0037–0044** add 14 tables and the `analytics` schema with 14 views.
* **0045** adds two columns and two CHECKs to `scheduled_expenses`
  (`scheduled-obligations-safety.md`).

The merge also changes the mobile ledger, forecast and rebalancing code:
F-8, F-9/F-10, R3, 2.7.0, and G0-01's mobile rule. It is not only a set of
behaviour-preserving extractions.

### Plan (each step: owner go-ahead; E = engineering, O = owner)

**P0 — before the merge**

1. **E:** CI is green on the final PR head.
2. **E + O:** Staging runs the final head with 0045 applied, through an
   owner-authorised temporary SSH key (`staging.md`).
   * The MCP image of this head is not ready without 0045's columns.
   * Then: `smoke_envelopes_2100`, `calendar_widget_review --axe`, `e2e_v2`,
     `smoke_behavioral_270`, and the log scan.
   * Then the owner's real-ChatGPT acceptance (`acceptance-2.11.0-chatgpt.md`
     and the release script).
   * On staging, after 0045: `UPDATE scheduled_expenses SET origin =
     'chatgpt'`. Every staging row was written by the MCP service or its
     scripts.
3. **O:** Rotate the production secrets (O-1…O-4).
   * `scripts/mcp/check_leaked_secrets.py` prints names only.
   * The `postgres` password changes only through Railway **Regenerate**.
   * The TCP proxy is already removed: keep it that way.
4. **O:** Healthcheck on `mita-production`: path `/health`, timeout 300 s.
   * Applying the setting deploys `main` HEAD `27ed25d`, whose backend is
     identical to `3aa52b7`. That also closes the undeployed-commit gap.
   * Verify that `/health` shows commit `27ed25d…` and `alembic_revision`
     `0036`.
   * Optional: **Wait for CI** (`checkSuites`).
5. **O + E — an independently restorable backup. Required, no merge
   without it.** Over an owner-authorised temporary SSH key (no TCP proxy):
   * Stream `pg_dump -Fc` of `mita-production-db` **off the production
     volume**: to the operator machine, or to storage the owner controls
     outside the production project. A dump on the database's own volume is
     not independent: it dies with that volume.
   * Restore it into a **separate** scratch database (local PostgreSQL 17, or
     a throwaway Railway service). Compare row counts of every table and the
     money totals (`SUM(amount)` of `transactions`, `daily_plan.planned_amount`,
     `scheduled_expenses`) with production at dump time. Record the sha256 and
     the `alembic_version` (0036).
   * The dump holds users' financial data. Keep it encrypted, readable by
     the owner only, and delete it when the owner closes the release window.
   * Revoke the key.
6. **O + E:** Run a read-only pre-flight over the same path:
   * `alembic_version = '0036'`;
   * no schema `analytics`;
   * none of the 14 new tables exist;
   * `users.id`, `transactions.id` and `scheduled_expenses.id` are uuid
     primary keys;
   * `scheduled_expenses` has no `origin` or `day_of_month` column;
   * no long-running transaction (`pg_stat_activity`);
   * the migrating role can `CREATE`;
   * the count of pending `scheduled_expenses` (context for G0-01).
7. **O decision:** The API's dependency advisories. They are not introduced
   by this PR. Either:
   * an upgrade change before the merge, starlette/FastAPI,
     python-multipart and Pillow first, then the rest (G4-03 lists the
     reachable paths: unauthenticated `FileResponse` Range on
     `/privacy-policy` and `/terms-of-service`, multipart parsing on auth
     and OCR, Pillow on authenticated OCR uploads), with full Backend and
     Mobile CI; or
   * a written risk acceptance.
8. **O decision:** The rollback policy is fix-forward (below).

**P1 — merge (owner, low traffic)**

9. **Required:** for this boot only, set `MIGRATION_DATABASE_URL` to the
   database URL plus `options=-c lock_timeout=5000`.
   * The single 0037 → 0045 transaction takes foreign-key locks on `users`
     and `transactions`, then `ACCESS EXCLUSIVE` on `scheduled_expenses`.
   * Without a timeout, one open transaction of the old deployment makes the
     boot wait indefinitely while requests queue behind it (independent
     review, finding 9).
   * With it, a blocked lock aborts cleanly, DDL rolls back to 0036, and the
     healthcheck keeps the old deployment serving. Retry later.
   * Remove the variable afterwards.
10. Merge PR #288. **Check that a deployment of the merge commit appears.**
    `27ed25d` never got one, so if none appears, start it by hand.

**P2 — verify (owner, read-only)**

11. `/health`: the merge commit, `alembic_revision` `0045`, database
    connected.
12. With one dedicated production test account: mobile register, log in,
    add an expense, `GET /api/budget/forecast`, the calendar and the
    dashboard. Then delete the account.
13. Boot logs: no error-level line.

**P3 — the production MCP service (owner, only after P2)**

14. Run `scripts/mcp/mcp_service_role.sql` inside `mita-production-db` over
    SSH: password from a 0600 file, `log_statement = 'none'`. Verify that DDL
    is refused and that the granted tables are readable. 0045 needs no new
    grant.
15. Create service `mita-mcp` (`deploy/mcp/railway.json`, 1 replica, us-east4,
    **source pinned to the reviewed commit**, never auto-deploy, G3-72).
    * Variables, generated into 0600 files and set with `--stdin`:
      `DATABASE_URL` (role `mita_mcp`), `MCP_PUBLIC_URL` (the final origin,
      never `*.up.railway.app`), `MCP_WIDGET_DOMAIN`, `MCP_DATA_SECRET`,
      `MCP_ANALYTICS_SECRET`, the OAuth key and the CSRF and fingerprint
      secrets, `MCP_SUPPORT_URL`, `OPENAI_APPS_CHALLENGE_TOKEN`,
      `ENVIRONMENT=production`.
    * No TCP proxy: the service refuses to start with one.
16. DNS: CNAME to Railway, the custom domain on the service, TLS.
17. Verify:
    * `/health` 200, and only after the grants;
    * protected-resource `resource` = `<origin>/mcp`;
    * `POST /mcp` without a token → 401;
    * an `/authorize` burst → 429.

    Then domain verification in the OpenAI portal.

**Rollback**

0037–0045 only add things, so moving forward never deletes data. Their
reverse does.

* **The boot migration fails.** Transactional DDL leaves the database at 0036,
  and nothing was written. With the healthcheck, the previous deployment keeps
  serving. Without it, redeploy `d4c2547c` (`3aa52b7`), which boots on 0036.
  This is the only routine rollback.
* **The migrations succeeded but the API misbehaves.** Fix forward. Never
  redeploy pre-merge code: it cannot boot on 0045 ("Can't locate revision").
* **`alembic downgrade` is not a rollback.** It is a destructive operation:
  the owner's explicit decision, after the P0.5 backup has been verified,
  and never as a reflex. From 0045 to 0036 it permanently deletes:
  * every ChatGPT connection (OAuth clients, codes, refresh tokens);
  * ChatGPT profiles and setup answers;
  * idempotency records;
  * feedback and usage events (the whole `analytics` schema);
  * users' own budget lines, payment links, spending patterns and regional
    data;
  * which saved payments were made in the app or in ChatGPT, and each kept
    monthly day.

  Expenses, plans and goals live in tables that stay, but a plan saved with
  bill lines or user lines loses what those lines meant. Anything written
  after the dump is lost if the dump is restored instead.
* **Data damaged.** Restore the independently stored P0.5 dump into a fresh
  database and switch to it. That is the owner's decision; writes made after
  the dump are lost.
* **The MCP service misbehaves.** Pin the previous reviewed commit. Every
  schema change stays backward compatible while a published version is
  live.

## State on 2026-10-27 (read-only re-check + compliance audit; supersedes below)

Requirements and their status: `openai-compliance-2026-10-27.md` (current
OpenAI documents re-read; the requirement notes below are partly outdated).

| Fact | Evidence |
|---|---|
| Production unchanged: `mita-production` on `3aa52b7` (deployment `d4c2547c`, 2026-09-29), source `main`, `checkSuites: false`, `bash start.sh`, **no healthcheck**; no MCP service; `mita-production-db` TCP proxy **ACTIVE** | Railway, read-only |
| Staging unchanged: `dbdc118` (2.2.0), no `MCP_WIDGET_DOMAIN` | Railway; `/health` |
| `mitafinance.com`: HTTPS still fails (TLS alert); no `www` / `mcp.` DNS; `/privacy`, `/terms`, `/support` = the landing page over HTTP | `curl`, `dig` |
| API image: **130** advisories in the same 9 directly pinned packages (not 200); MCP lock: 0 | `pip-audit --no-deps` |
| New since 2026-10-26 in OpenAI's docs or found against them: the profile tool's strict schema (fixed), auth declared in `mcp.json` (fixed), `submit_feedback` destructive (fixed), EU data-residency projects cannot submit (O-12b), usage policies effective 2026-11-20 (O-19), one directory with Codex, screenshots optional | compliance doc |

## State on 2026-10-26 (read-only re-check; supersedes the facts below where they differ)

| Fact | Evidence |
|---|---|
| `mita-production` still serves `3aa52b7` (#285, deployed 2026-09-29); `main` HEAD `27ed25d` (#286) is still undeployed; source `main`, `bash start.sh` (runs `alembic upgrade head`; aborts in production if it fails); 1 replica, us-east4; **still no healthcheck** | Railway deployment list and service config |
| `mita-production-db` (Postgres 17): the public TCP proxy `shinkansen.proxy.rlwy.net:12880` → 5432 is **still ACTIVE** | Railway `list-tcp-proxies` |
| Production has **no MCP service** (only `mita-production` and `mita-production-db`) | Railway environment |
| Staging `mita-mcp-staging`: pinned to `dbdc118` (MCP 2.2.0, the v4 sign-in page, the usage box pre-ticked); `0efce5c`, `8f2621d`, R3 and the final connect page are not deployed; no `MCP_WIDGET_DOMAIN`, no `OPENAI_APPS_CHALLENGE_TOKEN` (variable names only); staging Postgres has **no** TCP proxy | Railway; `GET /health` → `"version":"2.2.0"` |
| `https://mitafinance.com`: TLS alert (no certificate for the name); `www` and `mcp.mitafinance.com`: no DNS; HTTP serves the landing page only | `curl`, `openssl s_client`, `dig` |
| API image (`requirements.txt`): `pip-audit` finds 200 known advisories in 9 packages (aiohttp 3.12.14, bleach 6.2.0, cryptography 44.0.1, pillow 11.0.0, pyjwt 2.10.1, python-dotenv 1.0.1, python-multipart 0.0.18, requests 2.32.4, starlette 0.47.2). The MCP image (`requirements-mcp.lock`): none | `pip-audit` |

**Current OpenAI requirements that add to the steps below** (developers.openai.com
`plugins/deploy/submission`, `plugins/reference`, plugin guidelines; checked
2026-10-26): a UI plugin must set a dedicated, unique `_meta.ui.domain`
(MITA: `MCP_WIDGET_DOMAIN`); website, support, privacy policy and terms URLs
are all required (public HTTPS, same publisher); exactly 5 positive and 3
negative test cases; a reviewer-accessible demo video; a dedicated reviewer
account with sample data, no MFA or e-mail codes, kept available; developer
verification; domain verification at `/.well-known/openai-apps-challenge`;
the MCP URL cannot be changed after publication (choose the final hostname
first); every tool sets `readOnlyHint`, `destructiveHint`, `openWorldHint`
(MITA: tested); plugins must suit users aged 13–17 (Step 5).

**Added steps:**

* **6b. `MCP_WIDGET_DOMAIN`** on the production MCP service (`https://mcp.mitafinance.com`
  or another origin MITA owns, unique to this plugin) — and on staging for
  the acceptance run (below). Without it the calendar component is served
  from ChatGPT's shared sandbox origin, which OpenAI does not accept at
  submission.
* **7e. Staging carries the final code before any production step:** deploy
  the commits with R3 and the final connect page to `mita-mcp-staging`
  (MCP 2.3.0), set `MCP_WIDGET_DOMAIN` there, run `scripts/mcp/e2e_http.py`
  and `staging_failure_modes.py`, then the owner's real-ChatGPT run
  (`calendar-owner-test.md`). No migration is needed (still `0039`).
* **7f. API dependency upgrades** (security): raise the nine packages above
  and run the backend suite and mobile CI before the merge that brings
  ChatGPT accounts to production.
* **12b. Release package:** plugin version and release notes to 2.3.0 (bills
  held out of the daily amount); a test case for "Show my financial calendar
  for this month." (the UI is the headline feature; exactly 5 positive cases
  stay); the long description must not promise the MITA app ("…and in the
  MITA app") until the app is released.

## Production as observed today (read-only)

| Fact | Evidence |
|---|---|
| API `mita-production` serving at commit `3aa52b7`, alembic `0036` | `GET /health` → 200; body says `"degraded"`, and the only non-OK component it lists is Sentry (not configured); database, Redis, Firebase OK |
| `main` HEAD `27ed25d` (#286: mobile + CLAUDE.md only) was **never deployed** — Railway has no deployment for it, not even SKIPPED | Railway deployment list; GitHub CI for `27ed25d` passed |
| **`mita-production` has no Railway healthcheck** (staging has `/health`) | service config. Railway: without a healthcheck a deployment becomes Active "after starting the container" and the previous one is stopped |
| Production database is Railway **Postgres 17** `mita-production-db` (us-east4), not Supabase | service image `postgres-ssl:17`; several older docs still say Supabase |
| `mita-production-db` has a **public TCP proxy** `shinkansen.proxy.rlwy.net:12880` → 5432 | service networking; not documented anywhere in the repo |
| Staging MCP runs `fcd7ae3`, healthy | staging-acceptance.md §7 |
| `mitafinance.com`: A `217.160.0.85` (IONOS DNS); HTTPS fails (`tlsv1 alert internal error`); `www` has no DNS record; over HTTP `/`, `/privacy`, `/terms`, `/support` all return the same 605,912-byte landing page | `curl`, `dig` |
| `mita.finance` is not registered (no NS); `mcp.mitafinance.com` has no record | `dig` |

## Dependency order

The given order holds, with three corrections:

1. **Step 5 must be decided before Step 4's Terms are published** — the age
   clause is in the Terms.
2. **Step 7 executes before Step 6 goes live.** The MCP service answers 503
   on `/health` until migrations 0037–0039 are in production, and its source
   is `main` after the merge. Step 6 can be prepared earlier.
3. **Step 9 has no technical dependency — start it now** (verification has
   its own lead time).

```
1 rotate                → 6, 7     configure and deploy with final credentials
2 domain → 3 HTTPS → 4 pages
5 age decision          → 4        before the Terms go live
7a healthcheck → 7b pre-flight → 7c merge (0037–0039 applied) → 6 MCP service
2                       → 6, 8     DNS name; review mailbox
6 + 9                   → 10       domain verification
6 + 8                   → 11       demo video
2, 3, 4, 6, 9, 11       → 12       release package
8, 10, 12               → 13       submission
9                       no dependency: start now
```

## Steps

### 1. Rotate historically exposed credentials
* **Depends on:** nothing. Do before Step 6 so the MCP service is configured
  once, with final credentials.
* **A — done:**
  * Fingerprinted every secret-like value in every committed revision of
    `.env.production` / `.env.production.test` (`bf69fae`, `7d3af83`,
    `0881bf7`), `.mcp.json` (`f83ad16`, `3f0bb68`) and
    `agent_finance_advisor.py` (`2f2c1f1`). Real-looking: S-1…S-4 plus
    `POSTGRES_PASSWORD`/DB-URL password (`4a844b1f918f`) and `APNS_KEY`.
    The older two `.env.production` generations hold placeholders only.
  * `scripts/mcp/check_leaked_secrets.py` compares live variables against all
    33 fingerprints — whole value, URL password and bearer token — and prints
    names only. Against the historical files it flags every S-1…S-4 value;
    clean input exits 0. Tests: `tests_mcp/test_leaked_secret_check.py`,
    including that no value is ever printed.
  * Found the undocumented public TCP proxy on the production database.
* **B:** O-1 Supabase key · O-2 Upstash password · O-3 OpenAI key · O-4 run the
  comparator on `mita-production` and `mita-production-db`, rotate every MATCH ·
  O-4b decide on the TCP proxy.
* **Done when:** the comparator exits 0 for both services; old Supabase key
  refused; old OpenAI key gone; old Upstash password refused; TCP proxy
  removed or its need written down.

### 2. Domain / DNS decision
* **A — done:** DNS state above. Recommendation: `mitafinance.com` (owned) —
  website on the apex and `www`, MCP on `mcp.mitafinance.com`, support mailbox
  on the same domain. `mita.finance` would have to be bought, and
  `build_plugin.py --release` refuses it until then.
* **B:** O-5.
* **Done when:** the domain is chosen and a support mailbox receives mail.

### 3. HTTPS website
* **A — done:** diagnosis. The apex answers HTTP but has no certificate for
  its SNI name (TLS alert); `www` does not resolve.
* **B:** O-8a.
* **Done when:** `curl -sSI https://mitafinance.com/` → 200 with a valid
  certificate; `www` resolves and redirects to the apex.

### 4. Privacy Policy, Terms, Support pages consistent with the code
* **Depends on:** 2, 3, and 5 for the Terms.
* **A — done:** `docs/chatgpt-app/legal/policy-redline.md` — exact
  replacement text for every claim the code does not support (the
  legal-audit items, plus Terms §8 still promising Plaid/Yodlee bank
  connections), the ChatGPT data-flow section, both age-clause variants, and
  the facts only the owner can confirm. `legal/support-page.md` — publishable
  support page. Engineering drafts, not legal advice.
  v2 adds §C (ChatGPT can now write: expenses, plans, obligations, goals,
  feedback) and the usage-statistics consent text; `data-inventory.md` lists
  every stored field with its retention, and marks the periods only the owner
  can set **[OWNER]**.
* **B:** O-8b publish; O-9 legal review; O-17 usage statistics and feedback
  (legal basis, retention periods).
* **Done when:** `/privacy`, `/terms`, `/support` are distinct HTTPS pages
  with the corrected text and a working support address.

### 5. Age requirement: ToS 18+ vs OpenAI's 13–17 rule
* **A — done:** the facts.
  * OpenAI plugin guidelines: "Plugins must be suitable for general
    audiences, including users aged 13–17." "Plugins may not explicitly
    target children under 13." "Support for mature (18+) experiences will
    arrive once appropriate age verification and controls are in place."
  * MITA: ToS §2.1 requires 18+. **Nothing enforces it**: no date of birth is
    collected and no age check exists in the backend or the app.
  * Options:
    * **(a) Lower the minimum age to 13**, with guardian consent below the
      local age of digital consent (14 in Bulgaria; up to 16 elsewhere in the
      EU). No code change; Terms §2.1 and Privacy §6 change; purchases stay
      with the app stores' family controls. Consistent with OpenAI.
    * **(b) Keep 18+ and submit.** The tool content is suitable for teens, but
      the service contract excludes them, which reads as an 18+ experience;
      rejection risk.
    * **(c) Keep 18+ and wait** for OpenAI's age-verified 18+ support.
  * Engineering view: (a) is the only option that is both submittable now
    and true to what the code does. The decision is legal.
* **B:** O-9c.
* **Done when:** Terms §2.1 and Privacy §6 state the decision.

### 6. Production MCP service (prepare now; go live after 7)
* **Depends on:** 1, 2, 7.
* **A — done:** settings mirrored from verified staging (Dockerfile
  `deploy/mcp/Dockerfile`, healthcheck `/health` timeout 60, restart
  ON_FAILURE ×5, **1 replica**, region us-east4 like the API and database);
  variable list (names only); verification commands. Note:
  `mita-production-db` exposes `PG*`/`POSTGRES_*` variables but **no
  `DATABASE_URL`**, so compose it the way `mita-production` does, with the
  least-privilege `mita_mcp` role from `scripts/mcp/mcp_service_role.sql`
  (run in `mita-production-db` after Step 7 — not Supabase). The role was
  verified by the full v2 acceptance conversation: 70 checks, 0 warnings.
  v2 adds `MCP_DATA_SECRET` and `MCP_ANALYTICS_SECRET` (generate_keys.py).
* **B:** O-6, O-7.
* **Done when:** `https://mcp.mitafinance.com/health` → 200; protected-resource
  `resource` = `https://mcp.mitafinance.com/mcp`; `POST /mcp` without a
  token → 401.

### 7. Safe rollout of migrations 0037–0039
* **Depends on:** 1 (one round of restarts first). Gates 6.
* **A — done:**
  * **Merge impact on the API:** migrations 0037–0039; ORM modules
    `app/db/models/mcp_oauth.py` and `mcp_app.py`;
    `app/services/credential_verification.py` (MCP only; the mobile login
    route is identical to `main`). v2 also moves code the API already ran
    into dependency-free modules the MCP image can import, without changing
    behaviour: `FinancialConstants` → `app/core/financial_constants.py`
    (re-exported by `validators`), the password rules →
    `app/core/password_policy.py` (`SecurityUtils` delegates), the e-mail
    pattern → `app/core/email_policy.py` (same regex), `/register`'s user
    construction → `app/services/user_registration.py` (same fields), the
    large-transaction notification import made lazy,
    `commit_transaction_to_ledger` re-expressed through the new
    `add_transactions_to_ledger`, and `monthly_plan_service` gaining
    `allocations_from_profile` / `month_calendar` / `replace_month_plan`
    (the rollover path is unchanged). Backend CI on the branch: 1314 passed.
  * **Rehearsal** (local PostgreSQL 15, scratch database): replay
    0001→0036 in 3 s; 0036→0037 creates 3 tables + 7 indexes; 0038 two
    tables; 0039 four tables, schema `analytics` and 14 views; each was
    rehearsed up → down → up clean.
  * **Locks:** 0037 needs `ShareRowExclusiveLock` on `users` for its foreign
    keys. With a write transaction open on `users` it waited 5.1 s until that
    transaction ended. Reads of `users` were not blocked; writes queue behind
    it while it waits. 0038 and 0039 add four more foreign keys to `users`
    (the same lock, briefly, in the same boot).
  * **Rollback trap (reproduced):** once production is at 0037, any pre-merge
    deployment fails to boot: its `start.sh` runs `alembic upgrade head`
    with code that does not know 0037 → `Can't locate revision identified
    by '0037'` → startup aborts in production.
  * **Healthcheck gap:** with no healthcheck, a failed boot migration leaves
    no serving deployment. `/health` returns 200 even when degraded, so it
    is safe to enable.
* **B:** O-11 → 7a enable the healthcheck (starts a deployment; if it builds
  `main` HEAD `27ed25d`, that also closes the undeployed-commit gap), 7b
  read-only pre-flight SQL, 7c merge at low traffic, 7d verify.
* **Rollback:** fix forward. To return the API to pre-merge code, first run
  `alembic downgrade 0036` from the merged code (drops every table the three
  migrations created: ends every ChatGPT grant and deletes ChatGPT profiles,
  feedback and usage events; expenses, plans and goals live in existing
  tables and stay), then roll back.
* **Done when:** production `/health` shows `alembic_revision` `0039` and
  the merge commit; mobile registration, login and adding an expense work.
* **F-11 adds `0040` (2026-10-28, not merged or deployed):** one new
  MCP-owned table, `mcp_budget_lines`, no change to any existing table (no
  lock on existing data). Production needs its grant to `mita_mcp`
  (`scripts/mcp/mcp_service_role.sql`) before MCP 2.4.0 runs there. Rollback:
  the same trap as 0037 for the API (fix forward, or `alembic downgrade 0039`
  from the new code: drops the table; user lines stay in plans as amounts).

### 8. Production review account
* **Depends on:** 2 (mailbox on an owned domain). Testing it needs 6.
* **A — done:** `review/review-account.md`. Facts: MITA has no MFA; the
  consent page checks only password, lockout (5 failures → 30 min) and
  `is_active`, with no e-mail-verification gate; Google-only accounts cannot
  connect (O-16). v2: the account can be created on the ChatGPT sign-in page
  and filled through ChatGPT; goals need no Premium there; currency EUR to
  match the review prompts.
* **B:** O-10.
* **Done when:** the five positive cases pass in ChatGPT developer mode
  against the production MCP with this account.

### 9. OpenAI organization / developer verification
* **Depends on:** nothing.
* **B:** O-12.
* **Done when:** the platform shows the org verified; the submitter has Owner
  or Apps Management Write.

### 10. OpenAI domain verification
* **Depends on:** 6, 9.
* **A — done:** endpoint `/.well-known/openai-apps-challenge` serves exactly
  `OPENAI_APPS_CHALLENGE_TOKEN` (CI, staging 404 without a token).
* **B:** O-13.

### 11. Demo video
* **Depends on:** 6, 8.
* **A — done:** `review/demo-script.md`.
* **B:** O-14.

### 12. Final plugin release package
* **Depends on:** 2, 3, 4, 6, 9, 11.
* **A — done:** `build_plugin.py --release` refuses placeholders, example hosts
  and `mita.finance`; `--check` green in CI; the listing now states that
  MITA cannot initiate, execute or facilitate payments or money transfers.
  v2 (plugin 2.0.0) packages the onboarding skill and three starter prompts.
* **B:** O-15a.

### 13. OpenAI submission
* **Depends on:** 8, 10, 12.
* **B:** O-15b.

## Exact next owner action

**O-4: run the leaked-secret comparator against production**, then rotate
whatever it flags together with O-1…O-3. Start **O-12** (OpenAI verification)
in parallel. On staging: **S-6/S-7**, the real-ChatGPT acceptance of v2.
