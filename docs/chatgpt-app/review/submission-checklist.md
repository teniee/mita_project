# Readiness (2026-10-11, v2 update 2026-10-18)

Status categories: **CODE READY** (implemented) · **CI VERIFIED** (GitHub CI)
· **STAGING VERIFIED** (observed on the public staging endpoint) ·
**CHATGPT VERIFIED** (observed in real ChatGPT) · **OWNER REQUIRED** ·
**PRODUCTION NOT DONE**.

Production work follows `docs/chatgpt-app/production-readiness.md` (13 steps,
strict order); owner steps are in `OWNER_ACTIONS.md`. v2 staging evidence:
`staging-acceptance-v2.md` — current staging MCP 2.1.0: commit `79efb1d`,
deployment `87d26668`, CI run `39155447750` (§9); real ChatGPT §8 and §11.
**Staging acceptance closed 2026-10-19.** Every production row below is
unchanged.

## 2026-10-26 update (local; nothing deployed)

| Requirement | Status | Evidence | Remaining |
|---|---|---|---|
| R3: unpaid bills held out of the safe daily amount, the same in ChatGPT and the mobile forecast | CODE READY, TESTED LOCALLY | `r3-bills-reserve.md`; `tests_mcp/test_bills_reserve.py` (the scenario matrix), `test_money_consistency.py`, `app/tests/test_budget_forecast_local_day.py` | commit; staging (7e); real ChatGPT |
| F-9 (mobile figures: local day, savings out of today) | FIXED LOCALLY | `backend-findings.md` F-9 | commit |
| Final connect page (v5.2) | CODE READY, TESTED LOCALLY (axe 0 violations) | `docs/chatgpt-app/review/auth-ui-v5.2/` | commit; staging; real ChatGPT |
| `_meta.ui.domain` (`MCP_WIDGET_DOMAIN`) — OpenAI: required for a plugin with UI, unique | **OWNER REQUIRED** | unset on staging (variable names, 2026-10-26); no production MCP service | production-readiness 6b |
| Staging runs the code to be submitted | **NOT DONE** | staging pinned to `dbdc118` (2.2.0, v4 page, usage box pre-ticked) | production-readiness 7e |
| Real-ChatGPT acceptance of the calendar and the final page | **NOT DONE** | `calendar-owner-test.md` (updated) | after 7e |
| Website, support, privacy, terms URLs (OpenAI: all four required, HTTPS) | **OWNER REQUIRED** | `https://mitafinance.com` TLS alert; no `www`, no `mcp.` DNS (2026-10-26) | steps 2–4 |
| 5 positive + 3 negative test cases (OpenAI: exactly) | CODE READY | `plugin/mita/plugin.template.json` | add the calendar prompt among the 5 (12b) |
| Demo video, reviewer account, developer verification, domain verification | **OWNER REQUIRED** | — | steps 8–11 |
| API dependency advisories (pip-audit: 200 in 9 packages) | **NOT DONE** | production-readiness 7f | before the merge |

## Original table (2026-10-11 / 2026-10-18)

