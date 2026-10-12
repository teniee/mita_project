# MITA free v1 in ChatGPT — implementation plan (Gate 1, 2026-10-11)

Scope: the owner's master plan for the read/write ChatGPT app. This file is
the single plan of record; tool details live in `tool-catalog.md`, analytics
in `product-analytics.md`, data handling in `data-inventory.md`, conversation
rules in `dialogue-contract.md`. Production is untouched in this milestone.

## Baseline (before any change)

* Branch `feat/chatgpt-plugin` at `2b5a349` (= origin), MCP suite **259
  passed** locally (`PYTHONPATH=. .venv-mcp/bin/pytest -c tests_mcp/pytest.ini tests_mcp`).
* Production schema at `0036`; staging at `0037`; staging service pinned to `fcd7ae3`.

## Architecture (unchanged shape)

```
ChatGPT ─ OAuth 2.1 (MITA consent page: sign in OR create account)
        └ MCP /mcp (stateless)  ─ McpRuntime: token → user → scope → limit
                                   ├ read tools  : READ ONLY transaction
                                   └ write tools : one read-write transaction per call
                                        └ shared domain layer (app/services, expense_tracker,
                                          monthly_plan_service, budget_logic, goal sync,
                                          scheduled_expense_service, transactions.services)
                                             └ PostgreSQL (financial source of truth)
        analytics sink (out of band, after the call) → analytics.events
```

Mobile keeps `Flutter → REST → same domain → same database`. The MCP service
never calls REST endpoints.

### Findings that shape the design (code read on 2026-10-11)

| Finding | Consequence |
|---|---|
| The MCP image deliberately excludes fastapi, firebase_admin, bleach, sentry. `app.api.transactions.services` imports Firebase at module top; `TxnIn`/`FinancialConstants` live in `app.core.validators` (bleach, fastapi); both password policies live in modules that import fastapi/sentry. | Extract dependency-free pieces instead of growing the image: `FinancialConstants` → `app/core/financial_constants.py` (re-exported by validators), password policy → `app/core/password_policy.py` (used by `SecurityUtils`), the large-transaction notification import becomes lazy. Behavior of the API is unchanged. |
| `commit_transaction_to_ledger` commits per transaction. | New sibling `add_transactions_to_ledger` (no commit; the existing function is re-expressed through it), so a batch and its idempotency record are one unit of work. |
| `update_transaction` mutates `spent_at` to local time after its commit. | Tool write sessions commit explicitly and roll back on exit, so that mutation can never be flushed. |
| Budget engine: `generate_budget_from_answers` (income, fixed expenses, savings, region profile) → `_build_month_calendar` → `save_calendar_for_user` → `rebuild_month_plan`. Fixed obligations are laid out by the canonical distributor (rent on the 1st; categories without a rule spread over weekdays). | Preview and save reuse exactly these; no LLM, no new allocation rule. Region = `user.region or user.country` as the rollover path does; accounts created in ChatGPT have no region → DEFAULT profile. |
| REST goal creation is Premium-only and a second goal with a target date hits F-1 (unique key on `goal_savings` rows). | v1 is free: `create_savings_goal` has no Premium gate. Goal reservation sync runs in a SAVEPOINT and is non-blocking, exactly like the REST route, so F-1 cannot fail goal creation. F-1 itself stays a documented backend defect. |
| Plan categories (`dining out`, `transport public`) differ from transaction categories (`dining`, `transportation`) — F-2. | Reported as stored; documented limitation. Not redesigned in this milestone. |
| REST `/register` already answers "An account with this email address already exists". | The ChatGPT page uses one generic message and hashes before the lookup (no timing split); the existing mobile oracle is documented, not widened. |
| No `household_size` anywhere; `users` defaults (USD, UTC, 0) cannot be told apart from user choices. | Table `mcp_user_profiles`: household size, per-field "confirmed" timestamps, usage-analytics choice. Existing `users` columns stay canonical for income, currency, timezone, savings. |
| OpenAI: no invocation id in `_meta`; `openai/session` = anonymized conversation id; `destructiveHint` = "may delete or overwrite user data"; metadata collection only if "explicitly disclosed, narrowly scoped, subject to meaningful user control"; no raw location fields in input schemas; starter prompts ≤ 3 × 128 chars; `onboardingSkill: "./skills/setup/SKILL.md"`. | Idempotency key is a tool argument (scoped by user, operation and hashed session); overwrite tools are destructive; analytics needs disclosure + a user switch; no location input; plugin package gains the setup skill. |

