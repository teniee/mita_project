# Owner-only actions

Everything here needs your accounts, credentials, DNS, money, legal judgement
or production access. Ordered by the 13 steps of
`production-readiness.md` (why this order, and what was prepared for each
step). The O-numbers are stable; other documents refer to them.

**Production rule:** nothing in production has been changed. Steps that
deploy, restart or reconfigure production run only when you decide to run
them. Never paste a secret value into chat, an issue or git.

## Staging

v1 (8 read-only tools) — complete:

| Item | Status |
|---|---|
| S-1 staging test password | DONE (owner) |
| S-2 ChatGPT developer mode | DONE (owner) |
| S-3 staging app added; OAuth/DCR connected; consent completed | DONE — CHATGPT VERIFIED |
| S-4 acceptance prompts (positive, negative, control read) | DONE — CHATGPT VERIFIED; results in staging-acceptance.md §5 |
| S-5 *(optional)* re-check the `fcd7ae3` metadata | SUPERSEDED by S-7 (v2 replaces that build) |

v2 (free v1 read/write, 22 tools) — public automated acceptance and the real
ChatGPT results are in `staging-acceptance-v2.md` (§2–§5, §8):

| Item | Status |
|---|---|
| S-6 reconnect MITA staging in ChatGPT developer mode | DONE — CHATGPT VERIFIED (2026-10-18): plugin object recreated with DCR, all five scopes discovered, writes work |
| S-7 real-ChatGPT acceptance v2 | DONE — CHATGPT VERIFIED (§8); the cases it left open were completed in S-8 |
| S-8 final real-ChatGPT smoke test of MCP 2.1.0 | DONE — CHATGPT VERIFIED / STAGING VERIFIED (2026-10-19, `staging-acceptance-v2.md` §11): B, C, D, E, H, I, J, two real receipts and a repeated receipt with no duplicate; the opt-out verified in the database. **Staging acceptance is closed.** The synthetic `test-receipt.png` was not owner-run (repository coverage only). The ChatGPT app object's own Description field is owner-managed and moves to the listing/onboarding phase |

MCP 2.2.0 (24 tools, the financial calendar component, sign-in page v4):

| Item | Status |
|---|---|
| S-9 refresh the MITA staging app in ChatGPT developer mode (the tool list gains `get_calendar_month` and `show_financial_calendar`; no new scope, no reconnect needed unless ChatGPT asks) | OWNER REQUIRED — `calendar-owner-test.md` step A |
| S-10 review the sign-in page v4 and the calendar in real ChatGPT (phone and desktop; fullscreen; Save as PNG) | OWNER REQUIRED — `calendar-owner-test.md` |

Staging acceptance (v2) is closed; production is untouched. Keep staging
running until production is live; teardown is in staging.md.

## Step 1 — Rotate historically exposed credentials

The repository is public; every committed value is disclosed
(security-findings.md).

**O-4 Find which live variables still hold committed values (do this
first).** In a terminal where the Railway CLI is logged in:
```bash
cd ~/mita_project
for s in mita-production mita-production-db; do
  railway variable list --project d44d0580-3476-4e46-bc4c-b2d95dac64cd \
    --environment production --service "$s" --json \
  | python3 scripts/mcp/check_leaked_secrets.py --source "$s"
done
```
It prints variable names and the committed item each one equals — never a
value. Exit 0 = nothing in use. Also check your IDE configs the same way
(`python3 scripts/mcp/check_leaked_secrets.py --source ide < ~/.claude.json`,
and any `.mcp.json`). Rotate every **[secret]** MATCH at its provider, then
update the Railway variable (each change restarts the service — your call
when). Rotating `JWT_SECRET` signs every mobile user out; rotating the
database password needs the new value in `mita-production`'s
`DATABASE_URL` in the same change.

**O-1 Rotate the Supabase secret key** (fingerprint `825ad855969b`):
Supabase → project `atdcxppfflmiwjwjuqyl` → Project Settings → API Keys →
revoke/rotate. Production now runs on Railway Postgres; if this Supabase
project still holds user data, decide whether to export and delete it.
Check: the old key gets 401.