| Requirement | Status | Evidence | Remaining |
|---|---|---|---|
| Streamable HTTP MCP at `/mcp`, public HTTPS | STAGING VERIFIED, CHATGPT VERIFIED (v1) | `https://mita-mcp-staging-staging.up.railway.app/mcp`, `/health` version 2.0.0 | production: PRODUCTION NOT DONE (steps 6–7) |
| Connected in real ChatGPT developer mode | CHATGPT VERIFIED (v2, all five scopes) | staging-acceptance-v2.md §8 (S-6): plugin recreated with DCR; v1 grant earlier (staging-acceptance.md §5.1) | an old DCR registration keeps its v1 scopes (F-7) |
| 24 tools (14 read, 10 write; 22 until MCP 2.2.0), facts-only hints, no identity inputs, strict arguments | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (22) | `test_tool_contract.py`; staging: smuggled `user_id` rejected (§2, §4); writes used in ChatGPT (§8) | the two calendar tools in real ChatGPT: OWNER REQUIRED (`calendar-owner-test.md`) |
| UI component: the interactive financial calendar (MCP Apps, `ui://mita/financial-calendar-v1.html`; render tool `show_financial_calendar`) | CODE READY, CI VERIFIED, LOCALLY VERIFIED (MCP Apps host harness) | `test_calendar.py`; `scripts/mcp/calendar_widget_review.py` (59 checks, axe WCAG 2.2 AA); `docs/chatgpt-app/financial-calendar.md` | real ChatGPT rendering, fullscreen and image save: OWNER REQUIRED; `MCP_WIDGET_DOMAIN` at submission: OWNER REQUIRED |
| 8 original read tools unchanged | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | every read tool exercised before and after a restart (§4) | — |
| Account creation in the OAuth flow (shared e-mail/password policy, generic errors, per-IP limit) | CI VERIFIED, STAGING VERIFIED | `test_registration.py`; e2e_v2 sign-up (§2) | real ChatGPT: S-6 |
| Profile, expenses, batch, corrections, retry safety (idempotency) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (profile, expenses, update, delete) | `test_transaction_writes.py`, `test_idempotency_concurrency.py` (forced race); retry → `already_recorded` on staging; §8 cases 1, 5–6, correction, deletion | retry is not observable from ChatGPT |
| Recurring expenses, savings goals | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_recurring_goal_writes.py`; §8 rent and goal; S-8 D: an unsupported contribution change is explained, not claimed (§11) | — |
| Budget preview → signed draft → save (reviewed == saved) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_budget_plan.py`; §8: preview not saved, expired draft refused, identical re-preview saved (2,325 / 175 / 2,500) | drafts now last 2 hours (issue F) |
| Persistence across conversations | STAGING VERIFIED, CHATGPT VERIFIED | §2; §8 case 9 (new conversation: plan, spent, rent, savings, expenses; deleted coffee absent) | — |
| Six-month history and financial climate | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_history.py`; §8 no-history path and climate; S-8 H: July–September 300/320/360, September +16.1 % vs €310 (§11) | — |
| Receipt photo → expenses (ChatGPT vision, no image stored) | CHATGPT VERIFIED, STAGING VERIFIED | two real receipts (My Market 12 lines; GamingGear.bg dated 2025) and the same receipt again with 0 new expenses (§8, §11); 0 stored receipt URLs (§11); synthetic fixture: repository tests only | a repeat request is caught by ChatGPT's judgement, not by backend content dedup |
| Feedback to the team | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (tool) | §2, §3; §8 case 15; the owner's row and its type/area-only event checked read-only (§9) | — |
| Product analytics (consented, pseudonymous, allow-listed, out of band) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (opt-out) | `test_analytics_db.py`; staging audit and report (§3, §9); S-8 J: opt-out confirmed in ChatGPT, identity and linked events deleted, finances intact (§11) | Metabase hosting: OWNER REQUIRED (O-18); retention: O-17 |
| One display name per category in every tool (F-2 presentation) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_categories.py`; public staging (§9); S-8 B–C: one Fuel category, consistent names (§11) | ledger mapping (F-2) remains backend debt |
| Least-privilege database role for the MCP service | STAGING VERIFIED | staging runs as `mita_mcp`; 70/70 + 27 + 19 + 24 checks, no permission errors (§1, §5) | production: step 6 |
| OAuth 2.1 (PRM, AS metadata, DCR, PKCE S256, resource binding, rotation, revocation) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (connection) | adversarial suite; staging e2e + 24 failure modes (§4) | — |
| Exact figures; soft deletes; timezone | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | v1: ChatGPT matched ground truth to the cent; v2: exact figures in e2e_v2 | — |
| Negative cases (transfer, other user, trading) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | §8 cases 16–18; S-8 E: only the owner's records searched, nothing of anyone else (§11) | — |
| Onboarding skill, starter prompts (set up / record / "Show my financial calendar for this month.", 2026-10-25), listing (plugin 2.1.0) | CODE READY, CI VERIFIED (`--check`) | `build_plugin.py`, `test_plugin_package.py`, 73 golden prompts (en/ru/bg) | final ZIP: OWNER REQUIRED (step 12) |
| Capacity (600k transactions) | VERIFIED locally | capacity-plan.md: p95 ≤ 20 ms per tool query, no new index | — |
| Grant fingerprint secret separate from CSRF secret | CI VERIFIED, STAGING VERIFIED | `test_secret_separation.py` | — |
| Cross-user isolation | CI VERIFIED, STAGING VERIFIED | `test_isolation.py`; forged ref refused on staging | — |
| Logs free of tokens/codes/passwords/amounts/e-mails | CI VERIFIED (container), STAGING VERIFIED | 2.0.0: 235 entries, 0 hits (§5); 2.1.0: 336 entries, 0 hits, 6 expected security warnings (§9) | — |
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
