# Behavioral budget: obligations, planned purchases, flexible budgets — 2026-11-03

Owner brief of 2026-11-03, after testing MITA Finance Staging v2.6 in ChatGPT:
MITA plans money by **how the user actually spends it**, and a fixed
obligation is settled **only by its own payment**. Implemented on
`feat/chatgpt-auth-ui` as MCP 2.7.0 with migrations 0041 and 0042. Not
deployed. This supersedes the category-matching parts of
`bill-due-dates.md` (F-8) and `r3-bills-reserve.md` (R3): due dates,
reminders and "bills first" stay; what pays a bill changed.

## 1. What the owner saw

Owner's staging month (Nov 2026, Europe/Sofia, EUR): income 2,000, savings
500; Phone 30 (10th, `utilities`), Car loan 270 (15th, `transportation`),
Laptop loan 70 (25th, `other`); own lines Fuel 200, Cigarettes 200, Coffee and
walks 100, Housing 50, Groceries 50. Real expenses: BMW intake pipe €60
(2 Nov, `transportation`), personal-care products €23.50 (3 Nov, `other`),
cigarettes €3.50 and coffee €2 (3 Nov).

* The reserve held **286.50** against **370.00** of bills: 30 + (270 − 60) +
  (70 − 23.50). The car part "paid" the car loan; the cosmetics "paid" the
  laptop loan.
* A €200 cigarette limit behaved like €9.52 of cigarettes every weekday.
* MITA planned medical insurance (60.65, as a lump on the 5th: it looked like
  a payment) and public transport (151.63) for a driver who has neither.

## 2. Root causes (confirmed in code before changing it)

| Finding | Where |
|---|---|
| The reserve counted every expense in a bill's category as paying it: `max(0, need − spent_in_category)` | `budget_forecast_engine._still_reserved` |
| The ledger moved a bill line's money to ANY spending in its category, and the calendar marked the bill "recorded" from it | `bill_timing.settle` / `retime_bill_lines`, `queries/calendar._settled_bills` |
| No expense↔obligation link existed; `scheduled_expenses.transaction_id` is set only by a cron that runs nowhere | `models/scheduled_expense.py`, `cron_task_scheduled_expenses.py` |
| An obligation shared its `daily_plan` row (unique per date + category) with everyday money of the same category | `uq_daily_plan_user_date_category` |
| `spread` with a frequency took the FIRST N weekdays; unknown categories spread over weekdays; `fixed` non-rent landed on the 5th; `clustered` used pseudo-random days | `calendar_engine.distribute_budget_over_days` |
| The reviewed budget and the rollover had no behavioral input; the rollover's only "shape" was last month's count of populated dates | `monthly_plan_service.month_calendar` (`frequencies={}`), `_base_month_allocations` |
| Every overspend was judged per date: spending above one date's row drained other lines | `realtime_rebalancer.check_and_rebalance` |
| The engine always created medical insurance and public transport | `budget_logic.generate_budget_from_answers` |
| Frequencies existed only in the mobile onboarding payload (never persisted) | `api/onboarding` `spending_habits` |
| `behavioral_budget_allocator.get_behavioral_allocation` spreads by population weekday biases with float rounding — not used by the persisted plan, **not reused** (it would invent purchase days) | `services/core/behavior/` |

## 3. The model

Three kinds of spending, plus savings; every line of a laid-out month is one
of them, stamped on its rows (`plan_json["_mita_line_kind_v1"]`):

| Kind | What | Layout | Spending against it |
|---|---|---|---|
| **obligation** | a saved regular payment (`scheduled_expenses`): car loan, rent, phone | its own line `bill:<digest>` (one-way SHA-256 of its id, never the id), in full on each due date | only an expense the user **linked** to it (`obligation_payments`) pays it |
| **planned** | purchases on known days: groceries every Wednesday | the monthly amount split exactly over the real purchase dates | the line's own money follows its spending (R2), then other lines only beyond the line's month |
| **flexible** | no fixed days: coffee, cigarettes, walks — and **any line with no stated pattern** | evenly over every day as guidance, never shown as purchases | same as planned (R2): an envelope |
| set_aside | savings | as before | as before; never spendable |

