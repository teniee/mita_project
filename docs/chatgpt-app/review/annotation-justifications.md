# Tool annotation justifications (MCP 2.3.0, 24 tools)

OpenAI's guidelines say annotation justifications are no longer required,
while the submission-error list still has `justification_required`
(`openai-compliance-2026-10-27.md`, C6). If the portal asks, paste the text
below. The values are the server's own (`tests_mcp/test_tool_contract.EXPECTED`);
a justification never overrides them (developers.openai.com/plugins/deploy/app-review).

Facts that hold for every tool:

* **openWorldHint false**: every tool works only on the signed-in user's own
  MITA account (identity from the OAuth token; no tool accepts a user, e-mail
  or account argument). No tool reaches the public internet, a third party or
  an arbitrary recipient.
* **Read tools** run inside a database transaction set `READ ONLY` that is
  always rolled back; they create, change and delete nothing. Like every call,
  they are counted in MITA's own operational statistics (pseudonymous only
  for users who opted in); that is not a change to the user's data.

## Read tools — readOnlyHint true, destructiveHint false, openWorldHint false

| Tool | readOnlyHint true because |
|---|---|
| `get_profile` | Returns the connected profile's opaque id, display name and masked e-mail. |
| `get_setup_status` | Reports which profile facts are saved and what is missing. |
| `get_financial_summary` | Totals one month from the user's recorded expenses and saved plan. |
| `list_transactions` | Lists the user's own recorded expenses for a date range. |
| `get_spending_breakdown` | Totals the user's expenses by category. |
| `get_budget_status` | Compares the saved plan with recorded spending. |
| `get_budget_forecast` | Computes a month-end projection and the safe daily amount from saved data. |
| `get_recurring_expenses` | Lists the user's saved regular payments. |
| `get_goals` | Lists the user's savings goals with a deterministic projection. |
| `get_spending_history` | Aggregates up to 12 months of the user's expenses. |
| `get_financial_climate` | Summarizes the user's recent months from saved data. |
| `preview_monthly_budget` | Computes a budget draft and returns a signed token holding only the month and a digest; nothing is stored. Saving is a separate, destructive tool (`save_monthly_budget`). |
| `get_calendar_month` | Returns the month date by date from saved plan rows and expenses. |
| `show_financial_calendar` | Renders the calendar component from the same read query; takes no figures as arguments. The component itself can call only `get_calendar_month` and `list_transactions`. |

## Write tools — readOnlyHint false, openWorldHint false

| Tool | destructiveHint | Why |
|---|---|---|
| `update_financial_profile` | **true** | Overwrites the previous value of each field sent (income, currency, timezone, household size, savings target); only fields the user stated are sent. It does not change a saved budget. |
| `add_transaction` | false | Inserts one new expense; nothing existing is deleted or overwritten. MITA then recalculates this month's derived plan (its automatic redistribution) while keeping the reviewed base plan; deleting the expense reverses that. An `idempotency_key` makes a retried call a no-op. |
| `add_transactions` | false | Same as `add_transaction` for up to 25 new expenses, all or none. |
| `update_transaction` | **true** | Overwrites fields of an existing expense, identified by its opaque reference. |
| `delete_transaction` | **true** | Removes an expense from every total (soft delete; there is no undo tool). |
| `save_monthly_budget` | **true** | Replaces the month's saved plan with the reviewed draft, only if the draft is still unchanged. |
| `add_recurring_expense` | false | Creates a new saved regular payment; nothing existing is changed. |
| `create_savings_goal` | false | Creates a new goal; with a target date it adds that goal's own set-aside rows to the remaining days of the current month. No existing goal or plan line is overwritten. |
| `submit_feedback` | **true** | Sends the user's own words to the MITA team; a sent message cannot be taken back. Only on the user's explicit request, after confirming the wording. The recipient is fixed (MITA's team, stored in MITA's database), so openWorldHint stays false. |
| `set_usage_analytics` | **true** | Turning statistics off deletes the usage records already linked to the user. |

`idempotentHint` is true for every tool: read tools change nothing; the
create tools take an `idempotency_key` (same key and arguments → no further
effect); updates, deletes and saves of identical values report `unchanged`,
`already_deleted` or `already_saved`.
