# Owner-only actions

Everything here needs your accounts, money, legal judgement or DNS. Ordered
by dependency. Code side is done on `feat/chatgpt-plugin`.

## Security (do first — independent of ChatGPT)

**O-1 Rotate the leaked Supabase secret key.** Supabase dashboard → project
`atdcxppfflmiwjwjuqyl` → Project Settings → API Keys → secret key with
fingerprint `825ad855969b` (see security-findings S-1) → revoke/rotate. Update
any place using it (local `.mcp.json` for your IDE). Check: the old key returns
401 against the Supabase MCP endpoint.

**O-2 Rotate the Upstash Redis password** for `integral-jaybird-23463.upstash.io`
(fingerprint `9b824f818673`). Upstash console → database → Reset password.
Update every Railway variable embedding it (`REDIS_URL` / `UPSTASH_REDIS_URL`)
on `mita-production`. Check: API `/health` shows Redis healthy.

**O-3 Revoke the OpenAI key committed in 2025** (`sk-proj…`, fingerprint
`86d0921d9661`): platform.openai.com → API keys → delete it if it still exists.

**O-4 Compare production secrets with the ones committed in `.env.production`**
(security-findings S-4). On your machine:
`printf '%s' "$VALUE" | shasum -a 256 | cut -c1-12` for `JWT_SECRET`,
`JWT_PREVIOUS_SECRET`, `SECRET_KEY`, `REDIS_PASSWORD`, `DATABASE_URL`,
`OPENAI_API_KEY` in Railway → `mita-production` → Variables. Rotate any match.
Rotating `JWT_SECRET` signs every mobile user out (expected).

## Domain, website, legal

**O-5 Decide the public domain.** `mita.finance` is not registered. Either use
`mitafinance.com` (owned, IONOS) — recommended — or buy `mita.finance`. All docs
assume `mcp.mitafinance.com`.

**O-6 Create the MCP service on Railway.** Railway → project "Mita Finance" →
environment production → New → GitHub Repo `teniee/mita_project`, branch
`main` (after merge) → name `mita-mcp` → Settings → Config-as-code / "Railway
config file" = `deploy/mcp/railway.json`. Variables: run
`python scripts/mcp/generate_keys.py` locally and paste each line; add
`ENVIRONMENT=production`, `DATABASE_URL` (reference `mita-production`'s, or the
least-privilege role in deployment.md), `MCP_PUBLIC_URL=https://mcp.mitafinance.com`,
`MCP_SUPPORT_URL`. Deploy. Check: deployment log shows Uvicorn running;
`/health` is 200 once migration 0037 is on production.

**O-7 DNS for the MCP host.** Railway → `mita-mcp` → Settings → Networking →
Custom Domain → `mcp.mitafinance.com` → Railway shows a CNAME target. IONOS →
mitafinance.com → DNS → add **CNAME** `mcp` → that target (and the TXT record
if Railway asks for verification). Check:
`dig +short CNAME mcp.mitafinance.com` returns the target and
`curl -s https://mcp.mitafinance.com/health` returns `{"status":"ok",...}`.

**O-8 Fix HTTPS and publish real pages on the website.** `https://mitafinance.com`
currently fails TLS and every path serves the landing page. IONOS → SSL
certificate for `mitafinance.com` and `www` (or move hosting). Publish distinct
pages: `/privacy`, `/terms`, `/support` (with a working support e-mail). Check:
`curl -sI https://mitafinance.com/privacy` → 200 and the page is the policy.

**O-9 Legal decisions** (legal-audit.md): (a) remove/correct the unsupported
claims (Plaid/Yodlee, Google Analytics, SOC 2/ISO/PCI, pen-testing, TLS 1.3,
retention); (b) replace `@mita.finance` addresses; (c) resolve the 18+ age
requirement vs OpenAI's 13–17 suitability rule; (d) add the ChatGPT data-flow
section (draft provided). Publish before submitting.

## Review account

**O-10 Create the production review account** exactly as in
`review/review-account.md` (dedicated mailbox, MITA e-mail/password, data
entered in the app). Grant it Premium so goals can be created — decide the
mechanism (complimentary entitlement). If you choose a direct DB grant,
run in Supabase SQL:
`UPDATE users SET is_premium = true, premium_until = now() + interval '1 year' WHERE email = '<review e-mail>';`
Check: in ChatGPT developer mode the five positive cases answer as described.

## Merge and release

**O-11 Review and merge** `feat/chatgpt-plugin` into `main` (PR). Merging
deploys the API with migration 0037 (additive). The mobile auth code is
unchanged.

## OpenAI

**O-12 Verify identity/organization.** platform.openai.com → Settings →
Organization → Verification (individual or business "YAKOVLEV LTD"). The
submitter needs Owner or "Apps Management Write".

**O-13 Domain verification.** In the Plugins dashboard, start the MCP domain
check; copy the token into `mita-mcp` variable `OPENAI_APPS_CHALLENGE_TOKEN`;
redeploy. Check: `curl -s https://mcp.mitafinance.com/.well-known/openai-apps-challenge`
prints exactly the token, nothing else.

**O-14 Record the demo video** (`review/demo-script.md`), upload unlisted.

**O-15 Build and upload the ZIP.**
```bash
MCP_PUBLIC_URL=https://mcp.mitafinance.com WEBSITE_URL=https://mitafinance.com \
SUPPORT_URL=https://mitafinance.com/support PRIVACY_URL=https://mitafinance.com/privacy \
TERMS_URL=https://mitafinance.com/terms SUPPORT_EMAIL=<working address> \
DEVELOPER_NAME="<verified org name>" CATEGORY="<dashboard category, e.g. Finance>" \
DEMO_RECORDING_URL=<video URL> python scripts/mcp/build_plugin.py --release
```
Upload `dist/plugin/mita-finance-1.0.0.zip`; enter review credentials in
**Review details**; resolve automated findings; attest; submit.

**O-16 (optional) Google-only accounts.** Users who signed up with Google have
no MITA password and cannot connect. Decide whether to add "Sign in with
Google" to the consent page (needs a Google OAuth web client) or a
"set password" flow in the app.
