# Data-trust audit: which MITA sources the ChatGPT app may use

Rule for MCP v1: a tool may only return a figure that is either a stored fact
about the user (a transaction, a plan allocation, a goal, a value the user
entered) or deterministic arithmetic over such facts with the method stated.
Anything that substitutes a default, a tier average, a generic rule or a model
guess for missing data is excluded, even if the mobile app still shows it.

Classification:

* **TRUSTED** — used by MCP v1.
* **NEEDS_FIX** — the computation is sound but the route around it is wrong
  in a way MCP must not inherit (timezone, truthiness, mislabel). MCP calls the
  underlying pure function correctly or reads the table directly.
* **DO_NOT_USE_FOR_MCP** — produces invented, generic or unverifiable output.

All line numbers refer to `27ed25d`.

## Ledger and plan

| Source | Class | Why |
|---|---|---|
| `transactions` rows with `deleted_at IS NULL` | TRUSTED | The ledger. Amount `Numeric(12,2)`, `spent_at` timestamptz (UTC). Every MCP spend figure comes from here. |
| `daily_plan.planned_amount` | TRUSTED | Persisted allocation; per-day sums re-add to the month to the cent (`_materialize_month` refuses otherwise). Includes realtime rebalance adjustments, which is what the app shows. |
| `daily_plan.spent_amount` | NEEDS_FIX (as a source) | A cache rebuilt from the ledger by `rebuild_month_plan`; post-commit side effects are best-effort (`6056825`), so it can lag the ledger. MCP recomputes spend from the ledger with the same local-day keys instead. |
| `daily_plan.daily_budget` | DO_NOT_USE_FOR_MCP | Mirrors `planned_amount` per row; the invariant in `CLAUDE.md` is `day_budget == SUM(planned_amount)`. Not needed. |
| `expense_tracker.local_day_of` / `local_day_utc_window` | TRUSTED | Canonical user-local day. |
| `BudgetTracker.get_spent / get_remaining_per_category` | NEEDS_FIX (as a source) | Aggregation is correct, but reads the spend cache above. MCP uses planned from plan + spent from ledger. |
| `monthly_plan_service.ensure_month_plan*` | DO_NOT_USE_FOR_MCP | Correct and canonical, but it **writes**. MCP is read-only; an unmaterialized month is reported as `plan_status: "not_generated"`. |
| `users.monthly_income` | TRUSTED, labeled | A figure the user entered at onboarding / in profile. Reported as `stated_monthly_income`, never as earned income, never as a budget. `0` / `NULL` → `null`. |

## Budget / forecast routes

| Source | Class | Why |
|---|---|---|
| `budget_forecast_engine.compute_forecast` | TRUSTED | Pure Decimal; `today` injectable; `no_data` when there is no plan. MCP passes the user's local today. |
| `GET /budget/forecast` route | NEEDS_FIX | Month from UTC `now`, `today` from server `date.today()` (`budget/routes.py:363,425`). Wrong around local midnight and on month edges for non-UTC users. |
| `GoalForecast.on_track` when `target_date is None` | NEEDS_FIX | The engine reports `on_track: false` for a goal with no deadline — a verdict nothing supports. MCP reports `null` with `projection: "no_target_date"`. |
| `GET /budget/live_status` | DO_NOT_USE_FOR_MCP | `on_track` = spent ≤ `monthly_income * day/30` (`:740`): income treated as budget, 30-day month. |
| `GET /budget/daily` | DO_NOT_USE_FOR_MCP | `remaining` is `0.0` whenever `spent_amount` is 0 (`:483`, truthiness on Decimal). |
| `GET /budget/suggestions`, `/income_based_recommendations`, `/behavioral_allocation`, `/auto_adapt` | DO_NOT_USE_FOR_MCP | Recommendation engines (tier weights, rule-of-thumb splits). |
| `GET /api/dashboard` exception path | DO_NOT_USE_FOR_MCP | On any exception returns `balance 0.0`, `spent 0.0` as data (`dashboard/routes.py:477`). |

## AI / insights / analytics

