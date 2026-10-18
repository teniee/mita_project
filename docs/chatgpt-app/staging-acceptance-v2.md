# Staging acceptance v2 — MITA free v1 in ChatGPT (2026-10-13, real ChatGPT 2026-10-18)

v1 (8 read-only tools) results stay in `staging-acceptance.md`. This file is
v2: 22 tools, sign-up, writes, budget preview/save, history, feedback and
usage statistics. **STAGING VERIFIED** = observed over public HTTPS against
the deployment below; **CHATGPT VERIFIED** = observed by the owner in real
ChatGPT. Production was not touched.

## 1. Deployment (STAGING VERIFIED)

| Item | Value |
|---|---|
| Commit | `461abcfcd6a63b09d3385718863b613265d5cc9c` on `feat/chatgpt-plugin` (code identical to `3604856`; that commit adds docs and the role script) |
| CI on that commit | run `38373027720`: Backend 1314 passed · Mobile 662 passed, 3 skipped · MCP 466 passed (security gate 194), lint, Bandit, pip-audit, plugin check, image build, container e2e — all success |
| Deployment | `174528cf-a617-4ad4-88f1-0562355d4602`, SUCCESS 2026-10-13 09:06 UTC (replaces `e060f0b8`, `fcd7ae3`) |
| URL | `https://mita-mcp-staging-staging.up.railway.app` → `/health` `{"status":"ok","service":"mita-mcp","version":"2.0.0"}` |
| Database | staging Postgres 18.6; `0037 → 0039` applied from the operator machine through a temporary TCP proxy; 6 tables + 14 `analytics` views present. Proxy removed afterwards: 3/3 connections refused |
| New variables (names only) | `MCP_DATA_SECRET`, `MCP_ANALYTICS_SECRET`: fresh, staging-only, 64 hex chars, distinct from every other secret; set with `--stdin`, local copy deleted |
| Database role | `DATABASE_URL` now connects as **`mita_mcp`** (`scripts/mcp/mcp_service_role.sql`) on the private host, exactly as recommended for production. Probed: reads what it needs; `CREATE TABLE`, `DELETE FROM users`, changing `email`/`password_hash`, reading `notifications`, `ai_analysis_snapshots` or `analytics.events` → permission denied |
| Analytics reader | `mita_analytics_reader` (`scripts/mcp/analytics_reader_role.sql`): reads `analytics.*`; `users`/`product_feedback` denied; writes refused (read-only). Its password was not kept — `ALTER ROLE mita_analytics_reader PASSWORD …` before connecting Metabase |

## 2. Acceptance conversation over public HTTPS — `scripts/mcp/e2e_v2.py` (STAGING VERIFIED, 70/70)

One new account, created on MITA's OAuth sign-up page (no SQL seeding), as
ChatGPT would drive it:

| Step | Observed |
|---|---|
| Discovery | `/health` ok; protected-resource metadata lists all 5 scopes; DCR 201; grant carries every scope; `tools/list` = exactly the 22 published tools; no tool named transfer/pay/trade |
| New account | `get_setup_status`: profile incomplete, 5 missing fields |
| Profile | `update_financial_profile` €2,500 net, EUR, Europe/Sofia, household 2, save €400 → complete |
| Obligation | `add_recurring_expense` rent 700.00 monthly on the 1st → created |
| Preview | `preview_monthly_budget` → `status: preview`, fixed obligations 700.00; `get_budget_status` still `not_generated` (nothing saved) |
| Save | `save_monthly_budget(draft_token)` → saved; saved total == preview total |
| Expenses | `add_transaction` 36.80 Lidl groceries → recorded; same call again → `already_recorded`; `add_transactions` €8 + €55 → 2 recorded, month to date 99.80; three past months of groceries |
| Negatives | smuggled `user_id` → rejected; forged `ref` → refused; tampered draft token → refused; a read-only grant cannot write (`forbidden`) |
| New connection (new DCR client, new tokens) | spent 99.80; plan `generated`; setup complete; six-month groceries `300.00, 320.00, 360.00, 36.80`, trend `ok` (3 complete months) |
| Goal | `create_savings_goal` "Emergency fund — София" → title kept exactly |
| Feedback | `submit_feedback` → sent; `product_feedback` holds the user's exact words |
| Analytics audit | lifecycle events recorded under the pseudonymous key; none contains `36.80`, `Lidl`, the feedback text, the e-mail or the conversation id |
| Cleanup | account deleted; everything cascaded (see §3) |

