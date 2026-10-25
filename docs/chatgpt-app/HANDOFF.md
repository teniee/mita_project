# Handoff — MITA in ChatGPT (MCP), 2026-10-25

## Current phase: financial correctness, real-ChatGPT acceptance, staging stabilisation (2026-10-25)

| Item | State |
|---|---|
| Brief | owner, 2026-10-25: no redesign; F-8 first (proposal before any change to the money model), consistency tests, the usage box unticked, staging clean-up, real-ChatGPT acceptance, the calendar as a starter prompt, usability defects only |
| F-8 | root cause found and measured (`f8-money-model-proposal.md`): of €948.05 treated as overspending in the review month, €206.49 was real; the rest was timing, naming (F-2) and pacing, because the rebalancer works per date and category. Proposal R1–R5 with simulated figures; **awaiting the owner's decisions D1–D4 — nothing implemented** |
| Consistency tests | `tests_mcp/test_money_consistency.py` (22): every scenario through the real tools and the real rebalancer, checked across `get_budget_status`, `get_budget_forecast`, `get_calendar_month`, `show_financial_calendar`, the stored rows (money conserved, spend cache equal to the ledger) and the mobile API's figures; today's F-8 behaviour pinned with hand-checkable numbers (`…_today`), including the review month exactly |
| New finding | F-9: the app's day budget (`/budget/live_status`) still counts today's savings slice; `/budget/forecast` uses the server's UTC date |
| Usage statistics | box unticked by default on both tabs (approved); a tick is the consent; on sign-in an unticked box keeps the earlier choice and deletes nothing; withdrawal stays `set_usage_analytics(false)` (deletes linked events). No production user ever saw the pre-ticked box (MCP is not in production) |
| Starter prompts | set up / record / **"Show my financial calendar for this month."** (replaced "How am I doing financially this month?"); pinned as golden prompt en-35 → `show_financial_calendar` |
| Usability | narrow phones (320/360 px): amounts were cut mid-number ("22.1" for 22.15), the Spent tile truncated, Save as PNG cut off; now a fit pass (smaller size, then whole euros said under the grid), tiles two-up, buttons stacked; the "How is this worked out?" toggle 32 px tall. Harness 65/65 with axe 0 violations in 4 states; sign-in page axe 0 in 8 states |
| Owner acceptance in ChatGPT | rewritten `calendar-owner-test.md` (12 steps, screenshots, A/B/C for the PNG) — not yet run |
| Owner next | 1. decide F-8 (D1–D4); 2. authorise database access for the staging clean-up; 3. run `calendar-owner-test.md` in ChatGPT |

## Previous phase: the financial calendar in ChatGPT + sign-in page v4 (MCP 2.2.0)

| Item | State |
|---|---|
| Brief | owner, 2026-10-24: v3 rejected (generic, static); a premium sign-in/marketing page and a genuinely interactive financial calendar rendered inside ChatGPT (MCP Apps) |
| Owner decisions | hero photo generated with Figma AI (no real people, alt text "Illustration"); "fixed commitments" = plan lines (SACRED essentials + the categories of saved regular payments), reconciled to the plan |
| What changed | `get_calendar_month` + `show_financial_calendar` (24 tools, MCP 2.2.0), the `ui://mita/financial-calendar-v1.html` component, `queries/calendar.py`, `ToolOutput` in `runtime.py`, `MCP_WIDGET_DOMAIN`; the sign-in page v4 (`pages.py`, `demo.py`, hero photo); plugin listing 2.1.0 |
| Unchanged | the OAuth flow (`login.py`, scopes, CSP, headers, no script on the sign-in page), every existing tool's figures, the forecast engine, production |
| Docs | `financial-calendar.md` (design, definitions, limits), `docs/brand/AUTH-UI-DESIGN.md` (v4 + claim table), `tool-catalog.md`, `backend-findings.md` F-8, `calendar-owner-test.md` |
| Tests | MCP suite 578 passed, `test_calendar.py` 32, `test_auth_ui.py` rewritten for v4 (34); local MCP Apps host `calendar_widget_review.py` 59/59 incl. axe WCAG 2.2 AA (0 violations, 4 states); capacity re-run: calendar p95 10.8 ms; sign-in page axe 0 violations in 8 states |
| Screenshots | `review/calendar-v1/` (local MCP Apps host — not ChatGPT), `review/auth-ui-v4/` |
| Staging | `dbdc118` live since 2026-10-24 20:10 UTC (deployment `7fd7783b`), verified — see "Staging deployment of `dbdc118`" below |
| Owner next | `calendar-owner-test.md` (S-9, S-10): refresh the staging app in ChatGPT, review the page and the calendar on the phone and the computer, report what Save as PNG does in ChatGPT |

