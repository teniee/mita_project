# OpenAI requirements for publishing MITA as a ChatGPT plugin (checked 2026-10-02)

Sources (official only, fetched 2026-10-02):

* Upload and submit your plugin — https://developers.openai.com/plugins/deploy/submission
* Remote MCP server review requirements — https://developers.openai.com/plugins/deploy/app-review
* Package your plugin — https://developers.openai.com/plugins/build/plugins
* Plugin guidelines — https://developers.openai.com/plugins/plugin-guidelines
* App submission guidelines — https://developers.openai.com/apps-sdk/app-submission-guidelines
* Authentication — https://developers.openai.com/apps-sdk/build/auth
* Build an MCP server — https://developers.openai.com/plugins/build/mcp-server

## Differences from the brief

| Brief said | Current OpenAI docs | Followed |
|---|---|---|
| "ChatGPT App / Plugin Directory", `plugin.json`, `mcp.json` | Submission is a **plugin ZIP** in the Agent Plugins format: `plugin.json` (schema `https://agent-plugins.org/schemas/1.0.0/plugin.schema.json`) + `mcp.json` (schema `.../mcp.schema.json`) + `assets/`. OpenAI presentation and review data live under `extensions["com.openai"]`. | Agent Plugins format, `plugin/mita/` |
| "plugin manifest" with app reference | ZIPs containing `apps` / `.app.json` or hooks **cannot currently be submitted** | no `apps`, no hooks |
| Test cases "as many as required" | **5 positive + 3 negative** | exactly 5 + 3 |
| Domain `mcp.mita.finance` | Challenge served at `https://<host>/.well-known/openai-apps-challenge`, body = the token only | endpoint implemented; host is config — `mita.finance` is not registered (see repository-audit §7) |
| OAuth "if required" | OAuth 2.1 auth code + PKCE **S256**, RFC 9728 protected-resource metadata, RFC 8414 AS metadata, client via **CIMD (preferred) or DCR**, `resource` param → token `aud` | built-in AS on the official MCP SDK handlers, DCR; CIMD not in the SDK yet (gap below) |
| `user_id` never accepted | (OpenAI: inputs must be minimal and task-specific) | enforced by test |
| Premium check allowed? | Existing paid access may be honored; **no selling digital goods/subscriptions**, no checkout links for unavailable features | v1 has no premium-only tool, no upsell text |

## Checklist

Legend: ✅ done in this branch · 🟡 done, needs owner input to go live · ❌ blocked

