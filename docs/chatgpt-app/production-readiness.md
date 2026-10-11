# Production readiness — MITA ChatGPT app (2026-10-11)

Real ChatGPT staging acceptance is complete (staging-acceptance.md §5).
Production is untouched: no deploy, no variable or setting change, `main` not
merged. **Every production step below needs the owner's explicit
authorization**; owner click-paths and commands are in `OWNER_ACTIONS.md`
under the same step numbers.

**A** = autonomous preparation (done in the repo, no production change).
**B** = owner action (credentials, DNS, legal, billing, verification or
production access).

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
   on `/health` until migration 0037 is in production, and its source is
   `main` after the merge. Step 6 can be prepared earlier.
3. **Step 9 has no technical dependency — start it now** (verification has
   its own lead time).

```
1 rotate                → 6, 7     configure and deploy with final credentials
2 domain → 3 HTTPS → 4 pages
5 age decision          → 4        before the Terms go live
7a healthcheck → 7b pre-flight → 7c merge (0037 applied) → 6 MCP service
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
* **B:** O-8b publish; O-9 legal review.
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
  `DATABASE_URL`**, so copy however `mita-production` composes its
  `DATABASE_URL` (or use the least-privilege role in deployment.md, run in
  `mita-production-db` — not Supabase).
* **B:** O-6, O-7.
* **Done when:** `https://mcp.mitafinance.com/health` → 200; protected-resource
  `resource` = `https://mcp.mitafinance.com/mcp`; `POST /mcp` without a
  token → 401.

### 7. Safe rollout of migration 0037
* **Depends on:** 1 (one round of restarts first). Gates 6.
* **A — done:**
  * **Merge impact on the API:** migration 0037; a new ORM module
    (`app/db/models/mcp_oauth.py`); `app/services/credential_verification.py`,
    which the API does not call (the mobile login route is identical to
    `main`). Nothing else outside the MCP service, tests, docs and CI.
  * **Rehearsal** (local PostgreSQL 15, scratch database): replay
    0001→0036 in 3 s; 0036→0037 creates 3 tables + 7 indexes; 0037→0036 drops
    them; re-upgrade clean.
  * **Locks:** 0037 needs `ShareRowExclusiveLock` on `users` for its foreign
    keys. With a write transaction open on `users` it waited 5.1 s until that
    transaction ended. Reads of `users` were not blocked; writes queue behind
    it while it waits.
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
  `alembic downgrade 0036` from the merged code (drops only the three
  `mcp_oauth_*` tables, i.e. ends every ChatGPT grant), then roll back.
* **Done when:** production `/health` shows `alembic_revision` `0037` and
  the merge commit; mobile login and adding an expense work.

### 8. Production review account
* **Depends on:** 2 (mailbox on an owned domain). Testing it needs 6.
* **A — done:** `review/review-account.md`. Facts: MITA has no MFA; the
  consent page checks only password, lockout (5 failures → 30 min) and
  `is_active`, with no e-mail-verification gate; Google-only accounts cannot
  connect (O-16); goals need Premium.
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
* **B:** O-15a.

### 13. OpenAI submission
* **Depends on:** 8, 10, 12.
* **B:** O-15b.

## Exact next owner action

**O-4: run the leaked-secret comparator against production**, then rotate
whatever it flags together with O-1…O-3. Start **O-12** (OpenAI verification)
in parallel.