**Found, not fixed (owner decisions):** F-8 — MITA's automatic rebalancing
drains the plan of the dates ahead when a saved bill is paid on another date
than the layout puts it (review account: €12.16 left on 25–31 Oct against a
base of €299.95, while the safe daily average was €121.99). The calendar shows
both figures, labelled. Starter prompts were left as the planned three (a
calendar prompt would replace one — your call).

### Staging deployment of `dbdc118` (MCP 2.2.0) — live since 2026-10-24 20:10 UTC

| Item | Result (2026-10-24) |
|---|---|
| Deployment | `7fd7783b-d910-4c7b-b32b-324fb693a751`, created 20:09:37 UTC, SUCCESS 20:10:11 UTC; replaced `b4f6d2fd` (`de96251`, the v3 page, 2026-10-23 20:13 UTC) |
| Source | `teniee/mita_project` @ `feat/chatgpt-auth-ui`, pinned to `dbdc118343133f1658b2dc29ef1598cb80d95e29` by connecting the source again with the SHA |
| Health | `/health` ok, MCP 2.2.0; protected-resource metadata unchanged (five scopes); unauthenticated `/mcp` 401 |
| Runtime | 1 replica, `mita_mcp` over the private network, alembic `0039` — no migration in this release; `MCP_WIDGET_DOMAIN` not set |
| Sign-in page | 23 states rendered from staging (`auth_ui_screenshots.py`): 13 pixel-identical to `review/auth-ui-v4/` after the same WebP encoding, 8 differ only by anti-aliasing in the shadows of the tilted photo and floating cards (same content), the 2 motion frames by capture timing. Fonts and both hero images served from `/oauth/assets/` |
| Calendar | `calendar_widget_review.py` against staging, public endpoints only: 58/58 — sign-up through the real page, the month entered through MITA's tools, `tools/list`, the `ui://` resource, render and data tools agree, inline/fullscreen/phone/desktop, light/dark, a date's figures and expenses, model context, filter, keyboard, next month, PNG through `ui/download-file` and without it, axe-core WCAG 2.2 AA 0 violations in 4 states, read tools only. Same figures as the local review (€121.99 a day, 7 days left, €12.16 planned on the dates ahead — F-8) |
| Logs | 275 lines (148 deploy, 108 HTTP, 19 build): no e-mail, token, JWT, amount, merchant, DB URL, query string or error-level line; none of the service's 16 variable values of 12+ characters |
| CI on `dbdc118` (run `40128512856`) | Backend and Mobile CI green; MCP CI green up to the container end-to-end step (lint, Bandit, dependency audit, plugin package, security gate, full suite, image build), which failed: `e2e_http.py` requires every published read tool to be called with a read-only grant and did not call the two calendar tools. Fixed in the next commit (both tools called, each checked against the ledger); scripts only, so staging stays on `dbdc118` |
| Left on staging | one fictional review account and the DCR clients of the two runs: the TCP proxy for the clean-up was not opened (`staging.md` → "Left on staging") |
| Also fixed | the calendar harness's clean-up deleted only the `users` row; `transactions` has no foreign key to `users`, so it now uses `e2e_v2.cleanup` and checks no row of the account remains |
| PR #287, `main`, production | untouched: PR head `200c34d`, `main` `27ed25d`, no production deploy, migration, variable or secret change |

## Previous phase: mobile-first sign-in + safe-daily fix on staging (2026-10-23) — v3 reviewed and not approved

