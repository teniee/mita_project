# MITA in ChatGPT — tool catalog (v2.1, 22 tools)

Generated from the live tool list (`app/mcp/tools`); the semantics column is
pinned by `tests_mcp/test_tool_contract.EXPECTED`. Every tool: identity from
the OAuth token only, undeclared arguments rejected, `openWorldHint` false,
"MITA cannot initiate, execute or facilitate payments or money transfers" in
its description, and an output schema. Every category in a result comes with
`category_label`, MITA's one display name for it (`app/mcp/categories.py`).

**Confirmation.** ChatGPT asks the user before write tools; `destructiveHint`
(overwrite or delete) makes that an explicit approval. The tools themselves
add their own guards: corrections need the expense's `ref`, a budget is saved
only from a signed preview, feedback only on explicit request.

## Read (`readOnlyHint` true — run in a READ ONLY transaction)

| Tool | Purpose | Inputs | Scope |
|---|---|---|---|
| `get_profile` | which MITA account is connected; currency and timezone (`openai/profile` tool) | — | profile:read |
| `get_setup_status` | what MITA already knows, what is missing, plan/records counts, next step | — | profile:read |
| `get_financial_summary` | one month: income stated, plan, spent, remaining, top 3 categories | year, month | finance:read |
| `list_transactions` | expenses for a range with opaque `ref`s; keyset paging (`next_cursor`) | start_date, end_date, category, merchant, limit, cursor | finance:read |
| `get_spending_breakdown` | spending by category for a range | start_date, end_date | finance:read |
| `get_budget_status` | plan vs actual per category; today's figures | year, month | finance:read |
| `get_budget_forecast` | month-end projection at the current pace; safe daily amount | year, month | finance:read |
| `get_recurring_expenses` | scheduled obligations and expenses marked recurring (never inferred) | — | finance:read |
| `get_goals` | savings goals with deterministic projection (goals cannot be changed from ChatGPT) | status | finance:read |
| `get_spending_history` | up to 12 local months, per-category totals, completeness, trend (≥ 3 complete months) | months, category, end_month | finance:read |
| `get_financial_climate` | compact factual overview: averages, pace vs earlier months, plan adherence, late-month share, obligations, goals | months | finance:read |
| `preview_monthly_budget` | a budget draft from stated facts and MITA's engine; returns a signed `draft_token`; **saves nothing** | month | finance:read |

## Write

| Tool | Purpose | Destructive | Idempotent | How retries are safe | Scope |
|---|---|---|---|---|---|
| `update_financial_profile` | save stated income, currency, timezone, household size, savings target | yes (overwrites) | yes | same values → `unchanged` | finance:write |
| `add_transaction` | record one expense | no | yes | `idempotency_key` → `already_recorded` | finance:write |
| `add_transactions` | record up to 25 expenses, all or nothing | no | yes | `idempotency_key` | finance:write |
| `update_transaction` | correct amount/category/date/merchant of one expense (`ref`) | yes | yes | same fields → `unchanged` | finance:write |
| `delete_transaction` | soft-delete one expense (`ref`) | yes | yes | second call → `already_deleted` | finance:write |
| `save_monthly_budget` | save exactly the reviewed draft (`draft_token`); may replace the month's plan | yes | yes | same draft → `already_saved` | finance:write |
| `add_recurring_expense` | save a repeating obligation with a computed next due date | no | yes | `idempotency_key` | finance:write |
| `create_savings_goal` | create a goal with the user's exact title; a target date sets the monthly amount aside; the goal cannot be changed afterwards | no | yes | `idempotency_key` | finance:write |
| `submit_feedback` | send the user's feedback to the MITA team (explicit request only) | no | yes | `idempotency_key` | feedback:write |
| `set_usage_analytics` | turn usage statistics on/off (off deletes linked usage data) | yes | yes | same value → same state | profile:write |

`idempotentHint` is true for the create tools only because their arguments
include an `idempotency_key`: calling again with the same arguments has no
further effect (`app/mcp/idempotency.py`). The key is scoped by user,
operation and the hashed ChatGPT conversation; the same key with different
data is refused; nothing is ever deduplicated by content.

## Never offered

Transfers, payments, trading, bank connections, receipt-image upload or OCR,
changing or deleting a goal (no monthly contribution, target date or added
money after creation) or an obligation, deleting the account (in the app only),
another user's data, raw analytics.
