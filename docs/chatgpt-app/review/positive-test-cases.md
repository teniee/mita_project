# Positive test cases (OpenAI requires exactly 5)

Source of truth: `plugin/mita/plugin.template.json` →
`extensions.com.openai.review.test_cases.positive` (validated in CI). This page
adds what the reviewer should see with the review account
(`review-account.md`).

| # | Prompt | Tools | Expected behavior |
|---|---|---|---|
| 1 | How much have I spent this month, and what are my biggest categories? | `get_financial_summary` | Total spending for the current month, transaction count, top three categories with amounts in the account currency. Stated income presented as entered by the user. With the review data: 509.69 over 12 transactions; groceries 177.65, shopping 120.00, dining 88.05. |
| 2 | Am I over budget in any category this month? | `get_budget_status` | Planned / spent / remaining per category from MITA's plan; names over-budget and unplanned-spending categories; today's remaining daily budget. |
| 3 | At my current pace, how will this month end, and how much can I spend per day from now on? | `get_budget_forecast` | Projected month-end balance and status, safe daily amount for the remaining days, categories spending ≥1.2× their planned rate; explained as a linear projection. |
| 4 | Show my grocery purchases from the last 14 days. | `list_transactions` | Groceries transactions in range, newest first, with date, amount, merchant and the total (177.65 with the review data if all are inside the window); no notes/receipts/locations. |
| 5 | What bills do I have coming up, and how are my savings goals doing? | `get_recurring_expenses`, `get_goals` | Rent 1,100 monthly (next 1st), insurance 240 one-time, StreamFlix marked recurring by the user; Emergency fund 900 of 3,000 with its on-track projection. No claim of automatic subscription detection. |

Automated equivalents run in CI against real PostgreSQL:
`tests_mcp/test_finance_accuracy.py`, `tests_mcp/test_timezone.py`.
