# Fixed payments on their due dates, bill reminders, and paying them (F-8) — 2026-11-03

> **Update 2026-11-03 (MCP 2.7.0, `behavioral-budget.md`).** Due dates,
> reminders and "a bill paid early, late or in parts is not overspending"
> stand. What pays a bill changed: only an expense the user links to it
> (`obligation_payments`, `obligation_ref`) — a purchase in the same category
> no longer counts (§6's "recorded by category" is superseded; the state is
> `paid`). Each saved bill has its own plan line (`bill:<digest>`) in plans
> saved from now on.

Owner decision 2026-11-02, after the real-ChatGPT acceptance run on staging:
a fixed obligation is planned **in full on its actual due date**, the
financial calendar **reminds** of it from five days before, and paying it —
on time, early, late or in parts — is **never overspending in itself**. This
authorizes R4 of `f8-money-model-proposal.md` and the protection against false
rebalancing that bills need. R1, R2 for everyday lines and R5 stay not
adopted: everyday lines keep MITA's per-date rebalancing.

Status: implemented on `feat/chatgpt-auth-ui` (MCP 2.5.0). Shared engine, so
the mobile API's figures follow (ChatGPT shows what the app implements). No
migration, no new table, no notification infrastructure.

## 1. What the owner saw, reproduced

The owner's staging account (November 2026, Europe/Sofia, EUR): income
2,000; savings 500; household 1; Phone 30 on the 10th, Car loan 270 on the
15th, Laptop loan 70 on the 25th; their own lines Fuel 200, Cigarettes 200,
Coffee and walks 100, Groceries 50, Housing 50.

The calendar read 52.00 on the 10th, 38.99 on the 15th and 51.96 on the 25th.
`allocations_from_profile` reproduces the month exactly (MITA's lines 530.00:
public transport 151.63, medical insurance 60.65 …; nothing unallocated; plan
2,000.00) — and the three figures come out **only** with the phone saved
under `utilities` and the loans under categories the layout does not know
(`transportation`, `other`): `tests_mcp/test_bill_due_dates.py::
test_the_old_layout_is_what_the_owner_saw`.

## 2. Root cause

1. **The layout never used due dates.** `budget_draft.build_draft` →
   `allocations_from_profile` → `month_calendar` → `distribute_budget_over_days`
   placed every line by `CATEGORY_BEHAVIOR`: `utilities` is "fixed" → the 5th;
   `transportation` and `other` are unknown → "spread" over the 21 weekdays
   (12.86 + 3.33 a weekday). No date held a whole bill; the 15th (a Sunday)
   held none of the car loan.
2. **The rebalancer judged each date alone.** `rebuild_month_plan` →
   `check_and_rebalance` treats spending above *that date's* row of *that
   category* as overspending and covers it from later dates of other lines (up
   to 50 % per line), while the bill's own money elsewhere stays planned. A
   bill paid on its due date was therefore "overspending" by most of its
   amount, drained the dates ahead, and its line ended up planned twice.
3. **Bills other than rent / mortgage / utilities were donors** (unknown
   categories default to FLEXIBLE): a saved €30 internet bill was cut to 9.17
   by other lines' overspending.

## 3. The rule now

