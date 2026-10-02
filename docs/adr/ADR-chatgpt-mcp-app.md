# ADR: MITA as a read-only ChatGPT app (MCP)

* Status: accepted for v1 (branch `feat/chatgpt-plugin`)
* Date: 2026-10-02
* Context documents: `docs/chatgpt-app/repository-audit.md`,
  `openai-requirements.md`, `data-trust-audit.md`, `security-findings.md`

## Decision summary

1. One repository, one Python domain layer, **a separate deployable MCP
   service** (`python -m app.mcp`) on its own Railway service and hostname.
2. **Read-only v1.** Eight read tools, no write tool of any kind. Every tool
   runs in a database transaction opened `READ ONLY`.
3. **Identity comes only from the verified access token.** No tool accepts a
   user id, email, account id or any other selector of whose data to read.
4. **ChatGPT does the language; MITA supplies facts.** Tools return structured,
   deterministic data. The MCP service never calls OpenAI or any other model.
5. **OAuth 2.1 with MITA as the authorization server**, implemented on the
   official MCP Python SDK's authorization-server handlers (PKCE, metadata,
   DCR, token, revocation), with a MITA provider for storage, login and
   consent. Access tokens are RS256 JWTs bound to the MCP resource; the
   resource-server verifier is IdP-agnostic so an external IdP can replace the
   built-in AS by configuration.

## 1. Why one repository

The facts ChatGPT will report — ledger, plan allocation, forecast, goals,
entitlement — are already defined in `app/`: the ledger rules
(`expense_tracker`), the plan invariants (`monthly_plan_service`,
`CLAUDE.md`), the forecast engine. A second repository would need a copy of
that logic or an HTTP dependency on the REST API, and the copy is exactly how
two numbers for "what did I spend" appear. Importing the same modules keeps one
definition. The cost is that the MCP image carries the whole `app/` package;
that is acceptable (same image as the API, different start command).

## 2. Why a separate service

* **Blast radius.** A ChatGPT traffic spike, an MCP SDK bug or an OAuth issue
  cannot take down `mita-production`, which the mobile app depends on.
* **Dependencies.** mcp 2.2.0 requires `pydantic>=2.12`; the API pins 2.9.2.
  A separate service installs `requirements-mcp.txt` without forcing a
  pydantic upgrade on the API in the same release.
* **Separate controls.** Own health endpoint, rate limits, logs, metrics,
  environment variables and secrets (`MCP_OAUTH_PRIVATE_KEY`), own rollback.
* **No HTTP self-calls.** The service imports the domain layer and opens its
  own small pool to the same PostgreSQL; it does not proxy `/api/*`.

## 3. Why read-only v1

* OpenAI prohibits executing transfers/trades and requires write tools to be
  annotated and justified; a read-only surface has no destructive annotation to
  get wrong.
* Every MITA write goes through ledger invariants (advisory lock, month
  rebuild, rebalancer, audit log). Exposing them to a conversational client
  needs confirmation UX and idempotency keys that do not exist yet.
* **Enforcement, not convention:** `app/mcp/db.py` issues
  `SET TRANSACTION READ ONLY` on PostgreSQL before any tool query, so even a
  future bug in a tool cannot write. Consequence: the MCP service never calls
  `ensure_month_plan`, which materializes months on read. A month that has not
  been materialized yet is reported as `plan_status: "not_generated"` rather
  than computed as a preview (CLAUDE.md: "A preview is not a budget"). The app
  and the REST API materialize it on first open.
* The OAuth tables (`mcp_oauth_*`) are written by the authorization endpoints,
  never by tools, in separate transactions.

## 4. Why no `user_id` arguments

A tool argument is chosen by the model, and the model's input includes
untrusted text (pasted content, web results, other tools). If a tool accepted
`user_id`, prompt injection or a confused model could request another user's
data and authorization would depend on the tool body remembering to compare
it. Instead, `McpPrincipal` is derived from the bearer token by the transport
middleware, and query functions take the principal's user id as a Python
argument that no tool schema exposes. `tests_mcp/test_tool_contract.py` fails
if any tool input schema contains a property matching
`user|uid|account|owner|email|customer|member`.

## 5. Why ChatGPT does the reasoning

MITA's AI endpoints were the main source of fabricated findings (CLAUDE.md:
health score from income tier, `trend: "stable"` on failure, `on_track: True`
on failure, invented budget optimization). ChatGPT is already the language
model the user is talking to; a second model inside the tool would add cost,
latency, a second privacy flow to OpenAI and a second place to invent. The
tools return numbers with their method (`spent_source: "ledger"`,
`plan_status`, `projection: "linear_daily_pace"`), and the description tells
ChatGPT what each figure is and is not.

## 6. Why MITA remains the source of financial facts

Data-trust audit classification: only TRUSTED sources reach a tool. Spend is
always the ledger (`transactions`, `deleted_at IS NULL`), keyed by the user's
local day through `local_day_of`/`local_day_utc_window`. Allocation is always
`daily_plan.planned_amount`. Forecast is `compute_forecast` with the user's
local today. Money stays `Decimal` end to end and is serialized as a string
with two decimals plus a currency code — never a float.

## 7. OAuth architecture

