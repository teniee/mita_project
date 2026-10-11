# Owner-only actions

Everything here needs your accounts, credentials, DNS, money, legal judgement
or production access. Ordered by the 13 steps of
`production-readiness.md` (why this order, and what was prepared for each
step). The O-numbers are stable; other documents refer to them.

**Production rule:** nothing in production has been changed. Steps that
deploy, restart or reconfigure production run only when you decide to run
them. Never paste a secret value into chat, an issue or git.

## Staging — COMPLETE

| Item | Status |
|---|---|
| S-1 staging test password | DONE (owner) |
| S-2 ChatGPT developer mode | DONE (owner) |
| S-3 staging app added; OAuth/DCR connected; consent completed | DONE — CHATGPT VERIFIED |
| S-4 acceptance prompts (positive, negative, control read) | DONE — CHATGPT VERIFIED; results in staging-acceptance.md §5 |
| S-5 *(optional)* re-check the `fcd7ae3` metadata | NOT YET — refresh the staging app in ChatGPT developer mode, then ask the two prompts in staging-acceptance.md §7 |

Keep staging running until production is live; teardown is in staging.md.

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
   `MCP_GRANT_FINGERPRINT_SECRET`, `MCP_METRICS_TOKEN`, and new
   `JWT_SECRET`/`SECRET_KEY` that are never the API's). `DATABASE_URL`:
   `mita-production-db` has no `DATABASE_URL` variable, so build it the
   same way `mita-production`'s is built, on the private host — or use the
   least-privilege role in deployment.md (run that SQL in
   `mita-production-db`, not Supabase). Do not set `OPENAI_API_KEY`, SMTP or
   IAP variables.
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

## Step 7 — Migration 0037 (merge)

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
       to_regclass('public.mcp_oauth_refresh_tokens');          -- all NULL
SELECT data_type FROM information_schema.columns
 WHERE table_schema = 'public' AND table_name = 'users' AND column_name = 'id';  -- uuid
SELECT pid, state, now() - xact_start AS open_for
  FROM pg_stat_activity
 WHERE xact_start < now() - interval '30 seconds' AND pid <> pg_backend_pid();  -- no rows
```

**O-11c Review and merge** `feat/chatgpt-plugin` into `main` (PR) at a
low-traffic time. Railway builds the merge commit; `start.sh` applies 0037
(three new tables, a brief `ShareRowExclusiveLock` on `users`); the
healthcheck gates the switch.

**O-11d Verify.** `/health` shows `alembic_revision` `0037` and the merge
commit; the deploy log shows `Running upgrade 0036 -> 0037`; the mobile app
signs in and saves an expense.

**Rollback.** Fix forward. A Railway rollback to a pre-merge deployment
cannot boot against a 0037 database (`Can't locate revision identified by
'0037'`, reproduced). If the old code is really needed: run
`alembic downgrade 0036` from the merged code first (drops only the three
`mcp_oauth_*` tables), then roll back.

## Step 8 — Production review account

**O-10 Create it** exactly as in `review/review-account.md`: a mailbox on the
domain from Step 2, a MITA e-mail/password account (not Google sign-in), the
listed data entered in the app in the current month. Grant Premium so goals
can be created; for a direct grant, in `mita-production-db`:
`UPDATE users SET is_premium = true, premium_until = now() + interval '1 year' WHERE email = '<review e-mail>';`
No MFA or e-mail verification blocks sign-in. Five wrong passwords lock it
for 30 minutes. Check: the five positive cases answer correctly in ChatGPT
developer mode against `https://mcp.mitafinance.com/mcp`.

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

**O-15b** Upload `dist/plugin/mita-finance-1.0.0.zip`; enter the review
credentials in **Review details**; resolve automated findings; attest;
submit.

## Optional

**O-16 Google-only accounts.** They have no MITA password and cannot connect.
Decide whether to add "Sign in with Google" to the consent page (needs a
Google OAuth web client) or a "set password" flow in the app.
