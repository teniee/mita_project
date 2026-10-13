# Positive test cases (OpenAI requires exactly 5)

Source of truth: `plugin/mita/plugin.template.json` →
`extensions.com.openai.review.test_cases.positive` (validated in CI). This page
adds what the reviewer should see with the review account
(`review-account.md`). Each case is also played automatically, over public
HTTP, by `scripts/mcp/e2e_v2.py`.

| # | Prompt | Tools | Expected behavior |
|---|---|---|---|
| 1 | I spent €36.80 at Lidl on groceries today. | `add_transaction` | Records exactly 36.80 in the account currency, category groceries, merchant Lidl, dated today in the account's timezone; confirms it; nothing else changes. `list_transactions` then shows it. |
| 2 | I earn €2,500 net a month and want to save €400. Build my budget for this month. | `update_financial_profile`, `preview_monthly_budget` | Saves income and savings target (after confirming); shows a preview — fixed obligations, savings, category amounts, unallocated money, warnings — and says it is not saved; saves it with `save_monthly_budget` only after the user agrees. |
| 3 | How am I doing against my budget this month? | `get_budget_status` | Planned / spent / remaining per category from MITA's saved plan, categories over plan, today's remaining amount; says so if no plan is saved. |
| 4 | How have my grocery expenses changed over the last six months? | `get_spending_history` | Grocery totals per month from MITA's records; months before the first record marked as no data; a trend only with at least three complete months. |
| 5 | My rent is €700 every month on the first. Also, I want to save €5,000 by June. | `add_recurring_expense`, `create_savings_goal` | Rent saved as a monthly obligation due on the next 1st; a goal with the user's title, target 5,000 and a June date (asking the year if unclear); the monthly amount needed stated as arithmetic, no advice. |

Automated equivalents run in CI against real PostgreSQL:
`tests_mcp/test_transaction_writes.py`, `test_budget_plan.py`,
`test_history.py`, `test_recurring_goal_writes.py`.
