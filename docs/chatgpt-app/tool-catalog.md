# MITA in ChatGPT — tool catalog (v2.7, 25 tools)

Generated from the live tool list (`app/mcp/tools`); the semantics column is
pinned by `tests_mcp/test_tool_contract.EXPECTED`. Every tool: identity from
the OAuth token only, undeclared arguments rejected, `openWorldHint` false,
"MITA cannot initiate, execute or facilitate payments or money transfers" in
its description, and an output schema. Every category in a result comes with
`category_label`, MITA's one display name for it (`app/mcp/categories.py`).

**Confirmation.** ChatGPT asks the user before write tools; `destructiveHint`
(overwrite, delete, or a send that cannot be taken back) makes that an
explicit approval. Justifications per tool: `review/annotation-justifications.md`. The tools themselves
add their own guards: corrections need the expense's `ref`, a budget is saved
only from a signed preview, feedback only on explicit request.

## Read (`readOnlyHint` true — run in a READ ONLY transaction)

| Tool | Purpose | Inputs | Scope |
|---|---|---|---|
| `get_profile` | which MITA account is connected: opaque id, display name (when set), masked e-mail — exactly OpenAI's profile schema (`openai/profile` tool; since 2026-10-27 no currency/timezone: those are in `get_setup_status`) | — | profile:read |
| `get_setup_status` | what MITA already knows, what is missing, plan/records counts, next step; since 2.7.0 `spending` (how the user buys, line by line; lines without a stated pattern; MITA lines that do not apply) and the optional step `describe_spending`; since 2.8 `onboarding` (derived stage, preliminary/personalized readiness, topic states, next and optional questions — a returning user is never asked again) and `region` (the confirmed country and its source, the regional switch, ChatGPT's approximate country only as a suggestion) | — | profile:read |
| `get_financial_summary` | one month: income stated, plan, spent, remaining, top 3 categories | year, month | finance:read |
| `list_transactions` | expenses for a range with opaque `ref`s; keyset paging (`next_cursor`) | start_date, end_date, category, merchant, limit, cursor | finance:read |
| `get_spending_breakdown` | spending by category for a range | start_date, end_date | finance:read |
| `get_budget_status` | plan vs actual per category; today's figures | year, month | finance:read |
| `get_budget_forecast` | month-end projection at the current pace; safe daily amount, never counting money set aside for savings, goals or investments (`savings_set_aside`) or the money the month's bills still need (`commitments_reserved`, since 2026-10-25) | year, month | finance:read |
| `get_recurring_expenses` | scheduled obligations and expenses marked recurring (never inferred); since 2.7.0 each saved payment's `obligation_ref` and this month's due dates with what linked expenses paid | — | finance:read |
| `get_goals` | savings goals with deterministic projection (goals cannot be changed from ChatGPT) | status | finance:read |
| `get_spending_history` | up to 12 local months, per-category totals, completeness, trend (≥ 3 complete months) | months, category, end_month | finance:read |
| `get_financial_climate` | compact factual overview: averages, pace vs earlier months, plan adherence, late-month share, obligations, goals | months | finance:read |
| `get_regional_context` | 2.8: official statistics for the user's confirmed country from MITA's own copy (no live lookup) — consumer price inflation by category (Eurostat HICP for EU/EFTA/candidates, OECD CPI elsewhere), price levels vs the EU average (Eurostat PPP), household spending shares (Eurostat HBS), yearly inflation (World Bank), and since M3 the average EUR per kWh households pay for electricity and gas (Eurostat, half-yearly; `topic=prices`); each with source, period, unit, licence, limitation and `stale`; `no_country` / `turned_off` / `unavailable` | topic, category | finance:read |
| `preview_monthly_budget` | a budget draft from stated facts and MITA's engine, keeping the user's own budget lines exactly (`budget_lines`: their label and amount, and which MITA lines they `replace`; `source: set_by_you`) and allocating only the money left; since 2.7.0 each saved payment on its own line and every line laid out by how the user buys (`spending_patterns` overrides; planned purchases on real dates, flexible budgets with daily guidance, `not_applicable` MITA lines left out); a plan over the income is refused with every part named; returns a signed `draft_token`; **saves nothing** | month, budget_lines, remove_lines, spending_patterns | finance:read |
| `get_calendar_month` | the month as data, date by date: each date's plan, spending and state, budget lines in groups (commitments / set aside / everyday), saved bills by date with their state (paid — from linked expenses only, since 2.7.0 — / overdue / due today / upcoming / later), planned purchases and flexible guidance (since 2.7.0) and `reminders` (bills due within 5 days, today or overdue), a summary with the safe daily average; callable by the calendar component | year, month | finance:read |
| `show_financial_calendar` | **the only tool bound to a UI component**: shows the interactive calendar (`ui://mita/financial-calendar-v3.html`, since 2.7.0); figures from the account, never from arguments; short view for the model, the month for the component (`_meta`) | year, month, focus_date, category | finance:read |

## Write

| Tool | Purpose | Destructive | Idempotent | How retries are safe | Scope |
|---|---|---|---|---|---|
| `update_financial_profile` | save stated income, currency, timezone, household size, savings target; since 2.8 the confirmed country (ISO code; never a city, address or coordinates), income regularity, pay frequency and days, minimum monthly income for variable income, the regional switch and `setup_answers` (`none` / `described` / `skipped`) | yes (overwrites) | yes | same values → `unchanged` | finance:write |
| `save_spending_patterns` | save how the user buys for each line: planned (frequency + days), flexible, or a MITA line that does not apply; never changes a saved plan (`plans_to_review`) — since 2.7.0 | yes (overwrites a line's pattern) | yes | same patterns → `unchanged` | finance:write |
| `add_transaction` | record one expense, under a category or one of the user's own budget lines (`budget_line`), or as the payment of a saved payment (`obligation_ref`, since 2.7.0: the only thing that pays a bill) | no | yes | `idempotency_key` → `already_recorded` | finance:write |
| `add_transactions` | record up to 25 expenses, all or nothing | no | yes | `idempotency_key` | finance:write |
| `update_transaction` | correct amount/category/date/merchant of one expense (`ref`); link it to the saved payment it paid (`obligation_ref`, `""` unlinks) | yes | yes | same fields → `unchanged` | finance:write |
| `delete_transaction` | soft-delete one expense (`ref`) | yes | yes | second call → `already_deleted` | finance:write |
| `save_monthly_budget` | save exactly the reviewed draft (`draft_token`); may replace the month's plan | yes | yes | same draft → `already_saved` | finance:write |
| `add_recurring_expense` | save a repeating obligation with a computed next due date | no | yes | `idempotency_key` | finance:write |
| `create_savings_goal` | create a goal with the user's exact title; a target date sets the monthly amount aside; the goal cannot be changed afterwards | no | yes | `idempotency_key` | finance:write |
| `submit_feedback` | send the user's feedback to the MITA team (explicit request only) | yes (a sent message cannot be taken back; since 2026-10-27) | yes | `idempotency_key` | feedback:write |
| `set_usage_analytics` | turn usage statistics on/off (off deletes linked usage data) | yes | yes | same value → same state | profile:write |

`idempotentHint` is true for the create tools only because their arguments
include an `idempotency_key`: calling again with the same arguments has no
further effect (`app/mcp/idempotency.py`). The key is scoped by user,
operation and the hashed ChatGPT conversation; the same key with different
data is refused; nothing is ever deduplicated by content.

## UI component (MCP Apps)

`show_financial_calendar` carries `_meta.ui.resourceUri` (and ChatGPT's alias
`openai/outputTemplate`); `get_calendar_month` and `list_transactions` declare
`_meta.ui.visibility: ["model", "app"]` so the component may call them through
the host. The component is read-only, loads nothing and connects nowhere
(empty CSP allowlist). Details: `financial-calendar.md`.

## Never offered

Transfers, payments, trading, bank connections, receipt-image upload or OCR,
changing or deleting a goal (no monthly contribution, target date or added
money after creation) or an obligation, deleting the account (in the app only),
another user's data, raw analytics.
