# Staging acceptance — observed results

Target: `https://mita-mcp-staging-staging.up.railway.app`, fake account
`staging-review@example.test`. Scripted checks (§1–4) ran against commit
`842d365` on 2026-10-03. Real-ChatGPT acceptance (§5) ran against the same
deployment and was reported by the owner on 2026-10-11. Staging was then
redeployed to `fcd7ae3`, which changes tool metadata only (§6). No
credentials or tokens are recorded here.

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

## 5. Real ChatGPT (CHATGPT VERIFIED, reported 2026-10-11)

Run by the owner in real ChatGPT against staging `842d365` with the fake
account. Observations as reported; the third column compares them with the
ground truth in §3.

### 5.1 Connection and positive acceptance

| Check | Observed in ChatGPT | Ground truth (§3) | Status |
|---|---|---|---|
| OAuth / DCR | connection completed; staging account authenticated | — | CHATGPT VERIFIED |
| `get_profile` | Staging Review, EUR, Europe/Sofia | same | CHATGPT VERIFIED |
| `get_financial_summary` | 7 transactions; €246.94 spent; €2,358.00 monthly budget; €2,111.06 remaining; 10.5 % used | 7; 246.94; 2358.00; 2111.06 (246.94 / 2358.00 = 10.47 %) | CHATGPT VERIFIED |
| `list_transactions` | exactly 7 transactions, total €246.94 | 7, 246.94 | CHATGPT VERIFIED |
| Soft-deleted €999.99 | never appeared | absent from every tool | CHATGPT VERIFIED |
| `get_spending_breakdown` | Groceries €114.40, Dining €78.55, Transportation €38.00, Subscriptions €15.99 | same | CHATGPT VERIFIED |
| `get_budget_status` | correct for the actual current date | figures move daily (§3 note) | CHATGPT VERIFIED |
| `get_budget_forecast` | correct for the actual current date | figures move daily | CHATGPT VERIFIED |
| `get_recurring_expenses` | Staging Maple Apartments €1,100 monthly; Staging StreamFlix €15.99 marked recurring; Staging SafeCar Insurance €240 one-time | rent 1100.00 monthly; StreamFlix marked recurring; insurance once | CHATGPT VERIFIED |
| `get_goals` | Emergency Fund, €900 / €3,000, 30 %, on track | "Staging emergency fund", 900 / 3000, 30.0 %, on track | CHATGPT VERIFIED (amounts; title see §6.3) |

All eight tools were exercised. The number of tools ChatGPT listed was not
reported; at protocol level it is exactly 8 (§2).

### 5.2 Negative acceptance

| Prompt | Observed | Status |
|---|---|---|
| "Delete my most recent transaction" | refused: MITA is read-only | CHATGPT VERIFIED |
| "Change my food budget to €500" | refused: MITA is read-only | CHATGPT VERIFIED |
| "Transfer €200 to Anna" | no transfer executed; ChatGPT said MITA cannot send money, then offered to help prepare the transfer through a bank or payment service of the user's choice (§6.2) | CHATGPT VERIFIED (no MITA capability; wording see §6.2) |
| Transactions of `staging-other@example.test` | no other user's data exposed | CHATGPT VERIFIED — staging holds one account, so this shows nothing is fabricated or exposed by prompt; real cross-user isolation is `test_isolation.py` (CI) and the smuggled-`user_id` check (§2) |
| Control read after all negative prompts | 7 transactions; €246.94 spent; €2,358.00 budget; €2,111.06 remaining | CHATGPT VERIFIED: unchanged, so no prompt wrote anything |

## 6. UX observations and the follow-up change (`fcd7ae3`)

Neither observation was a data error or a security failure. The fix is tool
metadata only; structured output is unchanged.

**6.1 "Other expenses €15.99" in a summary answer.** `get_financial_summary`
returns `top_categories` = the three largest categories by design
(`app/mcp/serializers.py`, `totals[:3]`). With four categories the €15.99
`subscriptions` spend is not in that payload, so ChatGPT labelled the
remainder (246.94 − 230.95) itself; `get_spending_breakdown` named it
correctly. The MCP output is correct. The relabel matters because `other` is a
real MITA category (`app/config/category_config.py`): "Other expenses" can be
mistaken for it. Now stated in the summary description, the `top_categories`
schema text ("Not a full breakdown … get_spending_breakdown lists every
category"), `CategorySpendOut.category` ("MITA's category name … do not rename
it or merge it") and the server instructions.

**6.2 Transfer prompt.** MITA has no transfer tool and executed nothing; the
offer to prepare a transfer elsewhere was ChatGPT's own help. Every tool
description, the server instructions and the plugin listing now say "MITA
cannot initiate, execute or facilitate payments or money transfers" and that
MITA is not connected to any bank or payment account (verified: no bank or
payment integration in `app/`). This is stated as a fact about MITA only:
OpenAI's guidelines forbid metadata that steers the model about other
plugins or services, so ChatGPT may still offer general help outside MITA.
No money-transfer tool was added.

**6.3 Goal title.** Reported as "Emergency Fund"; the stored title is
"Staging emergency fund". Amounts are exact. Either ChatGPT shortened the
title or the report abbreviates it; titles are user text and were not
changed.

Evidence for `fcd7ae3`: MCP suite 252 passed locally (247 before); 4 new
contract tests fail on the old metadata; CI run `38138961278` success on
every job — Backend, Mobile, and MCP (lint, Bandit, pip-audit, plugin check,
full suite, image build, container e2e across a restart, log scan); staging
redeploy recorded in §7.

## 7. Staging redeploy to `fcd7ae3` (STAGING VERIFIED, 2026-10-11)

Service source re-pinned from `842d365` to `fcd7ae3` (staging project only;
production untouched). Deployment `e060f0b8` → SUCCESS at 12:29 UTC; deploy
log shows a clean start (Uvicorn on 8080, session manager started, no
errors). Variables, database and secrets unchanged, so existing ChatGPT
grants stay valid.

| Endpoint | Observed after redeploy |
|---|---|
| `GET /health` | 200 `{"status":"ok","service":"mita-mcp","version":"1.0.0"}` |
| Protected-resource metadata (`/mcp` and root) | 200; `resource` = `…/mcp`; scopes `profile:read finance:read` |
| AS metadata | issuer exactly the origin; S256 only; `client_secret_basic, client_secret_post, none` |
| JWKS | one RS256 key, no private parameters |
| `POST /mcp` without token | 401 with `resource_metadata` = `…/.well-known/oauth-protected-resource/mcp` |
| `/authorize` (no params) · `/token` (no client) · `/metrics` · challenge | 400 · 401 · 401 · 404 |

Identical to §1. `tools/list` over public HTTPS needs a token and was not
re-run here; an image built from the same commit passed the container e2e
in CI run `38138961278` (all 8 tools, across a restart).

Re-check in ChatGPT (optional, NOT YET): ChatGPT caches tool metadata, so
refresh the staging app in developer mode first, then ask "Summarize my
spending this month by category" and "Transfer €200 to Anna". Expected: every
category under its MITA name (or a pointer to the breakdown) and no "Other
expenses" line for `subscriptions`; the transfer refusal states MITA cannot
initiate, execute or facilitate transfers.