| Step | Code | Rule |
|---|---|---|
| Due dates | `monthly_obligations.due_dates_in_month` (amount: `due_in_month`, now defined as it) | monthly: its day of the month, the month's last day when shorter; weekly: every matching weekday; one-time: its date. Counted only when running (next date before the end of the next month), as before. |
| Layout | `monthly_plan_service.bills_on_due_dates` via `month_calendar(…, bills)` / `_build_month_calendar` | each occurrence in full on its date, in date order, never beyond the category's allocation; whatever else the line holds is laid out as before. Used by the reviewed budget (`build_draft`) and the month rollover (`ensure_month_plan`, `dated_obligations`). |
| Which lines are bills | `expense_tracker.month_bill_categories` = `commitment_expectations` keys | exactly R3's bills: recordable categories of saved payments that count in the month, and the rent / mortgage / utilities lines. |
| Paying | `bill_timing.settle` + `retime_bill_lines`, called by `rebuild_month_plan` after spend is accrued | what is recorded under a bill line is matched to the line's dated rows **in date order**: the money due on the payment's own date, then money due earlier and unpaid (late, oldest first), then money due later (early, nearest first). The matched money moves to the date the payment was recorded on. Same line only: totals, reserve and safe daily amount do not change. |
| Overspending | `realtime_rebalancer` (unchanged rule) | only spending beyond the bill line's **whole month** is overspending, covered from everyday lines as before. |
| Donors | `rebalance_after_overspend(…, protected=bills)` | a bill line is never a donor (nor SACRED lines, the user's own lines, savings — as before). |
| Records | `plan_json["_mita_bill_timing_v1"]` (signed delta) | backed out before every replay, like `_mita_realtime_adjustment_v1`; `_base_planned_amount` reads through it; `_budget_rows` judges rows on their base allocation (a due-date row emptied by an early payment is still the plan's row). It is **not** redistribution: no `redistribution_events` row, no "redistributed" note, no mobile banner. |

Everyday lines: unchanged — the per-date rebalancer, the 50 % cap, donor
order. F-2 (expenses recorded under the API's names) still produces planned-0
rows that the rebalancer covers.

## 4. The money stays consistent

* **Conservation.** Layout and bill timing only move money between dates of
  one line; `look()` in `tests_mcp/test_money_consistency.py` (every scenario)
  checks Σ rows = plan, Σ adjustments = 0, status = forecast = calendar = the
  mobile forecast.
* **R3.** `commitments_reserved` = per bill, its base plan (or saved payments
  due when more) minus what is recorded under it — unchanged. When a reserved
  bill is recorded: spent +X, reserved −X, left to spend and the daily figure
  unchanged; nothing is subtracted twice.
* **The owner's month** (`test_the_owner_s_bills_are_planned_whole_on_their_due_dates`):
  income 2,000 = savings 500 + bills 370 + their lines 600 + MITA's lines 530;
  left to spend before any spending 1,130.00; on 2 Nov 1,130.00 ÷ 28 days =
  **40.36 a day**. Dates: 10 Nov **65.80** (everyday 35.80 + Phone 30), 15 Nov
  **308.99** (everyday 38.99 + Car loan 270), 25 Nov **105.78** (everyday 35.78
  + Laptop loan 70). The reminder windows (e.g. 20–24 Nov) carry no bill money.
* **F-11.** A user line is not recordable, so never a bill: never re-timed,
  never a donor, never covered — exact (`USER_LINES` checks in the suite).
* **Savings** are never bills, never donors, never spendable (unchanged).

## 5. Early, on time, late, in parts

| Case | Plan rows | Calendar | Reserve | Test |
|---|---|---|---|---|
| On time (15 Nov) | 270 on the 15th, spent 270; nothing moves | Car loan: recorded, 15 Nov | 370 → 70 (phone paid too) / left unchanged | `test_paying_bills_on_their_dates_moves_nothing_and_releases_the_reserve` |
| Early (12 Nov) | 270 moves 15th → 12th; the 15th holds only everyday money | recorded 12 Nov, 3 days early; no reminder | released once; no second 270 | `test_a_bill_paid_early_is_counted_once_on_the_day_paid` |
| Late (17 Nov) | until recorded: 270 stays on the 15th, held; then moves 15th → 17th | 16 Nov: overdue, not recorded; then recorded 17 Nov, 2 days late | held until recorded | `test_a_bill_paid_late_is_overdue_until_recorded_then_moves_with_it` |
| In parts (100 + 170) | 100 on the 15th; 170 moves 15th → 20th | due today with 100 recorded; overdue with 100; then recorded 15 and 20 Nov | 270 → 170 → 0 | `test_a_partly_paid_bill_keeps_the_rest_held` |
| More than the line (300) | 270 on its line, 30 covered from MITA's everyday lines | recorded | 0 | `test_spending_beyond_a_bill_line_is_overspending_as_before` |
| A plan saved before this change (bills spread) | paying the bill uses its own spread money first (no other line gives) | recorded | as above | `test_a_plan_saved_before_due_dates_is_corrected_only_when_the_user_saves_again` |

Rent / utilities stated in the mobile onboarding without a saved payment are
bills too (R3): paid on another date than the plan's, they move their own
money (`test_a_stated_essential_without_a_saved_payment_is_a_bill_line_too`).

## 6. What MITA can prove about a payment — and what it cannot

Inspected: `scheduled_expenses.transaction_id` exists, but only the cron
`cron_task_scheduled_expenses` sets it (and nothing runs it in production or on
staging), and one id per row cannot cover a repeating payment's months. ChatGPT
records a bill like any expense (`add_transaction`), with no link to the saved
payment. So MITA **cannot tell which bill an expense paid**.

What it can prove, and what the calendar says:

* the due date and amount (the saved payment);
* what is recorded under the bill's category this month, and on which dates
  (the ledger) — matched to the category's bill dates in date order
  (`settle`, the same rule that moves the plan's money);
* states: `recorded` (covered), `overdue` (due date passed, **not recorded in
  MITA**), `due_today`, `upcoming` (within five days), `later`. The calendar
  says **"Recorded"**, never "Paid", and names the category and dates it
  counted ("€270.00 under Transport, recorded 12 Nov, 3 days early").
* Amount is never used to match: a €15 taxi under Transport counts €15 toward
  the car loan (state stays upcoming, reminders continue,
  `test_an_unrelated_expense_in_a_bill_s_category_counts_only_its_amount`).
  An unrelated expense of the bill's full amount under its category **does**
  cover it — that is R3's existing category rule (the reserve is released the
  same way), shown with its date and category so the user can see what was
  counted.

**Proposal, not implemented (needs an owner decision and migration 0041):**
`bill_payments (user_id, scheduled_expense_id, due_date, transaction_id,
amount)`, cascading with the user, the payment and the expense; an optional
`pays_bill` reference on `add_transaction` / `add_transactions` (ChatGPT asks
"is this your car loan?" when a saved bill of that category is due within the
window) and a "mark as paid" tool. Then: state `paid` only from a link; the
reserve and bill timing use the link where present and the category rule
otherwise. Rollback: drop the table; behaviour falls back to category
matching. Grants: `SELECT, INSERT, DELETE` for `mita_mcp`.

## 7. Reminders (inside the calendar only)

* Window: `REMINDER_DAYS` = 5 calendar days before the due date
  (`queries/calendar.py`); a reminder, never an allocation — the bill's money
  stays on its due date.
* Wording (the owner's): 5 days before "Upcoming: Laptop loan €70.00, due 25
  Nov"; 4–2 days "Laptop loan payment in 3 days"; 1 day "Laptop loan payment
  due tomorrow"; the day "Laptop loan payment due today: €70.00"; after it, not
  recorded, "Laptop loan payment overdue" ("… was due Wed 25 Nov, not recorded
  in MITA").
* Data: every bill has `state`, `days_until`, `recorded`, `recorded_dates`,
  `reminder_from`; `reminders` lists the bills to mention now — this month's
  bills due within five days or today, the current month's overdue ones, and
  next month's bills due within five days of today (a bill on 1 December is
  announced from 26 November).
* Component: a "Bill reminders" strip (inline: two, then "+ N more";
  fullscreen: all); a bill mark on each due date coloured by state (teal
  recorded, amber upcoming, red overdue, navy/yellow due today — always with
  words in labels and chips); an amber band on the dates of a window (from
  today on); the selected date's "Bills due on this date" (state, what is
  recorded, and *Everyday plan + Bills due = Plan for the date*), "Bills
  recorded on this date" (paid early/late) and "Coming up"; "Bills this month";
  the PNG's bill dots by state (no bill names in the image). The model gets the
  reminders in the tool text and in the model context of the selected date.
* No push notification, e-mail, scheduled job or new notification
  infrastructure (separate features needing their own approval).

## 8. Existing saved plans (the owner's November)

* **Not rewritten.** Deploying 2.5.0 changes no stored base plan. A plan saved
  with the old layout keeps it; from the next expense recorded in that month
  the new ledger rule applies to it (a bill's payment uses its own line's
  money, wherever the old layout spread it; bill lines are not donors). The
  visible per-date rows of that month are re-derived on that write, as every
  ledger write already does.
* **To put the bills on their dates**, the user previews and saves the month
  again (ChatGPT: "Show my November budget again and save it"). Nothing else
  changes: the preview lists no amount change and says "No amount differs
  from the plan saved for 2026-11. Saving this preview changes only the
  day-by-day plan: each saved bill is planned in full on its due date …"; the
  user's own lines are kept exactly.
* **Not done (owner decision needed):** a one-off re-layout of every user's
  current month. Impact: each user's current-month base plan would change
  dates for bill lines (amounts identical); rollback = restore the rows from a
  pre-run copy of `daily_plan` for that month (the script would write one).

## 9. Limits

* A bill paid early **across the month end** (December's rent on 29 November)
  counts in the month it is recorded (the ledger is monthly).
* Category matching: everyday spending recorded under a bill's category counts
  toward that bill (R3's documented limit).
* A weekly bill saved mid-month counts every matching weekday of the month
  (the existing `due_in_month` rule); the dates before it was saved get their
  money in the plan but no marker (markers never come before the saved date).
* The sign-in page's fictional month (`app/mcp/auth/demo.py`) still lays its
  internet bill out without due dates: the OAuth pages were out of scope; its
  figures (€59.60 a day) do not depend on the layout.

## 10. Rollback

Re-pin `0af8435` (2.4.0). Rows rebuilt under 2.5.0 keep their
`_mita_bill_timing_v1` marker, which 2.4.0 ignores: its visible per-date bill
money stays where 2.5.0 moved it, every total is unchanged, and 2.5.0 restores
the base on its next rebuild. Staging has no mobile API, so the 2.4.0 rollover
(which judges rows by their visible amount) is not reachable there.

## 11. Tests

`tests_mcp/test_bill_due_dates.py` (21): the rule (month lengths, weekly,
one-time, not running yet), `settle`, placement, the owner's old and new
layouts, the owner's month through every surface, the five-day window and each
state, on time / early / late / in parts / beyond the line, everyday
overspending (never from bills or the user's lines), an unrelated expense,
two bills on one day and two in one category, weekly and one-time bills,
Sofia midnight, next month and a reminder across the month end, the mobile
rollover, an old-layout plan corrected only by saving again, rent/utilities
without a saved payment. `tests_mcp/test_money_consistency.py`: the five tests
that pinned the old behaviour rewritten with old and new figures (review month:
utilities 190.00 → 95.00, kindergarten 231.04 → 180.00, internet 9.17 → 30.00,
moved between lines 904.32 → 656.19, the plan for 25–31 Oct 12.16 → 61.53;
left 823.91 and 117.70 a day unchanged). Component: the local MCP Apps host
`scripts/mcp/calendar_widget_review.py` (reminders, bill marks, the bill
date's detail, the bills card, 320 / 360 / 390 px and desktop, light/dark,
PNG, axe).
