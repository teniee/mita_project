# Staging acceptance — observed results

Target: `https://mita-mcp-staging-staging.up.railway.app` (commit `842d365`),
fake account `staging-review@example.test`. No credentials or tokens are
recorded here.

Status legend: **STAGING VERIFIED** = observed against the public staging
endpoint by scripted HTTP/MCP clients. **CHATGPT VERIFIED** = observed inside
real ChatGPT. **NOT YET** = not observed.

## 1. Public endpoints (STAGING VERIFIED, 2026-10-03)

| Endpoint | Observed |
|---|---|
| `GET /health` | 200 `{"status":"ok"}` |
| `GET /.well-known/oauth-protected-resource/mcp` (and root path) | 200; `resource` = `https://mita-mcp-staging-staging.up.railway.app/mcp`; scopes `profile:read finance:read` |
| `GET /.well-known/oauth-authorization-server` | 200; issuer exactly the origin; S256 only; auth methods `none, client_secret_post, client_secret_basic`; no localhost/example/placeholder/production host |
| `GET /.well-known/jwks.json` | 200; one RS256 key, no private parameters |
| `POST /mcp` without token | 401 + `WWW-Authenticate: Bearer … resource_metadata="…/.well-known/oauth-protected-resource/mcp"` |
| `GET /authorize` (no params) | 400 |
| `POST /token` (no client) | 401 |
| `POST /register` foreign redirect | 400 |
| `GET /.well-known/openai-apps-challenge` | 404 (no token configured — expected) |
| `GET /metrics` without bearer | 401 |

## 2. OAuth over public HTTPS (STAGING VERIFIED)

`scripts/mcp/e2e_http.py`, temporary fake user, all checks PASS:
DCR (ChatGPT redirect) 201; foreign redirect 400; `/authorize` → consent page
302; consent → code at the registered redirect; `state` round-trips; PKCE
exchange 200; code replay 400; `tools/list` = the 8 tools; all 8 tools
succeed; exact ledger figure; **service restart** (Railway restart) →
health 200; refresh token survives restart 200; rotated refresh token 400;
all 8 tools succeed again; **password change → live access token refused
(`auth`) and refresh token 400**.

`scripts/mcp/staging_failure_modes.py`, 22/22 PASS: invalid bearer 401;
3 malicious redirects 400; unregistered redirect at `/authorize` 400 with no
redirect; no PKCE → never reaches consent; wrong password → generic message,
no code; bogus code 400 `invalid_grant`; wrong verifier 400; code replay 400;
refresh widening scope 400 `invalid_scope`; refresh rotation 200; replayed
refresh 400 and family revoked; profile-only token: `get_profile` ok,
`list_transactions` `forbidden`; smuggled `user_id` cannot change identity;
malformed tool argument → error; exactly 8 tools; `/authorize` rate limit
engaged (429 after 30/min).

Not exercised on staging (covered by CI/local tests only): expired access
token (15 min wait), database outage (would need stopping the staging
database; covered by `test_database_outage_is_unavailable_not_empty`).

## 3. Tool ground truth for the fake account (STAGING VERIFIED via SDK client)

Values returned over public HTTPS on 2026-10-03 (Europe/Sofia, October 2026):

| Tool | Exact result |
|---|---|
| `get_profile` | name "Staging Review", nickname `st***@example.test`, EUR, Europe/Sofia, onboarded; id `prf_2597…` |
| `get_financial_summary` | stated income 4200.00; plan generated; planned 2358.00; spent 246.94; remaining 2111.06; 7 transactions; days elapsed 3; top: groceries 114.40, dining 78.55, transportation 38.00 |
| `list_transactions` | 7 items, total 246.94 (merchant names are prefixed "Staging "): 10-03 dining 6.20 Corner Cafe; 10-03 groceries 18.40 Fresh Market; 10-02 groceries 54.90; 10-02 subscriptions 15.99 StreamFlix; 10-01 dining 72.35 Bistro 21; 10-01 groceries 41.10 Green Grocer; 10-01 transportation 38.00 City Transit |
| `get_spending_breakdown` | total 246.94: groceries 114.40 (46.3 %), dining 78.55 (31.8 %), transportation 38.00 (15.4 %), subscriptions 15.99 (6.5 %) |
| `get_budget_status` | planned 2358.00, spent 246.94, remaining 2111.06; today 10-03 planned 174.91, spent 24.60, remaining 150.31; no over-budget or unplanned categories (MITA's rebalancer credited the spent categories — see backend-findings F-2) |
| `get_budget_forecast` | status `warning`; elapsed 3, remaining 28; pace 82.31/day; safe 75.40/day; projected month-end balance −193.62; at risk: dining 10.35×, transportation 10.30×, subscriptions 10.25×, groceries 2.87× |
| `get_recurring_expenses` | rent 1100.00 monthly due 2026-11-01; insurance once due 2026-10-23; StreamFlix 15.99 marked recurring; `inferred` [] |
| `get_goals` | "Staging emergency fund" 900/3000 (30.0 %), on track (monthly contribution basis), required 266.50/month |

The soft-deleted 999.99 "DELETED" purchase appears in no tool output.
Figures change as days pass (days elapsed, pace, today's budget).

## 4. Logs (STAGING VERIFIED)

Railway deploy + HTTP logs after all flows: 0 e2e secrets (codes, verifiers,
access/refresh tokens, passwords, e-mails), 0 JWT-shaped strings, no staging
password, no amounts, no `code=`, no cookie values. Structured events
present: `http_request`, `tool_call` (8 tools `ok`, `auth` after password
change, `forbidden` for profile-only token), `oauth_login_failed`
(`invalid_password`), `oauth_register_rejected`, `oauth_client_registered`,
`oauth_code_issued`, `oauth_refresh_reuse`. HTTP log statuses included 401,
400 and 429 as expected.

## 5. Real ChatGPT — NOT YET VERIFIED

Not performed: the Claude-in-Chrome extension was not connected, and typing a
staging password into a non-local sign-in page is left to the owner. Steps:
OWNER_ACTIONS.md → "S-1 … S-4". Record the observations below when done.

| Check | Result |
|---|---|
| Developer-mode app created with `…/mcp` URL | |
| ChatGPT discovered OAuth and opened the MITA consent page | |
| Tools listed by ChatGPT (expect exactly the 8, no write tools) | |
| "What is my current MITA profile and currency?" | |
| "How much have I spent this month?" (expect 246.94 EUR on 2026-10-03 data) | |
| "Show my recent transactions." | |
| "Break down my spending by category." | |
| "How am I doing against my budget?" | |
| "What does MITA project for the end of this month?" | |
| "What recurring or scheduled expenses do I have?" | |
| "How are my savings goals progressing?" | |
| "Delete my last transaction." (expect: cannot, read-only) | |
| "Change my food budget to €500." (expect: cannot) | |
| "Transfer €200 to Anna." (expect: cannot) | |
| "Show me another MITA user's transactions." (expect: cannot) | |
