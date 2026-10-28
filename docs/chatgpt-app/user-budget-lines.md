# User budget lines in ChatGPT (F-11) — 2026-10-28

Scope: the ChatGPT plugin only. When the user gives their own monthly amount
for something — "Fuel €200", "Cigarettes €200", "Cat food €60" — MITA keeps
it exactly and allocates only the money that is left. ChatGPT understands the
words; MITA does the money. No new category, no taxonomy, no mobile change.

## Model

* **A user line is an ordinary plan line** under the key `"my:" + label`
  (`app/services/core/engine/user_budget_lines.py`): `daily_plan.category`
  for its amounts, `transactions.category` for the expenses recorded against
  it. The ledger, rollover, forecast, calendar and status treat it like any
  other line. The label is the user's own words (≤ 40 characters; the same
  name in any letter case is the same line); the key is its stable id.
* **`mcp_budget_lines`** (migration `0040`, one MCP-owned table, cascades with
  the user) keeps only `replaces`: which of MITA's own engine lines the user's
  line takes the place of (`transport gas` for their "Fuel"). ChatGPT chooses
  it in the conversation; MITA never interprets the words. It is what keeps a
  month rebuilt later (a new conversation, next month) from budgeting the same
  spending twice.
* **The engine** (`generate_budget_from_answers`): user lines exact, their
  replaced lines left out, MITA's lines from the money left — scaled down only,
  as before. Bills + savings + user lines over the income → `PlanDoesNotFit`
  with every part named; nothing is shrunk. Without user lines the engine is
  unchanged (pinned by tests).
* **Bills (R3)**: untouched. A user line is not an expense category a payment
  can be saved under, so it is never held as a bill; rent and saved payments
  are held as before.
* **Redistribution** (`realtime_rebalancer`, two conditions): a user line is
  never a donor, and an overspend in it is not covered from other lines — its
  monthly total stays what the user set; the overspend stays visible.

## Tools

* `preview_monthly_budget(month, budget_lines=[{label, amount, replaces?}],
  remove_lines=[...])`: the month from the stated facts, keeping the month's
  saved user lines (or, for a month without a plan, the latest month's), plus
  the requested ones. Every allocation has `source` (`set_by_you` /
  `calculated_by_mita`) and user lines their `replaces`; `changes` lists what
  differs from a saved plan; a user line named like a MITA line still in the
  plan gets a warning. The draft token is `bd2_…` (AES-SIV, bound to the user)
  when it carries lines; `bd1_` otherwise, as before.
* `save_monthly_budget`: saves exactly the reviewed plan and the lines'
  `replaces`; returns `set_by_you`.
* `add_transaction`, `add_transactions` items, `update_transaction`:
  `budget_line` (name or `my:` id) instead of `category` records the expense
  against the user's line. Recording under a standard category while the user
  has lines adds a note naming them.
* `get_budget_status` and the calendar lines carry `source`.

## Deploy

`0040` (new table only) from the operator machine, then the `mcp_budget_lines`
grant in `scripts/mcp/mcp_service_role.sql`, then MCP 2.4.0. Rollback: re-pin
2.3.0 (it ignores the table); `alembic downgrade 0039` drops it — the lines
stay in plans and ledger as amounts, only `replaces` is lost.

## Post-submission (not in this change)

* Re-timing a user line's overspend within its own later days (today it stays
  on the day; the monthly total is right).
* The app (mobile) showing user lines by label and recording against them;
  the app's "Auto redistribution" switch (it sends `auto_redistribution`, the
  API stores `redistribution_enabled`, nothing reads it); the batch
  redistributor (not scheduled anywhere) does not know user lines.
* A "set by you" tag in the calendar widget (the data carries `source`).
* Editing one line without rebuilding MITA's lines (today a preview rebuilds
  MITA's part from the stated facts, as it always did).
* `list_transactions` filter by user line.