A month without the marker is a **legacy** layout (saved before 2.7.0, or by
the mobile onboarding): it keeps its layout and per-date rebalancing until the
user saves it again — no silent rewrite.

### 3.1 Payment identity (`app/services/obligation_lines.py`)

* `obligation_payments(user_id, scheduled_expense_id, due_date,
  transaction_id UNIQUE)`: one expense pays one due date; one due date may be
  paid in parts. Cascades with user, payment and expense; a soft-deleted
  expense is ignored. **Existing expenses are not linked** — nothing proves
  which paid a bill.
* A linked expense pays its due date **up to that date's amount**; more is
  spending beyond the bill (covered from MITA's everyday lines, never another
  due date's payment). A payment for a due date in another month does not
  touch this month's money; the reserve counts it for its own due date.
* `plan_line_of` is the one keying rule (ledger rebuild and every MCP read):
  a linked expense counts on its obligation's line in a keyed month, under
  its category in a legacy one; everything else on its category.
* The reserve (R3) per obligation = its due dates this month − linked
  payments (capped per due date), never below 0. Rent / mortgage / utilities
  lines with **no** saved payment (mobile onboarding) have no identity and
  keep R3's category rule. The mobile `GET /api/budget/forecast` uses the same
  function (`month_commitments`), so the app and ChatGPT agree.
* A linked expense is recorded under its obligation's own category.

### 3.2 Spending patterns (`app/services/core/engine/spending_schedule.py`)

Pure, integer cents, real dates. Frequencies: `daily`, `weekly` (one
weekday), `weekdays` (several), `biweekly` (+ one purchase date, the chain
continues across months), `times_per_month` (spaced evenly and centered:
twice in November = 8 and 23; weekdays optional; the result says MITA spaced
them), `monthly` / `dates` (day of the month, the last day when shorter:
31 → 28 Feb 2027, 29 Feb 2028). November 2026: €200 every Wednesday = 4 × 50.00
(4, 11, 18, 25); every Monday = 5 × 40.00 — never a four-week month.
**Approximate patterns (owner, 2026-11-04).** "About once a week, ~€50" gives
a frequency and an amount, not a day: `weekly` with no weekday is allowed and
MITA PROPOSES one date a week (the 4th, 11th, 18th, 25th); `times_per_month`
without weekdays likewise. Proposed dates are always labelled
(`dates_are_stated` = false → `purchase_dates_stated: false`, `proposed: true`
on each purchase, "(dates proposed by MITA)" in words); the monthly amount is
exact; the typical amount is shown, never used to change it.

`not_applicable` leaves one of MITA's lines out of the plan. Its money is
shown, never moved silently: the preview's `freed_money` compares with the
same engine run keeping the line — what each left-out line would have had,
what MITA's other lines gained by its usual shares, what stays unallocated
(conserved to the cent) — and the user directs it explicitly with
`budget_lines` (exact amounts, e.g. groceries €300). A line the user disabled
(`not_applicable`), one they never configured (`pattern_source:
mita_default`) and one MITA merely suggested (`source: calculated_by_mita`)
stay distinct in every result; a disabled line is never restored by a later
preview. A user line that replaces exactly one MITA line keeps that line's
pattern.

### 3.3 Source semantics

`set_by_you` (the user's amount, never changed by MITA), `fixed_payment`
(a saved obligation), `calculated_by_mita` (a suggestion), `savings`, and for
each line `pattern_source`: `user_confirmed` or `mita_default` (nothing
stated → flexible, no invented dates). `spending_patterns.source` accepts
only `user_confirmed`: nothing inferred is stored.

## 4. Ledger behavior (`expense_tracker.rebuild_month_plan`)

1. Back out every adjustment (realtime + line timing) → base plan.
2. Accrue each expense on its plan line (`plan_line_of`).
3. Move each self-settling line's own money to its spending dates
   (`bill_timing.retime_bill_lines`, `settle`): obligation lines with linked
   payments only (target due date first); planned and flexible lines with all
   their spending (same date, then earlier unspent, then the nearest later).
   Pacing, not redistribution: no `redistribution_events`, no note.
4. What is left over a date's row is overspending: covered by the existing
   rebalancer from MITA's own everyday lines (50 % cap per line), never from
   obligations, the user's lines or savings; a user line's overspend stays
   visible (F-11).

€43 against a €50 planned grocery purchase: the €7 stays on the line (157.00
left); the next shop of €55 uses its own €50 and those €7.

## 5. Conversational onboarding (MCP)

| Need | Tool |
|---|---|
| completion status, missing behavioral preferences | `get_setup_status`: `spending` (lines, stated or not, MITA lines that do not apply), `suggested_next_step` `describe_spending` (after obligations, before the first budget; optional) |
| save confirmed preferences / update one | **`save_spending_patterns`** (new; write, destructive = overwrites a line's earlier pattern, idempotent). Never changes a saved plan: `plans_to_review` names the months to preview and save |
| preview a behavioral month | `preview_monthly_budget(spending_patterns=…)`: overrides shown, not persisted; each line has `spending_type`, `pattern`, `purchases`, `per_day` + `per_day_rounded`, `typical_amount`; `not_applicable_lines`; obligations carry their `line` |
| confirm and save | `save_monthly_budget`: saves exactly the reviewed plan, its line kinds and the patterns the preview asked for |
| link a payment | `add_transaction` / `add_transactions` items / `update_transaction`: `obligation_ref` (+ `obligation_due_date`); `""` unlinks. Without a date MITA uses the earliest unpaid due date of the expense's month, else next month's first, and says which |
| refs | `get_recurring_expenses`: `obligation_ref` (`ob_…`, AES-SIV bound to the user) and this month's due dates with `paid` / `outstanding`; the calendar's bills carry it too |
| calendar | `get_calendar_month` / `show_financial_calendar` (component **v3**) |

An unlinked expense recorded in the category of an unpaid saved payment gets a
note naming it ("does not pay it… if the user says it was that payment, link
it") so ChatGPT asks; MITA never links by itself.

**Voice and receipts.** ChatGPT turns what the user says (typed or with
ChatGPT's own voice input) and what it reads from a receipt photo into tool
arguments. MITA receives structured arguments only — never audio, images or
files — and adds no speech or OCR service. The onboarding skill suggests voice
once, as a convenience.

## 6. Calendar (component `ui://mita/financial-calendar-v3.html`)

> **Superseded in part by 2.10.0 (2026-11-11, `flexible-envelopes-calendar.md`,
> component v4).** The "≈" daily guide is no longer drawn on dates and a date
> with nothing scheduled IS empty: with a category filter 2.7.0–2.9.0 drew a
> flexible line's stored daily share as each date's plan. The guidance
> (`left_per_day`, `summary.flexible_per_day`, the pace) is unchanged and is
> shown with the summary and each flexible line.

* Bills: `state` `paid` (from links) / overdue / due_today / upcoming / later;
  `paid`, `outstanding`, `paid_dates`, `obligation_ref`.
* Lines: `spending_type`, `pattern` (only when it describes this plan's own
  dates), `purchases` (from the base plan), `next_purchase`, flexible
  `left_per_day` (exact) + `left_per_day_rounded` + `left_per_week` —
  arithmetic, not a forecast.
* Dates: `planned_scheduled` (planned purchases + bills) and
  `planned_flexible` (guidance) add up to `planned`; `purchases` (each with
  `proposed`). Dates ahead show `planned_scheduled` in bold; a date with
  nothing scheduled shows the flexible budgets' daily guide as "≈€X"
  (`summary.flexible_per_day` = Σ each flexible line's `left_per_day`, never
  more than the month's safe average a day and never below 0: the user's own
  lines are never donors, so after an overspend nothing could cover — or a
  bill paid without its link — the envelopes can still show money that is no
  longer safe; then the safe average is the guide) — never a fabricated
  purchase, never an empty day. Told apart by "≈" and a lighter weight, in
  `--color-text-secondary` (WCAG AA; a paler colour failed axe).
* **Daily intelligence for flexible lines** (owner, 2026-11-04), all from the
  forecast engine's own per-category figures (the ones behind
  `categories_at_risk`): `pace_per_day` (spent ÷ days elapsed) against
  `planned_per_day` (the recommended pace), `pace_status` (not_started /
  on_pace / faster_than_pace at ≥ 1.2× — within the limit but running out
  early / over_limit), `days_until_exhausted`, and the revised safe pace
  `left_per_day` / `left_per_week`. Spending fast is not overspending; the
  monthly limit is. The summary carries `flexible_left`, `flexible_per_day`
  (+ rounded); the model's text names lines spending faster than their pace.

## 7. Before / after — the owner's November

| Figure | v2.6 (category rule) | 2.7.0 |
|---|---|---|
| Reserve with the €60 part + €23.50 cosmetics | 286.50 | **370.00** |
| Left to spend on 3 Nov | 1,124.50 | **1,041.00** (2,000 − 89 − 500 − 370) |
| Safe daily amount on 3 Nov | 41.65 | **38.56** (1,041 / 27) |
| Car loan state | "recorded" €60 | upcoming, paid 0.00, outstanding 270.00 |
| Cigarettes €200 | €9.52 every weekday | flexible: €200 a month, about €7 a day, no purchase dates |
| Medical insurance never stated | 60.65 lump on the 5th | flexible suggestion; removable (`not_applicable`) |

(Tests: `tests_mcp/test_obligation_payments.py`.)

## 8. Migrations, grants, deploy

* `0041_obligation_payments` and `0042_spending_patterns`: additive tables
  only, cascade with the user; both downgrade cleanly (tested up/down/up on
  the local test database). Applied by `mita-production`'s `start.sh`; the
  MCP service never migrates. Staging: from the operator machine through a
  temporary TCP proxy, as before.
* Grants (`scripts/mcp/mcp_service_role.sql`): `SELECT, INSERT, DELETE ON
  obligation_payments`, `SELECT, INSERT, UPDATE, DELETE ON spending_patterns`.
* Order: migrate → grant → MCP 2.7.0 → owner's real-ChatGPT run. Existing
  plans are not rewritten: the owner previews and saves November again to put
  each bill on its own line and the lines on their patterns; nothing links
  their existing expenses — link the real loan payments by telling ChatGPT
  which expense paid which bill.
* Rollback: re-pin 2.6.0. It ignores both tables and the `_mita_line_kind_v1`
  marker; `bill:` lines saved under 2.7.0 then read as plain lines (category
  rule, no identity) until the user saves the month again under 2.6.0. Data is
  not lost; downgrade 0042 → 0041 → 0040 drops only the new tables.

## 9. Limits and deferred work

* **Legacy months** (saved before 2.7.0) keep obligations under their
  categories: links decide what pays them, but an unlinked expense in that
  category on the bill's due date can use that date's row until the bill is
  paid (totals, reserve and states stay exact). Saving the month again ends it.
* One expense pays one due date; a combined payment of two bills is recorded
  as two expenses. A payment early across the month end counts in the ledger
  of the month it is recorded in; its due date is still shown as paid.
* `not_applicable` money is not redistributed to other MITA lines (the
  engine scales down only); it stays unallocated.
* The mobile app shows `bill:` lines by their code until it maps them to the
  payment's name (no Flutter change in this scope); everyday lines of mobile
  months keep per-date rebalancing.
* F-2 (expenses under the API's names, e.g. `dining`) still has no plan line
  of its own in the ledger and is covered by MITA's lines.
* Deferred, by the brief: no learning from history — a later phase may
  propose patterns from purchase frequency and amounts, persisted only after
  the user confirms (`source` would gain a value then).

## 10. Tests

`tests_mcp/test_obligation_payments.py` (13: the owner's car part and
cosmetics, linked / early / in parts / unlink / delete / refusals / isolation
/ legacy plan / weekly target / no ids leave MITA),
`tests_mcp/test_behavioral_budget.py` (10: Wednesdays, five Mondays, twice a
month / February / leap year / biweekly, flexible cigarettes, the €7 kept,
no medical insurance, Fuel protected, frequency change previewed then saved,
returning user, the whole authenticated flow with isolation); the F-8 and R3
suites rewritten to identity (`test_bill_due_dates.py`, `test_bills_reserve.py`,
`test_money_consistency.py`).
