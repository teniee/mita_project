# Readiness (2026-10-03)

Status categories: **CODE READY** (implemented) · **CI VERIFIED** (GitHub CI)
· **STAGING VERIFIED** (observed on the public staging endpoint) ·
**CHATGPT VERIFIED** (observed in real ChatGPT) · **OWNER REQUIRED** ·
**PRODUCTION NOT DONE**.

| Requirement | Status | Evidence | Remaining |
|---|---|---|---|
| Streamable HTTP MCP at `/mcp`, public HTTPS | STAGING VERIFIED | `https://mita-mcp-staging-staging.up.railway.app/mcp`; staging-acceptance.md §1 | production: PRODUCTION NOT DONE |
| 8 read-only tools, explicit hints, no identity inputs | CI VERIFIED, STAGING VERIFIED | `test_tool_contract.py`; staging failure-modes "exactly 8 tools", smuggled `user_id` | CHATGPT: NOT YET |
| OAuth 2.1 (PRM, AS metadata, DCR, PKCE S256, resource binding, rotation, revocation) | CI VERIFIED, STAGING VERIFIED | adversarial suite; staging e2e + failure modes (restart, replay, scope, password change) | CHATGPT: NOT YET |
| AS metadata advertises public clients; exact issuer | STAGING VERIFIED | fixed in `842d365` after first staging deploy | — |
| Grant fingerprint secret separate from CSRF secret | CI VERIFIED, STAGING VERIFIED (deployed) | `b630d10`, `test_secret_separation.py` | — |
| Cross-user isolation | CI VERIFIED | `test_isolation.py` (51) | — |
| Exact figures; soft deletes; timezone | CI VERIFIED, STAGING VERIFIED | staging ground truth (§3), deleted 999.99 absent | CHATGPT: compare answers |
| Logs free of tokens/codes/passwords/amounts/e-mails | CI VERIFIED (container), STAGING VERIFIED (Railway logs) | staging-acceptance.md §4 | — |
| Connected in real ChatGPT developer mode | **NOT YET — OWNER REQUIRED** | — | OWNER_ACTIONS S-1…S-4 |
| Plugin ZIP (Agent Plugins) | CODE READY, CI VERIFIED (`--check`) | `build_plugin.py` | final ZIP: OWNER REQUIRED (real URLs, video) |
| Domain verification endpoint | CODE READY, CI VERIFIED | returns 404 on staging until a token is set | O-13 |
| Website / support / privacy / terms over HTTPS | **OWNER REQUIRED** | `https://mitafinance.com` TLS failure | O-8, O-9 |
| Age policy (13–17 suitability) | **OWNER REQUIRED** | ToS §2.1 = 18+ | O-9(c) |
| Review account (production) | **OWNER REQUIRED** | staging fake account exists; production one does not | O-10 |
| Demo video | **OWNER REQUIRED** | demo-script.md | O-14 |
| Leaked credentials rotated | **OWNER REQUIRED** | security-findings S-1…S-4 | O-1…O-4 |
| Production MCP service, domain, migration 0037 on production | **PRODUCTION NOT DONE** | production API is at 0036 (`/health`) | O-5…O-7, O-11 (merge) |