| Item | State |
|---|---|
| Branch | `feat/chatgpt-auth-ui`, a child of `feat/chatgpt-plugin` @ `200c34d`: `fc9aeeb` the UI, `8c5116b` import order, `ee388c0` tablet header + owner test, `1e24bf4` mobile-first page + safe-daily fix, then documentation |
| What changed | the `/oauth/login` sign-in / sign-up / consent page, now phone-first (`app/mcp/auth/pages.py`); the forecast engine no longer counts set-aside money as spendable (`savings_set_aside`); `login.py`, scopes, CSP and headers unchanged |
| Design source | Figma Brand Guidelines `512WdjnhPJXM8jeHKcg4g8` → `docs/brand/AUTH-UI-DESIGN.md` |
| Tests | MCP suite 542 passed locally (25 new in `test_spendable_forecast.py`); CI run `39999435592` on `1e24bf4`: Backend and Mobile CI green, MCP CI stopped at its dependency audit — a new advisory against `opentelemetry-api` (below) — so its later steps did not run; on staging `e2e_v2.py` 77/77 and the live safe-daily check 45/45 |
| Screenshots | `docs/chatgpt-app/review/auth-ui-v2/` (20 states + before/after, fictional data) |
| Staging | `1e24bf4` live since 2026-10-23 18:02 UTC (deployment `dd8b4894`) — see below |
| Owner test | `auth-ui-owner-test.md` (≈ 5 minutes) |
| PR #287, `main`, production | untouched: PR head still `200c34d`, `main` `27ed25d`, no production deploy, migration, variable or secret change |

