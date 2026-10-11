# Readiness (2026-10-11)

Status categories: **CODE READY** (implemented) · **CI VERIFIED** (GitHub CI)
· **STAGING VERIFIED** (observed on the public staging endpoint) ·
**CHATGPT VERIFIED** (observed in real ChatGPT) · **OWNER REQUIRED** ·
**PRODUCTION NOT DONE**.

Production work follows `docs/chatgpt-app/production-readiness.md` (13 steps,
strict order); owner steps are in `OWNER_ACTIONS.md`.

| Requirement | Status | Evidence | Remaining |
|---|---|---|---|
| Streamable HTTP MCP at `/mcp`, public HTTPS | STAGING VERIFIED, CHATGPT VERIFIED | `https://mita-mcp-staging-staging.up.railway.app/mcp`; staging-acceptance.md §1, §5, §7 | production: PRODUCTION NOT DONE (steps 6–7) |
| **Connected in real ChatGPT developer mode** | **CHATGPT VERIFIED** | OAuth/DCR connection and staging sign-in completed in ChatGPT; staging-acceptance.md §5.1 | — |
| 8 read-only tools, explicit hints, no identity inputs | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_tool_contract.py`; staging "exactly 8 tools", smuggled `user_id`; all 8 exercised in ChatGPT (§5.1) | — |
| OAuth 2.1 (PRM, AS metadata, DCR, PKCE S256, resource binding, rotation, revocation) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (connection) | adversarial suite; staging e2e + 22 failure modes; ChatGPT DCR + consent completed | — |
| AS metadata advertises public clients; exact issuer | STAGING VERIFIED, CHATGPT VERIFIED | fixed in `842d365`; ChatGPT registered and connected against it | — |
| Exact figures; soft deletes; timezone | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | ChatGPT answers matched §3 ground truth to the cent; deleted €999.99 never appeared; status and forecast correct for the actual current date | — |
| Negative cases in ChatGPT (delete, budget change, transfer, other user) | CHATGPT VERIFIED | all refused or empty; control read unchanged (7 / €246.94 / €2,358.00 / €2,111.06), so nothing was written (§5.2) | — |
| Tool metadata: MITA category names kept; "cannot initiate, execute or facilitate payments or money transfers" | CODE READY, CI VERIFIED, STAGING VERIFIED (deployed) | `fcd7ae3`; 4 contract tests + summary/breakdown regression; CI run `38138961278` all jobs success; staging deployment `e060f0b8` | CHATGPT re-check: NOT YET (optional; staging-acceptance.md §7) |
| Grant fingerprint secret separate from CSRF secret | CI VERIFIED, STAGING VERIFIED | `b630d10`, `test_secret_separation.py` | — |
| Cross-user isolation | CI VERIFIED, STAGING VERIFIED (smuggled `user_id`) | `test_isolation.py` | — |
| Logs free of tokens/codes/passwords/amounts/e-mails | CI VERIFIED (container), STAGING VERIFIED (Railway logs) | staging-acceptance.md §4 | — |
| Plugin ZIP (Agent Plugins) | CODE READY, CI VERIFIED (`--check`) | `build_plugin.py`; listing states the money-movement limit (`test_plugin_package.py`) | final ZIP: OWNER REQUIRED (step 12: real URLs, developer name, video) |
| Domain verification endpoint | CODE READY, CI VERIFIED, STAGING VERIFIED (404 without token) | `/.well-known/openai-apps-challenge` | step 10 |
| Leaked credentials rotated | **OWNER REQUIRED** | security-findings S-1…S-4; `scripts/mcp/check_leaked_secrets.py` compares live variables by fingerprint | step 1 (O-1…O-4) |
| Production DB public TCP proxy | **OWNER REQUIRED** (decision) | `mita-production-db` exposes `shinkansen.proxy.rlwy.net:12880` → 5432 (Railway, read-only check 2026-10-11) | step 1 (O-4b) |
| Website / support / privacy / terms over HTTPS | **OWNER REQUIRED** | `https://mitafinance.com` TLS handshake fails; `www` has no DNS record; every path serves the same landing page (HTTP) | steps 2–4 |
| Age policy (13–17 suitability) | **OWNER REQUIRED** (legal) | ToS §2.1 = 18+; OpenAI: "suitable for … users aged 13–17"; 18+ experiences not yet supported | step 5 — decide before the Terms are published |
| Production API healthcheck (safe 0037 rollout) | **OWNER REQUIRED** | `mita-production` has no Railway healthcheck, so a failed boot migration would leave no serving deployment; `/health` returns 200 | step 7a |
| Migration 0037 on production | **PRODUCTION NOT DONE** | production API at `0036` (`/health`, 2026-10-11); 0037 rehearsed locally up → down → up | step 7 (merge) |
| Production MCP service, domain | **PRODUCTION NOT DONE** | only `mita-production` and `mita-production-db` exist in the production project | step 6 (after 7) |
| Review account (production) | **OWNER REQUIRED** | staging fake account exists; production one does not | step 8 |
| OpenAI organization verification | **OWNER REQUIRED** | — | step 9 (no dependency; can start now) |
| Demo video | **OWNER REQUIRED** | `demo-script.md` | step 11 |