**O-2 Rotate the Upstash Redis password** for `integral-jaybird-23463.upstash.io`
(fingerprint `9b824f818673`): Upstash console → database → Reset password.
Update every `mita-production` variable that embeds it (`REDIS_URL`,
`UPSTASH_REDIS_URL`, and `UPSTASH_REDIS_REST_TOKEN` if it changes). Check:
`/health` shows `"redis":"connected"`; O-4 reports no MATCH.

**O-3 Revoke the OpenAI key committed in 2025** (fingerprint
`86d0921d9661`): platform.openai.com → API keys → delete it if it still
exists.

**O-4b Decide on the production database's public TCP proxy**
(`shinkansen.proxy.rlwy.net:12880` → `mita-production-db`:5432). It exposes
the production database to the internet behind a password. The API should
not need it: docs/owner-dependencies-checklist.md records its `DATABASE_URL`
host as `mita-production-db.railway.internal` (private). Confirm that in
`mita-production` → Variables → `DATABASE_URL` first — if it uses the proxy
host, removing the proxy would take the API down. Then `mita-production-db`
→ Settings → Networking → remove the TCP proxy, unless you need it — then
write down why.

## Step 2 — Domain

**O-5 Choose the public domain.** `mita.finance` is not registered.
Recommended: `mitafinance.com` (owned, IONOS) with `mitafinance.com` + `www`
for the website, `mcp.mitafinance.com` for the MCP service and a support
mailbox on the same domain (IONOS mail or another provider). Check: a test
e-mail to the support address arrives.

## Step 3 — HTTPS website

**O-8a Fix TLS.** Today the apex fails the TLS handshake and `www` has no
DNS record. IONOS → Domains & SSL → `mitafinance.com` → assign an SSL
certificate covering the apex and `www`; add a `www` record (CNAME to the
apex or the hosting target). Or move the single-page site (branch
`website`) to a host with automatic TLS. Check:
`curl -sSI https://mitafinance.com/` → 200 with a valid certificate and
`curl -sSI https://www.mitafinance.com/` → 200 or 301 to the apex.

## Step 4 — Privacy Policy, Terms, Support pages

**O-9 (a, b, d) Legal review** of `legal/policy-redline.md`: confirm or
correct every **[CONFIRM]** fact, approve the replacements and the ChatGPT
section, replace the `@mita.finance` addresses. Wait for Step 5 before
publishing the Terms.

**O-8b Publish** three distinct pages: `/privacy`, `/terms` and `/support`
(`legal/support-page.md`). Check: each URL returns 200 over HTTPS with its
own content (today every path returns the landing page).

