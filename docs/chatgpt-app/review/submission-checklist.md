# Readiness (2026-10-11, v2 update 2026-10-13)

Status categories: **CODE READY** (implemented) · **CI VERIFIED** (GitHub CI)
· **STAGING VERIFIED** (observed on the public staging endpoint) ·
**CHATGPT VERIFIED** (observed in real ChatGPT) · **OWNER REQUIRED** ·
**PRODUCTION NOT DONE**.

Production work follows `docs/chatgpt-app/production-readiness.md` (13 steps,
strict order); owner steps are in `OWNER_ACTIONS.md`. v2 staging evidence:
`staging-acceptance-v2.md` (commit `461abcf`, deployment `174528cf`).

| Requirement | Status | Evidence | Remaining |
|---|---|---|---|
| Streamable HTTP MCP at `/mcp`, public HTTPS | STAGING VERIFIED, CHATGPT VERIFIED (v1) | `https://mita-mcp-staging-staging.up.railway.app/mcp`, `/health` version 2.0.0 | production: PRODUCTION NOT DONE (steps 6–7) |
| Connected in real ChatGPT developer mode | CHATGPT VERIFIED (v1 grant) | staging-acceptance.md §5.1 | v2: reconnect for the write scopes — OWNER REQUIRED (S-6) |
| 22 tools (12 read, 10 write), facts-only hints, no identity inputs, strict arguments | CI VERIFIED, STAGING VERIFIED | `test_tool_contract.py`; staging: exactly 22 tools, smuggled `user_id` rejected (§2, §4) | real ChatGPT: S-7 |
| 8 original read tools unchanged | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | every read tool exercised before and after a restart (§4) | — |
| Account creation in the OAuth flow (shared e-mail/password policy, generic errors, per-IP limit) | CI VERIFIED, STAGING VERIFIED | `test_registration.py`; e2e_v2 sign-up (§2) | real ChatGPT: S-6 |
| Profile, expenses, batch, corrections, retry safety (idempotency) | CI VERIFIED, STAGING VERIFIED | `test_transaction_writes.py` (75), `test_idempotency_concurrency.py` (forced race); retry → `already_recorded` on staging | real ChatGPT: S-7 §6.1 |
| Recurring expenses, savings goals | CI VERIFIED, STAGING VERIFIED | `test_recurring_goal_writes.py` (37); staging rent + goal (§2) | real ChatGPT: S-7 |
| Budget preview → signed draft → save (reviewed == saved) | CI VERIFIED, STAGING VERIFIED | `test_budget_plan.py`; preview saved nothing, saved total == preview, tampered token refused (§2) | real ChatGPT: S-7 |
| Persistence across conversations | STAGING VERIFIED | new DCR client and tokens saw spending, plan and setup (§2) | real ChatGPT: S-7 conversation B |
| Six-month history and financial climate | CI VERIFIED, STAGING VERIFIED | `test_history.py`; 300/320/360/36.80, trend from 3 complete months (§2) | real ChatGPT: S-7 #10 |
| Receipt photo → expenses (ChatGPT vision, no image stored) | CODE READY | `entry_method: receipt_image`; no tool accepts an image | real ChatGPT: S-7 §6.2 with `review/test-receipt.png` |
| Feedback to the team | CI VERIFIED, STAGING VERIFIED | stored with the user's words; analytics only type/area/rating (§2, §3) | real ChatGPT: S-7 §6.3 |
| Product analytics (consented, pseudonymous, allow-listed, out of band) | CI VERIFIED, STAGING VERIFIED | `test_analytics_db.py`; staging audit + report as `mita_analytics_reader`; cascade on deletion (§3) | Metabase hosting: OWNER REQUIRED (O-18); retention: O-17 |
| Least-privilege database role for the MCP service | STAGING VERIFIED | staging runs as `mita_mcp`; 70/70 + 27 + 19 + 24 checks, no permission errors (§1, §5) | production: step 6 |
| OAuth 2.1 (PRM, AS metadata, DCR, PKCE S256, resource binding, rotation, revocation) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (connection) | adversarial suite; staging e2e + 24 failure modes (§4) | — |
| Exact figures; soft deletes; timezone | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | v1: ChatGPT matched ground truth to the cent; v2: exact figures in e2e_v2 | — |
| Negative cases (transfer, other user, trading) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1: transfer, other user) | no money-movement tool; v1 control read unchanged | v2 incl. Bitcoin: S-7 §6.4 |
| Onboarding skill, starter prompts, listing (plugin 2.0.0) | CODE READY, CI VERIFIED (`--check`) | `build_plugin.py`, `test_plugin_package.py`, 56 golden prompts (en/ru/bg) | final ZIP: OWNER REQUIRED (step 12) |
| Capacity (600k transactions) | VERIFIED locally | capacity-plan.md: p95 ≤ 20 ms per tool query, no new index | — |
| Grant fingerprint secret separate from CSRF secret | CI VERIFIED, STAGING VERIFIED | `test_secret_separation.py` | — |
| Cross-user isolation | CI VERIFIED, STAGING VERIFIED | `test_isolation.py`; forged ref refused on staging | — |
| Logs free of tokens/codes/passwords/amounts/e-mails | CI VERIFIED (container), STAGING VERIFIED | 235 entries scanned, 0 hits (§5) | — |
| Domain verification endpoint | CODE READY, CI VERIFIED, STAGING VERIFIED (404 without token) | `/.well-known/openai-apps-challenge` | step 10 |
| Leaked credentials rotated (OpenAI key, Supabase, Upstash) | **OWNER REQUIRED** | security-findings S-1…S-4; `scripts/mcp/check_leaked_secrets.py` | step 1 (O-1…O-4) |
| Production DB public TCP proxy | **OWNER REQUIRED** (decision) | `mita-production-db` exposes `shinkansen.proxy.rlwy.net:12880` → 5432 | step 1 (O-4b) |
| Website / support / privacy / terms over HTTPS | **OWNER REQUIRED** | `https://mitafinance.com` TLS handshake fails; `www` has no DNS record; every path serves the same landing page | steps 2–4 |
| Usage statistics and feedback: legal basis, retention | **OWNER REQUIRED** (legal) | data-inventory.md **[OWNER]** cells; policy-redline.md §C | O-17 |
| Age policy (13–17 suitability) | **OWNER REQUIRED** (legal) | ToS §2.1 = 18+; OpenAI: "suitable for … users aged 13–17" | step 5 |
| Production API healthcheck (safe migration rollout) | **OWNER REQUIRED** | `mita-production` has no Railway healthcheck | step 7a |
| Migrations 0037–0039 on production | **PRODUCTION NOT DONE** | production at `0036`; staging at `0039`; each rehearsed up → down → up | step 7 (merge) |
| Production MCP service, domain | **PRODUCTION NOT DONE** | only `mita-production` and `mita-production-db` exist in the production project | step 6 (after 7) |
| Review account (production, EUR, data entered through ChatGPT) | **OWNER REQUIRED** | review-account.md | step 8 |
| OpenAI organization verification | **OWNER REQUIRED** | — | step 9 (can start now) |
| Demo video | **OWNER REQUIRED** | demo-script.md | step 11 |
| Public review | **OWNER REQUIRED** | — | step 13 |