Next: the owner reviews the page live from ChatGPT on staging. Open owner
decision: the `opentelemetry-api` lock bump (below). After approval, decide
how the branch joins `feat/chatgpt-plugin` (PR #287); launch preparation
follows `production-readiness.md`. Not started and not to start without the
owner: Plugin Directory submission, production MCP, production migrations,
the analytics dashboard.

### Mobile-first refinement and safe-daily fix — live on staging (2026-10-23)

The owner approved the mobile-first direction but blocked it on a financial
bug: `safe_daily_limit` counted the Savings line and goal reservations as
spendable. Fixed (owner decision): the forecast engine now returns
`savings_set_aside` (what set-aside lines still hold) and
`safe_daily_limit = (remaining_budget − savings_set_aside) / days_remaining`;
`get_budget_status.today` leaves set-aside lines out. The status / projection
are unchanged on purpose — see `docs/brand/AUTH-UI-DESIGN.md` ("What
remains, classified"): fixing savings there alone would read "danger" all
month for anyone who records rent on the 1st, because the pace counts rent.

* Code: `app/core/category_priority.py` (`SET_ASIDE_CATEGORIES`), the engine,
  `app/mcp/{schemas,serializers,tools/budget,queries/plan}.py`; tests
  `tests_mcp/test_spendable_forecast.py`. The engine is shared: after a merge
  the mobile app's `/api/budget/forecast` returns the corrected figure too;
  `/api/scheduled-expenses` impact still counts savings (follow-up).
* Page: mobile-first `pages.py`, example figures from the corrected engine
  (€66.70 a day with €400.00 savings kept), screenshots in `review/auth-ui-v2/`.
  Owner-approved (direction, safe-daily semantics, compact permissions,
  calendar, final visuals).
* The page shows no forecast status ("On track" removed, owner decision):
  `status` is unchanged in the MCP contract, but its linear pace counts rent
  paid on the 1st as daily spending. Not fixed — deferred to a dedicated
  forecast-engine task, with future fixed / recurring bills.
* Deferred technical debt: the mobile app's `/api/scheduled-expenses` impact
  still counts savings.
* Approved for staging on 2026-10-23 and deployed as `1e24bf4` (below).

### Staging deployment of `1e24bf4` — live since 2026-10-23 18:02 UTC

| Item | Result (2026-10-23) |
|---|---|
| Deployment | `dd8b4894-0c17-413e-920e-8a578ea2d831`, created 17:58:43 UTC, SUCCESS 18:02:06 UTC |
| Source | `teniee/mita_project` @ `feat/chatgpt-auth-ui`, pinned to `1e24bf40202f1e5e5132c63d59d9146be6f49927` by connecting the source again with the SHA (a new build, not "Redeploy"); later commits are documentation only |
| Health | `/health` ok, MCP 2.1.0; `/oauth/assets/mita-mark.svg` 200 |
| Runtime | 1 replica; connected as `mita_mcp` over the private network; alembic `0039`, no migration ran |
| Auth surface | compared with a capture of `ee388c0` taken just before the switch: status and security headers identical on 13 endpoints (sign-in, sign-up, error pages, metadata, assets), metadata identical, assets byte-identical; exactly `profile:read finance:read finance:write feedback:write profile:write`; PKCE `S256` only (plain and missing challenge refused); DCR; a foreign redirect refused at registration and at `/authorize`; no script, inline handler, `javascript:` URL or third-party resource |
| Page | phone-first order, `<details>` permissions, pacing example and calendar, no "On track"; 20 states rendered from staging: 9 pixel-identical to `review/auth-ui-v2/`, 4 differ only below the noise threshold, 7 only by the optional support link (`MCP_SUPPORT_URL` is not set on staging) |
| Safe daily, live | a synthetic account through the sign-up page: income 2,400, savings target 400, reviewed plan saved (1,785.34 over 13 lines, including the Savings line 400.00 and goal reservations 209.34 for a 900 goal due 30 November), expenses 85.60 on 23 October (Europe/Sofia, 8 days left). Forecast: `remaining_budget` 1,699.74, `savings_set_aside` 609.34, `safe_daily_limit` 136.30 = (1,699.74 − 609.34) / 8 — equal to the figure computed from the database rows (the old formula gave 212.47); `get_budget_status.today.planned` 97.05 = today's spending rows, the 41.44 set aside today left out; `status` still returned. Account deleted |
| OAuth, in memory | code replay refused; refresh rotates and the rotated-out token is refused; the code of a real sign-in is refused with the wrong PKCE verifier; tools/list = the 22 published tools; granted scopes = the five (45/45 checks with the safe-daily ones) |
| `e2e_v2.py` | 77/77 through the new sign-up page; account deleted |
| Logs | 407 lines (deploy, HTTP and build of the new deployment, the old one during the switch, Postgres): no e-mail, token, JWT, key, DB URL, code, password, synthetic amount or merchant; none of the service's 50 secret values or the 2 Postgres credential values; no query string logged |
| Cleanup | both synthetic accounts deleted with their data, plus this run's 3 token-less OAuth clients and the 22 anonymous analytics events of the account that did not opt in (the opted-in account's events cascade with it). Staging is back to 3 users, 27 transactions, 3 OAuth clients — one, registered 12:56 UTC without tokens, predates this run and was left as is. The temporary DB proxy was removed and its endpoint no longer serves Postgres |
| Not re-run | `e2e_http.py` (its restart phase keeps tokens in a state file) and `staging_failure_modes.py`: covered by the checks above, or unaffected by this change |

### CI dependency audit red on `1e24bf4` — not fixed, owner decision

`pip-audit` on `requirements-mcp.lock` now reports GHSA-xcq7-p3pf-p88h /
CVE-2026-114603 (published 2026-10-22, moderate, availability only):
`opentelemetry-api` 1.45.0 parses a W3C `tracestate` with quadratic cost;
fixed in 1.45.1. It arrives through `mcp` 2.2.0, whose OpenTelemetry
middleware extracts trace context from each request's `_meta`, so it is
reachable on authenticated `/mcp` calls. `1e24bf4` did not introduce it: the
lock is unchanged, `ee388c0`'s image carries the same version, and its CI
passed before the advisory existed. Because the audit fails first, CI skipped
the MCP security gate, full suite, image build and container e2e for
`1e24bf4`; the full suite passed locally (542). Fix: `opentelemetry-api==1.45.1`
in `requirements-mcp.lock` (one line, or `scripts/mcp/lock_deps.sh`), CI,
then a staging redeploy.

### Staging deployment of `ee388c0` — 2026-10-23 12:12 UTC (superseded by `1e24bf4`)

Railway paused all builds from 2026-10-21 (~17:00 UTC) until 2026-10-23 and
disclosed a security incident (below); the build ran once Hobby builds were
back, after the staging credentials were rotated.

| Item | Result (2026-10-23) |
|---|---|
| Deployment | `33783139-2cd3-49a8-9ec4-d166c7435404`, SUCCESS at 12:12 UTC (restarted in place 12:16 for the persistence check) |
| Source | `teniee/mita_project` @ `feat/chatgpt-auth-ui`, pinned to `ee388c02cc51883f2cf56bd68ec35571a7cef8df` (the commits after it were documentation only until `1e24bf4`) |
| Health | `/health` ok, MCP 2.1.0; `/oauth/assets/mita-mark.svg` 200 (404 on the old build) |
| Runtime | 1 replica; connected as `mita_mcp` over the private network; alembic `0039`, no migration ran |
| OAuth metadata | exactly `profile:read finance:read finance:write feedback:write profile:write`; PKCE `S256` only; DCR; exact issuer |
| `e2e_v2.py` | 77/77 through the new sign-up page; account deleted |
| `e2e_http.py` | phase 1 27/27; service restart; phase 2 22/22 (refresh token survives the restart, rotation and reuse, password change revokes access and refresh token, log checks) |
| `staging_failure_modes.py` | 24/24 |
| Auth write smoke | 26/26: two new accounts through DCR, PKCE and the sign-up page; one expense written and read back; the other account cannot see or change it; both deleted |
| Page | 12 states rendered from staging, identical to `review/auth-ui/` except the optional "Need help?" / "Help" link — `MCP_SUPPORT_URL` is not set on staging |
| Logs | 915 lines (app, HTTP, build, Postgres): no secret, token, code, password, e-mail, amount or merchant; none of the rotated values |

Staging data is back to its baseline (3 users, 27 transactions, 2 ChatGPT
clients); no TCP proxy is open.

### Railway security incident — staging recovery (2026-10-23)

Railway's disclosure of 2026-10-21: environment variables may have been read.
For staging (production is the owner's decision and was not touched):

* **Review:** no deployment between 2026-10-18 and the recovery (all by the
  owner's account); no staged change; no TCP proxy; variable names unchanged;
  HTTP 2026-10-20…23 = 3 ChatGPT token refreshes and the owner's checks; no
  failed sign-in; Postgres logs routine. Railway's audit log was not readable
  with the available tools — rotation regardless.
* **Rotated** (names only): `MCP_OAUTH_PRIVATE_KEY`, `MCP_LOGIN_CSRF_SECRET`,
  `MCP_GRANT_FINGERPRINT_SECRET`, `MCP_DATA_SECRET`, `MCP_ANALYTICS_SECRET`,
  `JWT_SECRET`, `SECRET_KEY`, `MCP_METRICS_TOKEN`; the `postgres` password
  (Railway "Regenerate", by the owner); the `mita_mcp` password and
  `DATABASE_URL`. Both old database passwords were verified as rejected.
* **Consequences:** every staging ChatGPT connection and token issued before
  2026-10-23 is invalid — reconnect; analytics pseudonyms restart.
* Procedure and checks: `staging.md` → "Credential rotation".

## Previous phase: staging acceptance — CLOSED (2026-10-19)

`staging-acceptance-v2.md` §11.

| Item | State |
|---|---|
| Staging code | `79efb1d612999339814b02b5220b7cde2a13921d`, MCP 2.1.0 |
| Staging deployment | `87d26668-4051-42c3-99b7-2036d0de42cf` (project `mita-mcp-staging`), `/health` ok, alembic 0039, role `mita_mcp`, 1 replica, database TCP proxy closed |
| Evidence | CI run `39155447750` green; public staging checks §9; real ChatGPT §8 and S-8 §11 |
| `main` | `27ed25d`, not merged |
| Production | untouched: API on `3aa52b7` at alembic 0036, no MCP service, no setting, variable or secret changed |

## PR #287 must not be merged yet

PR #287 (`feat/chatgpt-plugin` → `main`) is open, not a draft and mergeable,
and `main` has no branch protection. `mita-production` follows `main` with no
commit pin, path filter, CI gate or healthcheck, and its `start.sh` runs
`alembic upgrade head` on boot (aborting in production on failure). A merge
therefore deploys the API and applies 0037–0039 to the production database;
a failed boot leaves nothing serving, and a rollback cannot boot against the
migrated database. Merge only as `production-readiness.md` Step 7 — after
Step 1 (credential rotation) and with the healthcheck (O-11a) and pre-flight
(O-11b) done.

## Known limitations (not blockers)

* A repeated, deliberate receipt request is caught by ChatGPT's judgement;
  MITA's idempotency covers retried tool calls, not content duplicates.
* F-2: shown as one line in ChatGPT, but the ledger still books `gas` apart
  from the `transport gas` plan (backend debt).
* F-7: a future scope addition needs existing ChatGPT connections to
  re-register.
* The description on ChatGPT's own developer-mode app object is owner-managed.
* The mobile app still ships the older hand-drawn logo
  (`mobile_app/assets/logo/mitalogo.png`); the Figma guidelines and the new
  sign-in page use the geometric logomark (`docs/brand/AUTH-UI-DESIGN.md`).
