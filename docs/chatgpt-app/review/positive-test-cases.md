# Positive test cases (OpenAI requires exactly 5 — confirmed 2026-10-27)

Source of truth: `plugin/mita/plugin.template.json` →
`extensions.com.openai.review.test_cases.positive` (validated in CI). This page
adds what the reviewer should see with the review account
(`review-account.md`). Each case is also played automatically, over public
HTTP, by `scripts/mcp/e2e_v2.py`.

| # | Prompt | Tools | Expected behavior |
|---|---|---|---|
| 1 | I spent €36.80 at Lidl on groceries today. | `add_transaction` | Records exactly 36.80 in the account currency, category groceries, merchant Lidl, dated today in the account's timezone; confirms it; nothing else changes. `list_transactions` then shows it. |
| 2 | I earn €2,500 net a month and want to save €400. Build my budget for this month. | `update_financial_profile`, `preview_monthly_budget` | Saves income and savings target (after confirming); shows a preview — fixed obligations, savings, category amounts, unallocated money, warnings — and says it is not saved; saves it with `save_monthly_budget` only after the user agrees. |
| 3 | Show my financial calendar for this month. | `show_financial_calendar` | MITA's interactive calendar of the current month in the chat (inline; **Open calendar** for fullscreen): each date's plan and recorded spending, saved bills on their dates, money set aside, and a summary — left to spend, spent, savings kept, the average a day (the same safe daily figure as "How much can I safely spend per day?"). A date lists its expenses; category chips and month arrows redraw it; **Save as PNG** gives an image of the month. ChatGPT adds at most a short comment; nothing changes in the account. |
| 4 | How have my grocery expenses changed over the last six months? | `get_spending_history` | Grocery totals per month from MITA's records; months before the first record marked as no data; a trend only with at least three complete months. |
| 5 | My rent is €700 every month on the first. Also, I want to save €5,000 by June. | `add_recurring_expense`, `create_savings_goal` | Rent saved as a monthly obligation due on the next 1st; a goal with the user's title, target 5,000 and a June date (asking the year if unclear); the monthly amount needed stated as arithmetic, no advice. |

Case 3 replaced "How am I doing against my budget this month?"
(`get_budget_status`) on 2026-10-27: the calendar is the plugin's only UI
component and OpenAI's review checks UI errors; its summary carries the same
budget position. Run all five with the review account in production, on the
web and on the phone, before submitting (OpenAI: cases must pass on the
supported surfaces).

Automated equivalents run in CI against real PostgreSQL:
`tests_mcp/test_transaction_writes.py`, `test_budget_plan.py`,
`test_calendar.py`, `test_history.py`, `test_recurring_goal_writes.py`.