| Source | Class | Why |
|---|---|---|
| `/api/ai/financial-health-score` | DO_NOT_USE_FOR_MCP | Weighted composite with tier thresholds; honest since #283 but a score is a verdict, and ChatGPT should reason over facts. |
| `/api/ai/weekly-insights` / `AIFinancialAnalyzer.generate_weekly_insights` | DO_NOT_USE_FOR_MCP | No-data branch still returns `trend: "stable"` (`ai_financial_analyzer.py:1174`); trend over UTC weeks. |
| `/api/ai/budget-optimization` | DO_NOT_USE_FOR_MCP | "Reduce {top} by 15%", `confidence: 0.75`, `optimized_allocation = current_allocation` (`ai/routes.py:452-470`) — invented. |
| `POST /api/ai/advice` | DO_NOT_USE_FOR_MCP | Averages 30 days over a hardcoded 30, and the query has **no `deleted_at` filter** (`ai/routes.py:~787`) — deleted transactions reach the advice text. |
| `/api/ai/assistant`, `/personalized-feedback`, `/spending-prediction`, `/goal-analysis`, `/monthly-report`, snapshots | DO_NOT_USE_FOR_MCP | Second LLM / generated narrative. ChatGPT is the language layer. |
| `/api/insights/` exception path | DO_NOT_USE_FOR_MCP | Returns fabricated advice `"id": "fallback-001"` dated `"2025-01-29"` (`insights/routes.py:62-71`). |
| `/api/insights/income_based_tips` | DO_NOT_USE_FOR_MCP | `monthly_income or 3000.0` (`insights/routes.py:126`) + generic rules. |
| `/api/cohort/*` | DO_NOT_USE_FOR_MCP | Peer data about other people; documented residual multi-account leakage. Never exposed through ChatGPT. |
| `/api/behavior/*`, `/api/analytics/*`, challenges, leaderboard | DO_NOT_USE_FOR_MCP | Behavioral profiling / engagement features, out of scope; several had fabricated fallbacks (CLAUDE.md). |

## Goals, recurring, entitlements

| Source | Class | Why |
|---|---|---|
| `goals` (`deleted_at IS NULL`) | TRUSTED | User-entered target/saved/contribution/date. `progress` is a stored percentage; MCP recomputes it from amounts to avoid drift. |
| `scheduled_expenses` with `recurrence` set, `status='pending'`, not deleted | TRUSTED | User-declared future/recurring expense. |
| `transactions.is_recurring = true` | TRUSTED, labeled | User-flagged at entry. Reported as "marked recurring by you", not as a detected subscription. |
| Merchant-name subscription inference | — | Does not exist in the codebase. MCP v1 reports no inferred items. |
| `recurring_expense_handler.inject_recurring_expenses` | DO_NOT_USE_FOR_MCP | Imports a `RecurringExpense` model that is not defined anywhere — dead code. |
| `users.is_premium` / `premium_until` via `iap/entitlements` | TRUSTED (not used in v1) | Single source of entitlement. v1 has no premium-only tool. |

## Consequences for the tool set

| Tool | Sources |
|---|---|
| `get_profile` | `users` (name, masked email, currency, timezone, onboarding flag, stated income) |
| `list_transactions` | ledger |
| `get_spending_breakdown` | ledger |
| `get_financial_summary` | ledger + plan allocation + stated income |
| `get_budget_status` | plan allocation + ledger spend |
| `get_budget_forecast` | `compute_forecast` over plan allocation + ledger spend, local today |
| `get_recurring_expenses` | `scheduled_expenses` + `is_recurring` transactions |
| `get_goals` | `goals` + `compute_forecast` goal projection |

Nothing in MCP v1 calls OpenAI, GPT, the AI analyzer or any recommendation
engine.

## Fix backlog (outside this branch's scope, recorded for the owner)

1. `/budget/forecast`: pass `local_day_of(now, user.timezone)` as `today` and
   derive the default month from it.
2. `/budget/daily`: `remaining = daily_budget - spent_amount` with `is not None`.
3. `/budget/live_status`: drop `on_track` or compute it against the plan.
4. `/ai/advice`: add `Transaction.deleted_at.is_(None)`.
5. `/insights/` exception path and `/insights/income_based_tips` income
   default: same fix pattern as #278/#283.
6. `generate_weekly_insights` no-data branch: `trend: None`.
7. `GoalForecast` with no target date: `on_track: None`.
