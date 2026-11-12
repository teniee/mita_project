# MITA free v1 in ChatGPT — how it works

MITA keeps the user's budget, expenses, recurring obligations and goals in
their MITA account, so they are there in every future ChatGPT conversation
and in the MITA app. ChatGPT handles language, vision and the conversation;
MITA owns the account, the records and every calculation (PostgreSQL is the
source of truth, never ChatGPT memory). No subscriptions, paywalls, bank
connections, transfers or trading.

## The new-user flow

1. **Connect.** The user adds MITA in ChatGPT. MITA's own page offers
   *Sign in* or *Create an account* (e-mail, password, repeat password; the
   API's own policy and lockout), plus the optional usage-statistics box.
   Creating the account continues the same pending authorization; the grant
   is scoped to the new user and to the five scopes listed on the page.
2. **Setup** (onboarding skill `plugin/mita/skills/setup`): ChatGPT calls
   `get_setup_status`, asks once for only the missing fields (net income,
   currency, timezone, household size, savings target) and saves what the
   user states with `update_financial_profile`.
3. **Obligations.** Before a first budget MITA suggests asking once about
   regular payments (`suggested_next_step: ask_about_obligations`, never
   mandatory). "My rent is €700 every month on the first" →
   `add_recurring_expense` (next due date computed from what was said;
   never guessed). A preview without obligations is labelled a default draft.
4. **Budget.** "Build my budget for this month" → `preview_monthly_budget`
   (nothing saved) → the user reviews fixed obligations, savings, categories,
   unallocated money, warnings → "Save it" → `save_monthly_budget` with the
   draft token saves exactly that plan.
5. **Everyday use.** "I spent €36.80 at Lidl on groceries today" →
   `add_transaction`; "Also €8 coffee and €55 fuel" → `add_transactions`;
   a receipt photo → ChatGPT reads it, MITA records the lines, each with the
   category of what it is (`entry_method: receipt_image`; the image never
   reaches MITA). Mistakes:
   `list_transactions` → `update_transaction` / `delete_transaction` by `ref`.
6. **Questions.** Budget status, forecast, summary, spending breakdown,
   `get_spending_history` ("how have my groceries changed over six
   months?") and `get_financial_climate` (overview).
7. **Goals and feedback.** "I want to save €5,000 by June" →
   `create_savings_goal` (with a target date MITA sets the monthly amount
   aside; a goal cannot be changed afterwards from ChatGPT, and the tools say
   so); "Tell the MITA team that…" → `submit_feedback`.
8. **A new conversation months later** sees all of it: everything above is in
   MITA's database, keyed to the account the token belongs to.

## Budget engine (what is reused)

No LLM and no new allocation rule. Inputs, in priority order: stated net
income → saved obligations (monthly in full; weekly × matching weekdays;
one-time if dated in the month) → savings target → the canonical engine
`generate_budget_from_answers` (the function onboarding calls; region rules
from the user's stored region/country — the DEFAULT profile for accounts
created in ChatGPT) → `distribute_budget_over_days` for the day layout. The
engine only scales allocations down, so money can stay *unallocated*.
Household size is recorded but the engine does not use it, and the preview
says so. Recorded history (up to three complete months) only adds warnings.
No regional cost data and no income-class labels are exposed.

**Reviewed == saved:** the draft token carries the month and a digest of the
allocations and day layout, HMAC-bound to the user, valid 2 hours (a
freshness bound; integrity comes from the digest check below). Saving
rebuilds the draft under the ledger lock and writes it only if the digest
matches; a change to income, savings or obligations since the preview makes
the user preview again. Replacing a month's plan keeps goal reservations and
re-applies the month's expenses (MITA's automatic redistribution may then
move money between categories — the base plan stays the reviewed one).

## Six-month financial climate

Aggregated in SQL by the user's local month — never raw rows. A month before
the first recorded expense is `before_tracking` (no data, not zero); a
complete month with nothing recorded is `recorded` with 0; the current month
is `in_progress` and never enters averages. Averages/medians use complete
months; trends and the late-month share need 3 complete months, else
`insufficient_data`. The climate states numbers only: averages, this month vs
earlier months by the same day, months within/over a saved plan, share of
spending in a month's last 7 days, obligations, goal totals, completeness.
Six months is the default analysis window, not a retention period: records
stay until the user deletes them or the account.

## Receipts

ChatGPT interprets the image (merchant, date, total, lines, categories) and
calls the normal write tools; if the total, date or a category is unclear it
asks first. MITA validates and stores structured expenses only, and the
idempotency key makes a retried call harmless. MITA stores no images and runs
no OCR in v1.

## Known differences from the app

* Push alerts (budget, velocity, large transaction) are not sent for
  expenses recorded in ChatGPT (the MCP service has no Firebase); the plan is
  updated identically.
* Savings goals are not Premium-gated in ChatGPT (v1 is free).
* A second savings goal with a target date cannot reserve its daily amounts
  in the plan (backend finding F-1); the goal is saved and the result says so.
* Plan categories (`dining out`, `transport gas`…) and expense categories
  (`dining`, `gas`…) are stored under different names by the existing engine
  (F-2). In ChatGPT every category carries one display name (`category_label`:
  "Fuel" for both `transport gas` and `gas`) and budget status shows such a
  pair as one line; the app still shows both stored names, and the ledger
  still treats `gas` spending as unplanned (the redistribution covers it).
* MITA's taxonomy has no alcohol or tobacco category: drinks bought in a shop
  are groceries unless the user chooses otherwise.