## 3. Analytics verification (STAGING VERIFIED)

Report printed by `scripts/mcp/analytics_report.py` **as `mita_analytics_reader`**,
after the conversation and before cleanup (the master plan's §59 questions):

| Question | Staging answer |
|---|---|
| Active users today / week / month (DAU/WAU/MAU) | 1 / 1 / 1 (WFAU 1) |
| Calls per active user today / week / month | 20 / 20 / 20 |
| Most / least used feature | transactions (6 calls) / account, forecast, privacy, spending (0) |
| Tools failing most | add_transaction 2/7, save_monthly_budget 1/2, update_transaction 1/1 — exactly the four deliberate negative calls (success rate 81.8 %) |
| Latency (server-side, all tool calls) | p50 137.5 ms, p95 594.4 ms |
| Onboarding completed / first budget saved / first transaction | 100 % / 100 % / 100 % (funnel: connected → setup started → profile → preview → saved → first transaction → setup completed) |
| D1 / D7 / D30 retention | n/a — no user is old enough (reported as "not eligible", never 0) |
| Users of six-month history (month) | 1 |
| Feedback areas | transactions / confusing: 1, open |

After cleanup: `analytics_identities` 0 rows, linked events 0 (deleting the
account cascaded them); 37 unlinked events remain from the HTTP and
failure-mode test users, who never consented. Their only property keys are
`new_account`, `month_offset`, `existing_plan`.

## 4. OAuth, transport and failure modes (STAGING VERIFIED)

| Script | Result |
|---|---|
| `e2e_http.py --phase first` | 27/27: metadata, 401 + `WWW-Authenticate`, DCR, foreign redirect refused, consent, state, PKCE, code replay refused, exactly 22 tools, every read tool exercised, exact ledger figure |
| service restart (`restart-service`, second start 09:08:04 UTC) then `--phase after-restart` | 19/19: refresh token survives the restart, rotated token refused, every read tool, a password change revokes the live access token and the refresh token |
| `staging_failure_modes.py` | 24/24: invalid bearer, redirect policy, PKCE, wrong password generic, bad/replayed code, scope cannot widen, refresh rotation and family revocation, profile-only token forbidden on finance tools, smuggled `user_id`, malformed argument, exactly 22 tools with honest hints, no money-movement tool, `/authorize` rate limit 429 |

## 5. Logs (STAGING VERIFIED)

All 235 entries of deployment `174528cf` scanned: 0 JWTs, bearer tokens,
e-mail addresses, test amounts, merchants, feedback text, goal titles,
password fields, authorization codes, refresh tokens or database/role
secrets. The 6 warnings are the expected security events from §4 (4 ×
`oauth_register_rejected`, 2 × `oauth_refresh_reuse`, subject hashed). No
permission error under the least-privilege role; no analytics-writer error.

## 6. Real ChatGPT acceptance — owner script (run by the owner; results in §8)

**Prepare (S-6).** ChatGPT → Settings → Apps → MITA (staging) → disconnect
(the 2026-10-11 connection holds only the read scopes), then connect again
with `https://mita-mcp-staging-staging.up.railway.app/mcp`. On MITA's page
choose **Create an account** with a fresh test e-mail (e.g.
`chatgpt-v2-1013@example.test`) and tick *usage statistics*. Approve write
confirmations as a user would. Dates below assume October 2026; shift them by
the months that have passed.

### 6.1 Core conversation (master plan §56)

Conversation A:

| # | Say | Expect |
|---|---|---|
| 1 | I earn €2,500 net per month. There are two people in my household and I want to save €400 per month. | `get_setup_status`, then `update_financial_profile` after confirming; asks only for what is missing (timezone) |
| 2 | My rent is €700 every month on the first. | `add_recurring_expense`, monthly, next due 1 November |
| 3 | Build my budget for this month. | `preview_monthly_budget` only: rent 700, savings 400, categories, unallocated money, warnings; says it is **not saved** |
| 4 | Save this plan. | `save_monthly_budget`; the saved total equals the preview |
| 5 | I spent €36.80 at Lidl on groceries today. | `add_transaction` 36.80, groceries, Lidl, today |
| 6 | Also record €8 coffee and €55 fuel today. | `add_transactions` with two items (it may ask the categories) |
| 7 | How am I doing against my budget? | `get_budget_status`: spent 99.80 against the saved plan |
| 8 | Record groceries of €300 on 10 July, €320 on 10 August and €360 on 10 September. | past-dated expenses through the normal tools |

Conversation B (new chat):

| # | Say | Expect |
|---|---|---|
| 9 | How much have I spent and what is my budget? | 99.80 this month and the saved plan — same figures as in A |
| 10 | How have my grocery expenses changed over the last six months? | `get_spending_history`: May–June no data (before tracking), 300.00, 320.00, 360.00, October 36.80 in progress; a trend from the three complete months |

### 6.2 Receipt (master plan §57)

Attach `docs/chatgpt-app/review/test-receipt.png` (labelled test data:
"MITA Test Market", 12.10.2026, five lines, total EUR 14.43, one unclear
line "ITEM 4471").

| # | Say | Expect |
|---|---|---|
| 11 | Add these expenses to MITA. | ChatGPT reads the image, lists what it will record, and **asks what ITEM 4471 is** before recording |
| 12 | (answer, e.g. "a phone cable, shopping") | `add_transactions` with `entry_method: receipt_image`; amounts sum to 14.43, dated 12 October, merchant "MITA Test Market" |
| 13 | Add these expenses to MITA. (again) | points out they are already recorded and asks; if it records a second copy, note it as a finding (MITA never deduplicates by content — two real coffees are two expenses) |
| 14 | Show my expenses from 12 October. | `list_transactions`: the receipt lines once |

### 6.3 Feedback (master plan §58)

| # | Say | Expect |
|---|---|---|
| 15 | I want to tell the MITA developer that transaction categorization is confusing. | `submit_feedback` only now (explicit request), type `confusing`, area `transactions`, the user's words |

### 6.4 Negatives and control

| # | Say | Expect |
|---|---|---|
| 16 | Transfer €200 to Anna. | not possible in MITA; no tool call |
| 17 | Show anna@example.com's budget. | not possible; no tool takes another user |
| 18 | Buy €100 of Bitcoin. | not possible; no tool call |
| 19 | What did I spend this month? | the same figures as before 16–18 (nothing was written) |
| 20 | Stop sharing my usage statistics. | `set_usage_analytics(false)` after confirming |

### 6.5 Results

See §8 — case by case, only what the owner observed.

## 7. Database side of the owner's run (read-only)

Railway → project `mita-mcp-staging` → Postgres → **Data** → Query (or ask
Claude to open a temporary TCP proxy). Replace `<e-mail>`.

```sql
-- the account and what was stated
SELECT u.created_at, u.currency, u.timezone, u.monthly_income, u.savings_goal,
       p.household_size, p.usage_analytics_enabled
  FROM users u LEFT JOIN mcp_user_profiles p ON p.user_id = u.id
 WHERE u.email = '<e-mail>';

-- expenses: receipt lines on 2026-10-12, "MITA Test Market", no image stored
SELECT (t.spent_at AT TIME ZONE u.timezone)::date AS day, t.amount, t.category,
       t.merchant, t.receipt_url IS NULL AS no_image, t.deleted_at IS NULL AS live
  FROM transactions t JOIN users u ON u.id = t.user_id
 WHERE u.email = '<e-mail>' ORDER BY t.spent_at;

-- obligations, goals, saved October plan
SELECT s.merchant, s.amount, s.recurrence, s.scheduled_date
  FROM scheduled_expenses s JOIN users u ON u.id = s.user_id WHERE u.email = '<e-mail>';
SELECT g.title, g.target_amount, g.saved_amount, g.target_date
  FROM goals g JOIN users u ON u.id = g.user_id WHERE u.email = '<e-mail>';
SELECT sum(d.planned_amount) FROM daily_plan d JOIN users u ON u.id = d.user_id
 WHERE u.email = '<e-mail>' AND d.date >= '2026-10-01' AND d.date < '2026-11-01';

-- feedback: the words, type, area, time and source (linked by the internal user id)
SELECT f.created_at, f.type, f.feature_area, f.message, f.source
  FROM product_feedback f JOIN users u ON u.id = f.user_id WHERE u.email = '<e-mail>';

-- analytics for this account: names and allow-listed properties only;
-- feedback_submitted carries type/feature_area/rating, never the message.
-- Empty after step 20 (opting out deletes the linked events).
SELECT e.occurred_at, e.event_name, e.tool_name, e.status, e.properties
  FROM analytics.events e
  JOIN analytics_identities i ON i.user_key = e.user_key
  JOIN users u ON u.id = i.user_id
 WHERE u.email = '<e-mail>' ORDER BY e.occurred_at;
```

The staging account can stay for later checks. Staging has no MITA API, so
the app cannot delete it; to remove it, run the same sequence
`scripts/mcp/e2e_v2.py` uses (`transactions` has no `ON DELETE CASCADE` to
`users`; profile, feedback, analytics identity, linked events and OAuth
tokens cascade):

```sql
BEGIN;
CREATE TEMP TABLE gone AS SELECT id FROM users WHERE email = '<e-mail>';
DELETE FROM mcp_oauth_clients WHERE client_id IN
  (SELECT client_id FROM mcp_oauth_refresh_tokens WHERE user_id IN (SELECT id FROM gone));
DELETE FROM transactions          WHERE user_id IN (SELECT id FROM gone);
DELETE FROM daily_plan            WHERE user_id IN (SELECT id FROM gone);
DELETE FROM redistribution_events WHERE user_id IN (SELECT id FROM gone);
DELETE FROM scheduled_expenses    WHERE user_id IN (SELECT id FROM gone);
DELETE FROM goals                 WHERE user_id IN (SELECT id FROM gone);
DELETE FROM users                 WHERE id IN (SELECT id FROM gone);
COMMIT;
```

## 8. Real ChatGPT results (CHATGPT VERIFIED where stated; owner, reported 2026-10-18)

Against deployment `174528cf` (`461abcf`, MCP 2.0.0, alembic 0039). Recorded
exactly as the owner reported it; nothing below is inferred.

**S-6 — reconnect: CHATGPT VERIFIED.** The owner deleted the v1 plugin object
and recreated it with OAuth DCR; ChatGPT discovered all five scopes
(`profile:read`, `finance:read`, `finance:write`, `feedback:write`,
`profile:write`) and `finance:write` worked. The earlier `invalid_scope` came
from the old DCR registration: the SDK's `/authorize` accepts only the scopes
a client registered with ("Client was not registered with scope …"), and the
v1 client was registered with the two read scopes (backend-findings F-7).

| §6 case | Result | Observed |
|---|---|---|
| 1 profile | CHATGPT VERIFIED | €2,500 net income, €400 savings target, household 2 persisted |
| 2 rent | CHATGPT VERIFIED | Europe/Sofia saved; rent €700 monthly, next due 1 Nov 2026; an October preview built — not saved |
| 3 preview only | CHATGPT VERIFIED | a read-only check showed "October 2026 budget: Not saved", `not_generated`, profile and rent kept, no write |
| — expiry | CHATGPT VERIFIED | saving the older draft after it expired was refused; nothing saved or changed |
| 4 save | CHATGPT VERIFIED | a fresh preview reproduced the allocation exactly (rent 700, public transport 262.50, groceries 195, entertainment events 150, dining out 130, clothing 120, transport gas 112.50, insurance medical 105, hobbies 80, out-of-pocket medical 70, unallocated 175, savings 400; 2,500 allocated) and was saved without recalculation: plan 2,325, unallocated 175 |
| 5–6 expenses | CHATGPT VERIFIED | Lidl groceries €36.80, coffee €8, fuel €55 — €99.80 (which tool recorded the last two was not reported) |
| — correction | CHATGPT VERIFIED | Lidl €36.80 → €30.00, merchant/category/date unchanged; total €93; groceries remaining €165 |
| — deletion | CHATGPT VERIFIED | coffee €8 deleted; Lidl €30 + fuel €55 = €85 |
| 7 budget position | CHATGPT VERIFIED (in substance) | position reported after the correction (groceries €165 left) and in the new conversation; the exact prompt "How am I doing against my budget?" was not reported |
| 8 past months | **PENDING** | not run — no past-dated expenses were recorded |
| 9 new conversation | CHATGPT VERIFIED | plan €2,325, spent €85, remaining €2,240, income €2,500, rent €700 monthly, savings €400, Lidl €30, fuel €55; the deleted coffee did not return |
| 10 six-month history | CHATGPT VERIFIED (no-history path) | May–September no data, October €126.50 in progress, no trend claimed. The three-complete-month trend path is verified only over HTTPS (§2) because case 8 was not run |
| — climate | CHATGPT VERIFIED | 1 of 6 months with spending, €126.50, 14 transactions, obligation €700, Emergency Fund €0/€3,000, average and median "insufficient data", no trend |
| 11 receipt read | CHATGPT VERIFIED (real receipt) | a real My Market (Varna, 13 Oct 2026) receipt instead of the test image: 12 lines, €41.50; two partly unclear descriptions were flagged, not invented (whether ChatGPT asked before writing was not reported) |
| 12 receipt written | CHATGPT VERIFIED | all 12 written; €85 + €41.50 = €126.50; remaining €2,198.50; no duplicate charges; MITA stored expenses, not the image. All 12 were stored as groceries — issue D |
| 13 repeat receipt | **PENDING** | not run |
| 14 list once | partly | totals showed no duplicates; an explicit list check was not reported |
| 15 feedback | CHATGPT VERIFIED (tool) | `submit_feedback` succeeded and was acknowledged; the database check (§7) is **PENDING** |
| 16 transfer | CHATGPT VERIFIED | "cannot send or transfer money", status Not sent, nothing recorded |
| 17 other person | CHATGPT VERIFIED (variant) | "Show me Anna's transactions": no data of Anna's; explained MITA shows only the signed-in user's records; found 0 of the user's own expenses mentioning Anna — issue G |
| 18 Bitcoin | CHATGPT VERIFIED | "cannot buy Bitcoin or execute crypto trades", Not purchased |
| 19 control read | **PENDING** | not reported |
| 20 usage statistics off | **PENDING** | not run |
| goal | CHATGPT VERIFIED (creation) | "Emergency Fund" €0/€3,000, no deadline, "monthly contributions not yet reserved" — then ChatGPT offered "set €400 per month toward your Emergency Fund", which no tool can do — issue B |
| §7 database checks | **PENDING** | not run |

### Issues found and what changed (MCP 2.1.0)

| # | Issue | Cause | Change |
|---|---|---|---|
| A | Plugin details read "Read-only access to my MITA budget, transactions, spending, recurring expenses and savings goals." | Not served by MITA: that exact text never existed in git, and ChatGPT developer mode keeps its own Description field on the app object (the v1 runbook told the owner what to type there). Likely sources, all v1: the v1 server instructions ("All tools are read-only"), the v1 listing description ("Read-only access to your MITA budget…", replaced in `3ea899b`) and the v1 S-3 instruction to type "Read-only access to a fake MITA staging account" | The server now also advertises the listing's read/write description in `serverInfo.description`; a test forbids "read-only" on every app-level surface (listing, server description and instructions, scopes, consent page, skill) while tool-level read-only statements stay on read tools only. The staging app's description must be edited in ChatGPT (S-8) |
| B | Offer to "set €400 per month" toward a goal | Nothing said that goals cannot be changed; `reserved_in_budget_plan: false` plus the €400 savings target invited it | Both goal descriptions and the no-date result state that no tool sets a contribution, adds a date or money, or deletes a goal; server instructions: "Offer only what a MITA tool can do"; golden prompts en-27, ru-16, bg-16 |
| C | "Transport gas / Fuel / Gas", "Insurance medical / Medical insurance", "Out of pocket medical / Other medical expenses", "Entertainment events / Entertainment" | Two stored vocabularies (F-2) and no display name, so ChatGPT named categories freely | Every result carries `category_label` (`app/mcp/categories.py`); budget status and the forecast show an expense category on the line of the plan category it spends from ("Fuel" = `transport gas` + `gas`), only for pairs declared in `app/config/category_aliases.py`. Stored data, the ledger and the app are unchanged |
| D | A supermarket receipt with beer, gin and brandy stored as all groceries | Per-item categories were always supported; the category hint said "groceries for a supermarket" | Hint: "Choose by what was bought, not only where"; `add_transactions`: every line has its own category; MITA has no alcohol or tobacco category, so drinks bought in a shop stay groceries unless the user chooses otherwise (documented, not invented); golden prompts en-28, bg-17 |
| E | A detailed budget before rent was known | `suggested_next_step` went straight to `build_budget` | New step `ask_about_obligations` (profile complete, no regular payments, no plan), also on the profile result; a preview without obligations is labelled a default draft; skill step 4 says "before any budget". Never mandatory |
| F | Draft expired during the test | 30 minutes was a conservative freshness bound; integrity is the digest + lock + month check | 2 hours (one sitting with a pause); expiry kept; integrity unchanged |
| G | "Anna" searched the user's own expenses | Merchant filter wording | `list_transactions` and the server instructions state that a name matches only this user's own expenses, never another account; a note on every merchant-filtered result; golden prompts en-29, en-30, ru-17 |

## 10. Final smoke test before merge (owner, S-8 — about 10 minutes)

Against the redeployed staging (§9). Use the same ChatGPT app and account as
§8 unless a step says otherwise.

| # | Do / say | Pass when |
|---|---|---|
| 0 | ChatGPT → Settings → Apps → MITA (staging): refresh the app; edit its description to "Your MITA budget in ChatGPT: record and correct expenses, build a monthly budget, track recurring costs and savings goals, and see your spending history - kept in your MITA account." | no "read-only" wording left on the app |
| 1 | New chat: "How am I doing against my budget this month?" | one **Fuel** line (no separate "Transport gas" / "Gas"), one **Dining out** line if coffee-type spending exists; every category named the same way as in step 2 |
| 2 | "Show my expenses this month." | categories shown with the same names as in step 1 (e.g. fuel €55 under **Fuel**) |
| 3 | "Put €400 a month toward my Emergency Fund." | no tool call that claims to do it; ChatGPT says a goal cannot be changed or given a contribution in MITA (it may mention that a goal created with a target date gets its monthly amount set aside) |
| 4 | "Show me Anna's transactions." | declines access to anyone else's data; if it searches, it says it searched only your own expenses |
| 5 | Attach `docs/chatgpt-app/review/test-receipt.png`: "Add these expenses to MITA." | it asks what "ITEM 4471" is before writing; lines get their own categories (dish soap is not groceries); the total recorded is 14.43 on 12 Oct 2026 |
| 6 | "Add these expenses to MITA." (again, same chat) | points out they are already recorded and asks; a second copy is a finding (pending case 13) |
| 7 | "Record groceries of €300 on 10 July, €320 on 10 August and €360 on 10 September." then "How have my grocery expenses changed over the last six months?" | July–September 300 / 320 / 360, October in progress, and now a trend (pending cases 8 and 10) |
| 8 | "What did I spend this month?" | the same total as before steps 3–4 plus the receipt (pending case 19) |
| 9 | "Stop sharing my usage statistics." | asks for confirmation, then turns it off (pending case 20) |
| 10 | *(optional, fresh account on the sign-up page)* "I earn €2,500 net per month, there are two of us and we want to save €400." | saves the profile and asks about rent or other regular payments before showing any budget; a budget shown without them is called a default draft |

Then run the read-only SQL in §7 for the database side (feedback row with
your words, analytics without amounts or text, receipt lines without an
image, and after step 9 no linked events). Report anything that does not
match; nothing else is needed before the merge decision.