## Tool set (22)

Read (`readOnlyHint` true): `get_profile`, `get_setup_status`,
`get_financial_summary`, `list_transactions` (now paginated with
`next_cursor` and returns an opaque `ref`), `get_spending_breakdown`,
`get_budget_status`, `get_budget_forecast`, `get_recurring_expenses`,
`get_goals`, `get_spending_history`, `get_financial_climate`,
`preview_monthly_budget` (stateless signed draft — writes nothing).

Write: `update_financial_profile` (overwrites → destructive),
`add_transaction`, `add_transactions` (additive, idempotency key),
`update_transaction`, `delete_transaction` (destructive),
`save_monthly_budget` (may replace a plan → destructive),
`add_recurring_expense`, `create_savings_goal` (additive, idempotency key),
`submit_feedback` (additive, idempotency key), `set_usage_analytics`
(turning it off deletes linked usage data → destructive).

Scopes: existing `profile:read`, `finance:read`; new `finance:write`,
`feedback:write`, `profile:write`. Grants made before this change hold only
the read scopes; write tools answer `insufficient_scope`, so ChatGPT asks the
user to reconnect.

## Migrations (after 0037, never editing it)

* `0038` — `mcp_user_profiles`, `mcp_idempotency_keys` (Gates 2–3).
* `0039` — `product_feedback`, `analytics_identities`, schema `analytics`
  (`events` + aggregate views) (Gate 7).
* `0040` — only indexes that EXPLAIN on the 600k benchmark justifies (Gate 8).

All additive, FK `ON DELETE CASCADE` to `users`, rehearsed up → down → up on a
scratch database. The least-privilege analytics reader role is an
operator-run SQL script, not a migration (roles are cluster-wide).

## New configuration

`MCP_DATA_SECRET` (keys for transaction refs, budget drafts, list cursors)
and `MCP_ANALYTICS_SECRET` (pseudonymous analytics keys; must stay stable),
both ≥ 32 chars, distinct from each other and from the CSRF / grant secrets.
`MCP_REGISTRATIONS_PER_HOUR` (per IP, default 5).

## Gates and status

| Gate | Content | Status |
|---|---|---|
| 1 | Inspection, this plan, baseline | done |
| 2 | OAuth registration, scopes, `get_setup_status`, `update_financial_profile` | done — 0038 rehearsed up→down→up; MCP 299 passed; backend auth/ledger subsets 438 passed |
| 3 | Transaction writes + corrections, idempotency, recurring, goals | done — `22e32af` (transactions), Gate 3 completion commit; MCP 413 passed |
| 4 | Preview → signed draft → save | done — reviewed == saved per category and per day; MCP 430 passed |
| 5 | History, climate, pagination | done — exact six-month figures, explicit completeness, survives new sessions; MCP 438 passed |
| 6 | Setup skill, starter prompts, dialogue contract, golden prompts | done — skill packaged and validated, 51 golden prompts (en/ru/bg); MCP 451 passed |
| 7 | Analytics schema/sink/views, feedback, Metabase prep | — |
| 8 | 600k benchmark, EXPLAIN, indexes | — |
| 9 | Full CI | — |
| 10 | Staging deploy + public E2E; real ChatGPT acceptance (owner) | — |
