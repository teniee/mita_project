# MITA in ChatGPT — product analytics

What MITA measures about its ChatGPT app, how, and what it never stores.
Implementation: `app/mcp/analytics.py` (allow-list, keys, sink),
migration `0039` (tables and views), `scripts/mcp/analytics_report.py`
(answers without a dashboard), `scripts/mcp/analytics_reader_role.sql`
(least-privilege reader). Tests: `tests_mcp/test_analytics_db.py`,
`test_analytics_background.py`, `test_transaction_writes.py` (hygiene).

## Principles

* **Usage, not content.** One row per tool call and a few lifecycle events.
  Never prompts, responses, transcripts, receipt images, amounts, merchants,
  goal titles, feedback text, tokens, codes, passwords, raw session ids, raw
  ChatGPT subject ids, user ids or e-mail addresses.
* **Pseudonymous and consented.** `user_key` = HMAC-SHA256 of the MITA user id
  under `MCP_ANALYTICS_SECRET` (first 32 hex); `session_key` = the same HMAC of
  ChatGPT's anonymized conversation id (`_meta["openai/session"]`). Keys are
  written only for users who ticked the usage-statistics box on the MITA
  consent page (or turned it on with `set_usage_analytics`). The box starts
  unticked (owner decision 2026-10-25). On sign-in an unticked box keeps the
  account's earlier choice; it is never a withdrawal and never deletes
  anything — withdrawing is `set_usage_analytics(false)`. Everyone else
  produces rows with both keys NULL: counted for volume and reliability,
  linked to nobody. Accounts that connected before this feature have no
  choice recorded and are treated as "off".