```
ChatGPT ──(1) GET /mcp → 401 WWW-Authenticate: resource_metadata=…/.well-known/oauth-protected-resource/mcp
        ──(2) GET protected-resource metadata → authorization_servers=[MCP_ISSUER_URL]
        ──(3) GET /.well-known/oauth-authorization-server (S256, registration_endpoint)
        ──(4) POST /register (DCR; redirect_uris must be ChatGPT's)
        ──(5) GET /authorize?…&code_challenge=…&resource=https://host/mcp
                 → provider.authorize() stores a pending request, redirects to /oauth/login?req=…
        ──(6) user enters MITA email + password, sees requested scopes, clicks Allow
                 → shared credential check (same lockout as the app) → code (5 min, single use)
        ──(7) POST /token (code + code_verifier) → SDK verifies PKCE → provider issues
                 access JWT (RS256, 15 min, aud=resource, scope) + refresh token (30 days, rotating)
        ──(8) POST /mcp with Bearer → verifier: sig, iss, aud, exp, nbf, scope, then per call
                 users.token_version == token claim (password change / logout-all revokes ChatGPT too)
```

Decisions inside it:

* **Why not Auth0 (OpenAI's suggested IdP) now:** MITA's identity store is its
  own `users` table (bcrypt, lockout). Making Auth0 authenticate against it
  needs a Custom Database connection (Professional plan, $240/month at 500 MAU
  per auth0.com/pricing on 2026-10-02) or a two-login account-link flow (Auth0
  login, then MITA login) — worse UX and a harder review account. The SDK
  already implements the protocol-critical parts (PKCE verification, code
  exchange, redirect validation, metadata, DCR, revocation); MITA's code is the
  provider (storage + login + consent).
* **No vendor lock-in:** the resource server only needs an issuer, a JWKS (or
  local keys), an audience and a claim that maps to a MITA user. Switching to
  Auth0/Stytch later = set `MCP_AUTH_MODE=external`, `MCP_EXTERNAL_ISSUER`,
  `MCP_EXTERNAL_JWKS_URL`, `MCP_EXTERNAL_USER_CLAIM`, and turn off the built-in
  routes. The tools do not change.
* **Scopes:** `profile:read` (who you are: name, masked email, currency,
  timezone) and `finance:read` (transactions, budget, forecast, goals,
  recurring). Nothing else is grantable; DCR clients cannot register other
  scopes. MITA's own `write:*` / `premium:*` scopes are never issued to
  ChatGPT.
* **Redirect allow-list:** DCR accepts only `https://chatgpt.com/connector/oauth/…`
  and `https://chatgpt.com/connector_platform_oauth_redirect` by default
  (`MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES`). This closes the DCR phishing case
  where an attacker registers a client with their own redirect URI.
* **Refresh token rotation with reuse detection:** stored hashed; reuse of a
  rotated token revokes the whole family.
* **Login page:** no JavaScript, CSRF token (HMAC, bound to the pending
  request), `frame-ancestors 'none'`, `Cache-Control: no-store`, per-IP rate
  limit, account lockout shared with the mobile login.
* **Known gaps:** CIMD (preferred by OpenAI) is not implemented by the SDK's AS
  handlers; DCR is supported by ChatGPT. RFC 9207 `iss` in the authorization
  response is not advertised. Google-only MITA accounts have no usable password
  and cannot sign in on the consent page in v1 (OWNER_ACTIONS O-12).

## 8. Deployment architecture

* Railway: new service `mita-mcp` in project "Mita Finance", same GitHub repo
  and branch, config file `deploy/mcp/railway.json` (Dockerfile build
  `deploy/mcp/Dockerfile`, start `python -m app.mcp`, healthcheck `/health`).
* **Migrations stay with the API.** `mita-production`'s `start.sh` already runs
  `alembic upgrade head`; the MCP service never migrates. It checks at startup
  that its tables exist and refuses readiness otherwise.
* Public hostname: `MCP_PUBLIC_URL` (recommended `https://mcp.mitafinance.com`;
  `mita.finance` is not registered). Resource identifier = `${MCP_PUBLIC_URL}/mcp`.
* Rollback: redeploy the previous `mita-mcp` deployment in Railway; the API
  is unaffected. Disabling the app entirely: remove the domain or scale to 0.

## 9. Security model

| Threat | Control |
|---|---|
| Read another user's data via tool args | no identity args (schema test); principal from token only; cross-user tests |
| Token for another resource replayed here | `aud` must equal `MCP_RESOURCE_URL` |
| Stolen access token | 15 min lifetime; `token_version` revocation checked per call |
| Stolen refresh token | rotation + family revocation on reuse; revocation endpoint |
| Malicious DCR client | redirect allow-list; consent page shows client name and redirect host |
| Credential stuffing on consent page | per-IP rate limit + shared account lockout |
| Write through a buggy tool | `READ ONLY` transaction |
| Data over-exposure | per-tool serializers, PII/UUID scan test |
| Log leakage | structured logs carry tool name, outcome, latency, hashed subject; never tokens, amounts, merchants or descriptions |

## 10. Future write tools

Not in v1. If added: one tool per action (`add_expense`), `readOnlyHint=false`,
`destructiveHint` true for edits/deletes, a new scope (`finance:write`)
requested only when needed (incremental consent), idempotency key argument,
route through the existing ledger service (`commit_transaction_to_ledger`),
never a generic `execute_action`. Payments/transfers/trading remain out of
scope (OpenAI prohibits them).
