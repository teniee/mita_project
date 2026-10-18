# Readiness (2026-10-11, v2 update 2026-10-18)

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
| Connected in real ChatGPT developer mode | CHATGPT VERIFIED (v2, all five scopes) | staging-acceptance-v2.md §8 (S-6): plugin recreated with DCR; v1 grant earlier (staging-acceptance.md §5.1) | an old DCR registration keeps its v1 scopes (F-7) |
| 22 tools (12 read, 10 write), facts-only hints, no identity inputs, strict arguments | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_tool_contract.py`; staging: exactly 22 tools, smuggled `user_id` rejected (§2, §4); writes used in ChatGPT (§8) | — |
| 8 original read tools unchanged | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | every read tool exercised before and after a restart (§4) | — |
| Account creation in the OAuth flow (shared e-mail/password policy, generic errors, per-IP limit) | CI VERIFIED, STAGING VERIFIED | `test_registration.py`; e2e_v2 sign-up (§2) | real ChatGPT: S-6 |
| Profile, expenses, batch, corrections, retry safety (idempotency) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (profile, expenses, update, delete) | `test_transaction_writes.py`, `test_idempotency_concurrency.py` (forced race); retry → `already_recorded` on staging; §8 cases 1, 5–6, correction, deletion | retry is not observable from ChatGPT |
| Recurring expenses, savings goals | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (rent; goal creation) | `test_recurring_goal_writes.py`; §8 case 2 and goal | fixed: ChatGPT offered a goal contribution no tool can set (issue B, `test_acceptance_fixes.py`); S-8 step 3 |
| Budget preview → signed draft → save (reviewed == saved) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED | `test_budget_plan.py`; §8: preview not saved, expired draft refused, identical re-preview saved (2,325 / 175 / 2,500) | drafts now last 2 hours (issue F) |
| Persistence across conversations | STAGING VERIFIED, CHATGPT VERIFIED | §2; §8 case 9 (new conversation: plan, spent, rent, savings, expenses; deleted coffee absent) | — |
| Six-month history and financial climate | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (no-history path) | `test_history.py`; §2 trend path; §8 cases 10 and climate | trend path in ChatGPT: S-8 step 7 |
| Receipt photo → expenses (ChatGPT vision, no image stored) | CODE READY, CHATGPT VERIFIED (real receipt, 12 lines, €41.50) | §8 cases 11–12; no tool accepts an image | per-line categories (issue D) and a repeated request: S-8 steps 5–6 |
| Feedback to the team | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (tool) | §2, §3; §8 case 15 | database check: S-8 / §7 |
| Product analytics (consented, pseudonymous, allow-listed, out of band) | CI VERIFIED, STAGING VERIFIED | `test_analytics_db.py`; staging audit + report as `mita_analytics_reader`; cascade on deletion (§3) | Metabase hosting: OWNER REQUIRED (O-18); retention: O-17 |
| One display name per category in every tool (F-2 presentation) | CI VERIFIED | `test_categories.py`: labels for every stored vocabulary, pairs only from `category_aliases`, one line per label, the owner's scenario end to end | S-8 steps 1–2 |
| Least-privilege database role for the MCP service | STAGING VERIFIED | staging runs as `mita_mcp`; 70/70 + 27 + 19 + 24 checks, no permission errors (§1, §5) | production: step 6 |
| OAuth 2.1 (PRM, AS metadata, DCR, PKCE S256, resource binding, rotation, revocation) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (connection) | adversarial suite; staging e2e + 24 failure modes (§4) | — |
| Exact figures; soft deletes; timezone | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v1) | v1: ChatGPT matched ground truth to the cent; v2: exact figures in e2e_v2 | — |
| Negative cases (transfer, other user, trading) | CI VERIFIED, STAGING VERIFIED, CHATGPT VERIFIED (v2: transfer, another person, Bitcoin) | no money-movement tool; §8 cases 16–18 | wording for another person's name tightened (issue G); S-8 step 4 |
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