| # | Requirement (source) | Current MITA state | Gap | Implementation |
|---|---|---|---|---|
| 1 | Public HTTPS streamable-HTTP MCP endpoint, typically `/mcp` (mcp-server) | none | new service | `app/mcp/server.py`, stateless streamable HTTP at `/mcp`; 🟡 needs Railway service + DNS |
| 2 | Tools work without UI first (mcp-server) | — | — | ✅ tools only, no iframe |
| 3 | Tool names: human-readable, specific, verbs, unique (guidelines) | — | — | ✅ `get_profile`, `list_transactions`, … ; uniqueness asserted in tests |
| 4 | Non-empty description: purpose, when to use, limitations, side effects; must match behavior (guidelines) | — | — | ✅ every description states read-only + limits; test asserts non-empty + mentions read-only |
| 5 | `readOnlyHint`, `destructiveHint`, `openWorldHint` explicit booleans on every tool (guidelines, app-review) | — | — | ✅ `True/False/False`; `tests_mcp/test_tool_contract.py` fails on any tool missing one |
| 6 | Only data relevant to the request; no internal IDs, request IDs, timestamps, telemetry (guidelines) | REST payloads include UUIDs, `created_at` | — | ✅ serializers whitelist fields; test scans every tool output for UUIDs / tokens / emails |
| 7 | Minimal inputs, no conversation history fields (guidelines) | — | — | ✅ no free-form context args; no `user_id`; test enforces |
| 8 | No money transfers, crypto, trades (plugin guidelines) | MITA does none | — | ✅ v1 read-only; negative test cases cover transfer/delete/buy |
| 9 | No sale of digital goods/subscriptions; no checkout links for gated features (guidelines) | MITA sells Premium via IAP | must not upsell in ChatGPT | ✅ no paywall, no purchase links; `review.commerce=false` |
| 10 | Protected resource metadata at `/.well-known/oauth-protected-resource` (auth) | none | — | ✅ SDK route (`/.well-known/oauth-protected-resource/mcp`) |
| 11 | 401 with `WWW-Authenticate: Bearer resource_metadata=…` (auth) | — | — | ✅ SDK `RequireAuthMiddleware`; tested |
| 12 | AS metadata (RFC 8414) with `code_challenge_methods_supported: ["S256"]` (auth) | none | — | ✅ SDK route |
| 13 | Client registration: CIMD preferred, DCR supported (auth) | none | CIMD unsupported by mcp SDK 2.2.0 AS handlers | 🟡 DCR implemented; CIMD listed as follow-up (ChatGPT accepts DCR) |
| 14 | PKCE S256 (auth) | — | — | ✅ SDK token handler verifies; tested with a wrong verifier |
| 15 | `resource` echoed into token `aud`, server validates audience (auth) | — | — | ✅ provider rejects a foreign `resource`; verifier requires `aud == MCP_RESOURCE_URL` |
| 16 | Redirect URIs `https://chatgpt.com/connector/oauth/{id}` and `https://chatgpt.com/connector_platform_oauth_redirect` (auth) | — | — | ✅ DCR only accepts redirect URIs in `MCP_OAUTH_ALLOWED_REDIRECT_PREFIXES` (defaults to those two) |
| 17 | Token verification: signature, iss, exp/nbf, aud, scopes (auth) | MITA HS256 tokens, wrong audience | — | ✅ `app/mcp/auth/verifier.py` RS256 + kid; plus `token_version` check per call |
| 18 | Profile tool for multi-account: `get_profile`, empty args, read-only, `_meta["openai/profile"]: true`, stable opaque `id` (auth) | — | — | ✅ `id = "prf_" + sha256("mita-profile-v1:"+uuid)[:16]` |
| 19 | Review/demo account with sample data, no MFA/email codes/magic links (submission, guidelines) | none | owner must create | 🟡 `scripts/mcp/seed_review_account.py` + `review/review-account.md`; credentials entered in dashboard, never in git |
| 20 | 5 positive + 3 negative test cases (submission) | — | — | ✅ `docs/chatgpt-app/review/*` and in `plugin.json` |
| 21 | Video walkthrough URL (submission) | — | owner records | 🟡 `review/demo-script.md`; URL placeholder |
| 22 | Release notes (submission) | — | — | ✅ `review/release-notes.md`, `publication.release_notes` |
| 23 | Website, support, privacy, terms URLs over HTTPS (submission) | `mitafinance.com` HTTPS broken; no real policy/support pages | ❌ blocker | 🟡 owner: fix TLS, publish pages (OWNER_ACTIONS) |
| 24 | Listing limits: name ≤30, short desc ≤30, long ≤4000, dev name ≤80, capabilities ≤20×120, prompts ≤128 (submission) | — | — | ✅ validated by `scripts/mcp/validate_plugin.py` in CI |
| 25 | Icons square ≥48×48, PNG/JPEG/WebP/SVG ≤5 MiB (submission) | brand PNGs exist outside repo | owner supplies final art | 🟡 SVG placeholder generated from the brand logo mark spec; validator checks size |
| 26 | Domain verification `/.well-known/openai-apps-challenge`, exact token (submission) | — | — | ✅ endpoint serving `OPENAI_APPS_CHALLENGE_TOKEN`; 🟡 owner sets token |
| 27 | Verified individual/organization; Apps Management Write (submission) | unknown | owner | 🟡 OWNER_ACTIONS |
| 28 | CSP for UI (app-review) | — | no UI | n/a |
| 29 | Suitable for 13–17, no under-13 targeting (guidelines) | ToS age? (legal-audit) | owner/legal | 🟡 |
| 30 | Customer support contact (guidelines) | `@mita.finance` addresses on an unregistered domain | ❌ | 🟡 owner: working support address |
| 31 | Stable, complete, not a trial (guidelines) | — | — | ✅ CI + review package |
| 32 | Each tool independent; no instructing the model to call another plugin (guidelines) | — | — | ✅ |
| 33 | Countries allow-list optional (submission) | — | owner decision | `publication.countries` omitted (no restriction) — owner may restrict |

## Financial-app specifics

OpenAI's pages contain no separate financial-app checklist beyond the
prohibited list (transfers/trades/crypto/lending schemes) and the sensitive
data rules: **payment card data, government IDs and access credentials must
not be collected**. MITA's MCP tools take no such inputs and the transaction
serializer never returns `receipt_url`, `location`, `notes`, `tags` or
`confidence_score`.