* **Meaningful control** (OpenAI: metadata collection only if "explicitly
  disclosed, narrowly scoped, subject to meaningful user control"): the
  consent page explains it; `set_usage_analytics(false)` stops linking and
  deletes the linked history; account deletion deletes it too.
* **Out of band.** Events are queued after the tool has produced its result
  and written by one background task through its own session. A queue
  overflow or a database error drops events (logged by type); it never
  fails, slows or rolls back a financial write.
* **Read-only tools stay read-only.** Analytics is operational telemetry about
  the request, written outside the tool's `READ ONLY` transaction; the user's
  data and environment are unchanged, which is what `readOnlyHint` describes.

## Event taxonomy

`status` is `ok`/`error`. Every event carries `occurred_at`, `user_key`,
`session_key`, `surface` (`chatgpt`), `locale` (validated BCP 47 from
`openai/locale`), `server_version`, `tool_contract_version`.

| Event | Fires when | Allowed properties | Privacy class |
|---|---|---|---|
| `tool_call_succeeded` | every successful tool call (one per call) | `replayed` (bool) | usage |
| `tool_call_failed` | every failed call; `error_code` = auth, forbidden, validation, rate_limited, unavailable, internal, invalid_arguments (rejected by the SDK before the tool ran; always unlinked) | — | usage |
| `account_created` | a new account is created on the consent page | — | lifecycle |
| `oauth_connected` | an authorization code is issued after sign-in or sign-up | `new_account` | lifecycle |
| `onboarding_started` | `get_setup_status` reports setup incomplete (may repeat; funnels use the first) | — | lifecycle |
| `onboarding_completed` | a write makes setup complete (income, currency, timezone and a plan for the month) | — | lifecycle |
| `financial_profile_created` / `_updated` | `update_financial_profile` changed fields (first time / later) | `fields` (field names only) | lifecycle |
| `transaction_created` / `transaction_batch_created` | expenses recorded | `entry_method`, `item_count` | usage |
| `transaction_updated` / `transaction_deleted` | a correction | `fields` (names only) | usage |
| `receipt_flow_completed` | expenses recorded with `entry_method = receipt_image` | `item_count` | usage |
| `budget_previewed` | a preview was built | `month_offset`, `existing_plan` | usage |
| `budget_saved` / `budget_replaced` | a reviewed plan was saved (new / replacing) | `month_offset` | lifecycle |
| `recurring_expense_created` | an obligation was saved | `recurrence` | usage |
| `savings_goal_created` | a goal was created | `has_target_date` | usage |
| `feedback_submitted` | feedback was sent | `type`, `feature_area`, `rating` | usage (the text stays in `product_feedback`) |
| `usage_analytics_enabled` | the user turned statistics on | — | consent |

"Feature used" metrics (budget status, forecast, history, period comparison,
recurring, goals) are not separate events: they are `tool_call_succeeded`
rows by `feature`/`tool_name`/`intent_code`, so nothing is double-counted.

**Intent codes** come from the tool and its bounded arguments only (never a
prompt): `onboarding`, `profile_update`, `account`, `create_transaction`,
`create_batch`, `edit_transaction`, `delete_transaction`, `list_transactions`,
`create_budget`, `save_budget`, `budget_status`, `forecast`,
`monthly_summary`, `category_breakdown`, `compare_periods` (history ≤ 2
months), `category_trend` (history with a category), `six_month_overview`,
`create_recurring`, `upcoming_expenses`, `create_goal`, `goal_progress`,
`privacy_setting`, and the feedback type (`feature_request`, `bug_report`,
`confusing`, `praise`, `other`).

**Features** (`TOOL_FEATURES`): account, setup, summary, transactions,
spending, budget_status, forecast, budget_plan, recurring, goals, history,
feedback, privacy.

## Definitions

* **Active user (DAU/WAU/MAU):** a `user_key` with at least one tool call that
  day / in the last 7 / 30 days (UTC days). Unlinked calls never count as users.
* **Weekly Financially Active User (WFAU):** a user with at least one
  *successful* call in the last 7 days to a financial feature — transactions,
  summary, spending, budget_status, forecast, budget_plan, recurring, goals or
  history (not account, setup, feedback or privacy). North-star companions:
  WFAU / MAU, and D30-retained WFAU.
* **Session:** a distinct `session_key` (one ChatGPT conversation).
* **Activation funnel** (`analytics.user_firsts`, first occurrence per user):
  OAuth connected → setup started → profile saved → budget previewed → budget
  saved → first transaction → setup completed.
* **Retention:** D1/D7/D30 = active exactly 1/7/30 days after the first event,
  over users old enough to be measured (`*_eligible`). Weekly cohorts in
  `analytics.retention_weekly` (cohort week = week of first event).
* **Lifecycle segments** (`analytics.user_segments`, thresholds in
  `analytics.segment_thresholds`, change with an UPDATE): NEW (first seen
  < 7 days), POWER (≥ 20 financially active days in 30), ENGAGED (≥ 8),
  DORMANT (no activity for ≥ 30 days), AT_RISK (engaged in the previous 30
  days but inactive ≥ 14 days), ACTIVATED (setup completed and a saved budget
  or ≥ 3 recorded expenses), otherwise CASUAL. Activity counts only; no
  sentiment or behavioural labels.

## Views (schema `analytics`)

| View | Answers |
|---|---|
| `tool_calls` | every call with its day, feature, tool, status, latency |
| `user_daily` | per user per day: sessions, calls, successes, failures, features, financially active |
| `feature_daily` | per feature per day: users, calls, successes, failures, p50/p95 latency |
| `activity_daily` | last 90 days: DAU, WAU, MAU, WFAU, calls, sessions |
| `user_firsts`, `activation` | funnel milestones per user / per cohort day |
| `retention_weekly`, `retention_days` | cohorts; D1/D7/D30 with eligibility |
| `feature_adoption` | every feature (also unused ones): users, % of MAU, calls, calls/user, repeat %, D30 repeat % |
| `user_segments` | segment per user key |
| `reliability_daily` | per tool per day: calls, failures by class, p50/p95 latency |
| `registrations_daily` | all MITA registrations per day (counts only, app and ChatGPT) |
| `feedback` | feedback with type, area, rating, status, theme, notes and the user's key (if they consented) — no user id |
| `storage` | row estimates and bytes for the main tables (capacity) |

Plain views, always fresh. At early-stage volumes they answer in
milliseconds (see `capacity-plan.md`); Metabase's own result cache is the
first lever before any materialized view.

## Dashboards (Metabase)

Connect Metabase to PostgreSQL with the `mita_analytics_reader` role (can read
`analytics` only; read-only; 30 s statement timeout). Never expose Metabase
without its login. Pages and their queries:

1. **Overview** — `activity_daily` (DAU, WAU, MAU, WFAU, DAU/MAU, sessions,
   calls/user), `retention_days` (D1/D7/D30), `tool_calls` (success rate, p95).
2. **Onboarding** — `activation` and `user_firsts` as a funnel.
3. **Feature adoption** — `feature_adoption` as a table, zeros included.
4. **Engagement** — distributions from `user_daily` (calls/user, sessions/user,
   active days/month), `user_segments` counts.
5. **Retention** — `retention_weekly` as a cohort grid.
6. **Reliability** — `reliability_daily` per tool.
7. **Feedback** — `feedback` by type, area, rating, status, theme.
8. **Cost/capacity** — `storage`, events per day from `tool_calls`.

Until Metabase is set up, `scripts/mcp/analytics_report.py --database-url
<reader DSN>` prints the same core answers.

## Deletion and retention

* Account deletion cascades `analytics_identities` → every linked event, and
  `product_feedback`, `mcp_user_profiles`, `mcp_idempotency_keys`.
* `set_usage_analytics(false)` deletes the identity link and with it every
  linked event; later calls are unlinked.
* Unlinked events (no key) remain: they cannot be tied to anyone.
* No automatic purge of linked events exists yet; a retention period is an
  owner/legal decision (see `data-inventory.md`).