**O-17 Usage statistics and feedback (decide before O-8b).** v2 stores
feedback the user asks to send (`product_feedback`) and, only for users who
tick the box on the sign-in page, pseudonymous usage events
(`analytics.events`; `data-inventory.md`, `product-analytics.md`). Decide
and write into the Privacy Policy (`legal/policy-redline.md` §C):
(a) the legal basis (the code treats usage statistics as consent: off for an
account that never answered, switchable in ChatGPT, turning it off deletes the
linked events — but the box on the sign-in page is **pre-ticked**, so everyone
who connects through ChatGPT is opted in unless they untick it; a pre-ticked
box is not valid consent under the GDPR, CJEU C-673/17 *Planet49*. If consent
is the basis, the box should start unticked: a one-line default in
`login.py`/`pages.py`, not changed without you because it changes the sign-in
page's behaviour);
(b) how long feedback and linked events are kept while the account exists —
nothing is purged automatically today, every **[OWNER]** cell in
`data-inventory.md`; (c) who at MITA may read feedback text. Tell me the
periods and I will add the purge job.

## Step 5 — Age requirement

**O-9c Decide** between 13+ (variant a), keeping 18+ and submitting anyway,
or keeping 18+ and waiting for OpenAI's age-verified 18+ support
(production-readiness Step 5; texts in `legal/policy-redline.md` §D). Nothing
in the app enforces an age today.

## Step 6 — Production MCP service (after Step 7)

**O-6 Create `mita-mcp`.**
1. Locally: `python scripts/mcp/generate_keys.py` — paste each line into the
   service's variables. Never commit it.
2. Railway → project **Mita Finance** → environment **production** → New →
   GitHub repo `teniee/mita_project`, branch `main` → name `mita-mcp`.
3. Settings, mirroring staging: builder Dockerfile, path
   `deploy/mcp/Dockerfile`; healthcheck `/health`, timeout 60; restart on
   failure, 5 retries; **1 replica** (rate limits are per replica); region
   us-east4 (same as the API and the database).
4. Variables: `ENVIRONMENT=production`, `MCP_PUBLIC_URL=https://mcp.mitafinance.com`,
   `MCP_AUTH_MODE=builtin`, `MCP_SUPPORT_URL=https://mitafinance.com/support`,
   `LOG_LEVEL=INFO`, `MCP_TRUSTED_PROXY_HOPS=1`, `PORT=8080`, the
   `generate_keys.py` values (`MCP_OAUTH_PRIVATE_KEY`, `MCP_LOGIN_CSRF_SECRET`,
   `MCP_GRANT_FINGERPRINT_SECRET`, `MCP_DATA_SECRET`, `MCP_ANALYTICS_SECRET`,
   `MCP_METRICS_TOKEN`, and new `JWT_SECRET`/`SECRET_KEY` that are never the
   API's). Never reuse a staging value. `MCP_ANALYTICS_SECRET` must then stay
   unchanged (rotating it splits every user's usage history).
   `MCP_WIDGET_DOMAIN`: the dedicated origin OpenAI requires for an app
   with UI (`_meta.ui.domain` on the calendar component; unique to MITA —
   e.g. `https://mcp.mitafinance.com`, as OpenAI's submission form asks).
   `DATABASE_URL`: use the least-privilege role — after Step 7, run
   `scripts/mcp/mcp_service_role.sql` as the database owner in
   `mita-production-db` (not Supabase; command in deployment.md) and build
   the URL with user `mita_mcp` on the private host, the way
   `mita-production`'s is built (`mita-production-db` has no `DATABASE_URL`
   variable). Do not set `OPENAI_API_KEY`, SMTP or IAP variables.
5. Deploy. Check: deploy log shows Uvicorn on 8080; `/health` → 200.

**O-7 DNS.** `mita-mcp` → Settings → Networking → Custom domain
`mcp.mitafinance.com` (port 8080) → add the CNAME (and TXT, if Railway asks)
at IONOS. Check:
```bash
H=https://mcp.mitafinance.com
curl -s $H/health                                    # {"status":"ok",...}
curl -s $H/.well-known/oauth-protected-resource/mcp  # resource = $H/mcp
curl -s -o /dev/null -w '%{http_code}\n' -X POST $H/mcp \
  -H 'content-type: application/json' -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'  # 401
```

## Step 7 — Migrations 0037–0039 (merge)

**O-11a Give `mita-production` a healthcheck first.** Settings → Deploy →
Healthcheck path `/health`, timeout 300 → apply/deploy. Without it, a failed
boot migration leaves no serving deployment. Applying starts a new
deployment; note which commit it builds — if it is `main` HEAD `27ed25d`
(mobile + docs only, never deployed so far), that also closes that gap.
Check: the deployment shows the healthcheck passing; `/health` still reports
`alembic_revision` `0036`.

**O-11b Pre-flight (read-only).** In `mita-production-db` (Data tab or
`railway connect`):
```sql
SELECT version_num FROM alembic_version;                       -- 0036
SELECT to_regclass('public.mcp_oauth_clients'),
       to_regclass('public.mcp_oauth_authorization_codes'),
       to_regclass('public.mcp_oauth_refresh_tokens'),
       to_regclass('public.mcp_user_profiles'),
       to_regclass('public.mcp_idempotency_keys'),
       to_regclass('public.product_feedback'),
       to_regclass('public.analytics_identities');              -- all NULL
SELECT count(*) FROM pg_namespace WHERE nspname = 'analytics';  -- 0
SELECT data_type FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'id';  -- uuid
SELECT pid, state, now() - xact_start AS open_for
  FROM pg_stat_activity
 WHERE xact_start < now() - interval '30 seconds' AND pid <> pg_backend_pid();  -- no rows
```

**O-11c Review and merge** `feat/chatgpt-plugin` into `main` (PR) at a
low-traffic time. Railway builds the merge commit; `start.sh` applies 0037,
0038 and 0039 in one run (nine tables, schema `analytics` with 14 views;
each new foreign key takes a brief `ShareRowExclusiveLock` on `users`); the
healthcheck gates the switch. The API code in the merge changes only by
behaviour-preserving extractions (`production-readiness.md` Step 7).

**O-11d Verify.** `/health` shows `alembic_revision` `0039` and the merge
commit; the deploy log shows `Running upgrade 0036 -> 0037`, `0037 -> 0038`,
`0038 -> 0039`; the mobile app registers a new account, signs in and saves an
expense.

**Rollback.** Fix forward. A Railway rollback to a pre-merge deployment
cannot boot against a migrated database (`Can't locate revision identified
by '0037'`, reproduced). If the old code is really needed: run
`alembic downgrade 0036` from the merged code first — it drops every table
these migrations created, so it ends every ChatGPT grant and deletes
ChatGPT profiles, feedback and usage events (expenses, plans and goals stay
in the existing tables) — then roll back.

## Step 8 — Production review account

**O-10 Create it** exactly as in `review/review-account.md`: a mailbox on the
domain from Step 2, a MITA e-mail/password account (not Google sign-in),
currency EUR, the listed data entered through ChatGPT developer mode against
`https://mcp.mitafinance.com/mcp` in the current month. No Premium grant is
needed any more (goals are free in ChatGPT). No MFA or e-mail verification
blocks sign-in. Five wrong passwords lock it for 30 minutes. Check: the five
positive cases (`review/positive-test-cases.md`) answer correctly.

## Step 9 — OpenAI verification (start now)

**O-12** platform.openai.com → Settings → Organization → Verification
(individual, or business "YAKOVLEV LTD"). The submitter needs Owner or Apps
Management Write.

## Step 10 — OpenAI domain verification

**O-13** In the Plugins dashboard, start the MCP domain check; set the token
as `OPENAI_APPS_CHALLENGE_TOKEN` on `mita-mcp`; redeploy. Check:
`curl -s https://mcp.mitafinance.com/.well-known/openai-apps-challenge`
prints exactly the token.

## Step 11 — Demo video

**O-14** Record `review/demo-script.md` against production with the review
account; upload unlisted.

## Step 12 — Release package

**O-15a**
```bash
MCP_PUBLIC_URL=https://mcp.mitafinance.com WEBSITE_URL=https://mitafinance.com \
SUPPORT_URL=https://mitafinance.com/support PRIVACY_URL=https://mitafinance.com/privacy \
TERMS_URL=https://mitafinance.com/terms SUPPORT_EMAIL=<working address> \
DEVELOPER_NAME="<verified org name>" CATEGORY="<dashboard category, e.g. Finance>" \
DEMO_RECORDING_URL=<video URL> python scripts/mcp/build_plugin.py --release
```

## Step 13 — Submit

**O-15b** Upload `dist/plugin/mita-finance-2.0.0.zip`; enter the review
credentials in **Review details**; resolve automated findings; attest;
submit.

## Optional

**O-16 Google-only accounts.** They have no MITA password and cannot connect.
Decide whether to add "Sign in with Google" to the consent page (needs a
Google OAuth web client) or a "set password" flow in the app.

**O-18 Metabase (when you want dashboards).** `product-analytics.md` lists the
questions and the views behind them; until then
`scripts/mcp/analytics_report.py` prints the same report. Hosting Metabase is
a billing decision (Metabase Cloud, or a Railway service in the production
project). Connect it ONLY with `mita_analytics_reader`
(`scripts/mcp/analytics_reader_role.sql`), never the owner or `mita_mcp`
role, and do not expose it publicly without its own sign-in.
